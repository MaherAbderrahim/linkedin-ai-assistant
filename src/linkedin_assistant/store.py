from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone

from .db import transaction
from .hashing import (
    NORM_VERSION,
    approval_fingerprint,
    canonical_json,
    content_fingerprint,
    normalized_hash,
    sha256_text,
)

ACTIVE_INTENT_STATES = ("CREATED", "SENDING", "UNKNOWN_OUTCOME")


class StoreError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex


def create_draft(conn: sqlite3.Connection, now: str | None = None) -> str:
    now = now or utcnow()
    draft_id = new_id()
    conn.execute(
        "INSERT INTO drafts (id, state, current_revision, created_at, updated_at) VALUES (?, 'IDEA', 0, ?, ?)",
        (draft_id, now, now),
    )
    return draft_id


def add_revision(
    conn: sqlite3.Connection,
    draft_id: str,
    text: str,
    manifest: dict,
    now: str | None = None,
) -> int:
    now = now or utcnow()
    manifest = dict(manifest)
    manifest["text"] = text
    with transaction(conn):
        row = conn.execute("SELECT current_revision, state FROM drafts WHERE id = ?", (draft_id,)).fetchone()
        if row is None:
            raise StoreError("DRAFT_NOT_FOUND", draft_id)
        if row["state"] == "PUBLISHING":
            raise StoreError("DRAFT_LOCKED", "édition impossible pendant un envoi")
        revision = row["current_revision"] + 1
        conn.execute(
            "INSERT INTO draft_versions (draft_id, revision, text, manifest_json, content_hash, approval_hash, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                draft_id,
                revision,
                text,
                _json(manifest),
                content_fingerprint(manifest),
                approval_fingerprint(draft_id, revision, manifest),
                now,
            ),
        )
        conn.execute(
            "UPDATE drafts SET current_revision = ?, state = 'DRAFT', blocked_reason = NULL, updated_at = ? WHERE id = ?",
            (revision, now, draft_id),
        )
    return revision


def record_approval(
    conn: sqlite3.Connection,
    draft_id: str,
    revision: int,
    kind: str,
    actor: str,
    now: str | None = None,
    expires_at: str | None = None,
) -> str:
    now = now or utcnow()
    if kind not in ("TEXT", "IMAGE", "NO_IMAGE", "FINAL", "RULE"):
        raise StoreError("BAD_APPROVAL_KIND", kind)
    with transaction(conn):
        version = _version(conn, draft_id, revision)
        draft = conn.execute("SELECT current_revision FROM drafts WHERE id = ?", (draft_id,)).fetchone()
        if draft["current_revision"] != revision:
            raise StoreError("STALE_REVISION", "approbation sur une révision périmée")
        if kind == "FINAL":
            _require_content_approvals(conn, draft_id, revision, now)
        approval_id = new_id()
        conn.execute(
            "INSERT INTO approvals (id, draft_id, revision, kind, actor, object_hash, nonce, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (approval_id, draft_id, revision, kind, actor, version["approval_hash"], new_id(), now, expires_at),
        )
    return approval_id


def consume_final_and_create_intent(
    conn: sqlite3.Connection,
    approval_id: str,
    actor: str,
    now: str | None = None,
) -> str:
    now = now or utcnow()
    with transaction(conn):
        approval = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        if approval is None or approval["kind"] != "FINAL":
            raise StoreError("NO_FINAL_APPROVAL", "autorisation finale absente")
        if approval["actor"] != actor:
            raise StoreError("ACTOR_MISMATCH", "acteur non autorisé")
        if approval["consumed_at"] is not None:
            raise StoreError("APPROVAL_CONSUMED", "autorisation déjà utilisée")
        if approval["expires_at"] is not None and approval["expires_at"] <= now:
            raise StoreError("APPROVAL_EXPIRED", "autorisation expirée")
        draft = conn.execute("SELECT * FROM drafts WHERE id = ?", (approval["draft_id"],)).fetchone()
        if draft["current_revision"] != approval["revision"]:
            raise StoreError("STALE_REVISION", "le brouillon a changé depuis l'aperçu")
        version = _version(conn, draft["id"], draft["current_revision"])
        if version["approval_hash"] != approval["object_hash"]:
            raise StoreError("MANIFEST_MISMATCH", "le contenu approuvé a changé")
        _require_content_approvals(conn, draft["id"], draft["current_revision"], now)
        manifest = _loads(version["manifest_json"])
        account = manifest["account"]
        locked = conn.execute(
            "SELECT id FROM publication_intents WHERE account = ? AND state IN ('CREATED', 'SENDING', 'UNKNOWN_OUTCOME')",
            (account,),
        ).fetchone()
        if locked is not None:
            raise StoreError("ACCOUNT_LOCKED", "publication bloquée sur ce compte")
        duplicate = conn.execute(
            "SELECT id FROM publication_intents WHERE content_hash = ? AND state IN ('CREATED', 'SENDING', 'UNKNOWN_OUTCOME', 'PUBLISHED')",
            (version["content_hash"],),
        ).fetchone()
        if duplicate is not None:
            raise StoreError("DUPLICATE_CONTENT", "contenu identique déjà envoyé ou en cours")
        known = conn.execute(
            "SELECT v.id FROM history_versions v JOIN history_posts p ON p.id = v.post_id WHERE v.exact_hash = ? AND p.account = ?",
            (sha256_text(version["text"]), account),
        ).fetchone()
        if known is not None:
            raise StoreError("DUPLICATE_CONTENT", "texte déjà présent dans l'archive")
        intent_id = new_id()
        conn.execute(
            "INSERT INTO publication_intents (id, draft_id, account, content_hash, state, approval_id, created_at) VALUES (?, ?, ?, ?, 'CREATED', ?, ?)",
            (intent_id, draft["id"], account, version["content_hash"], approval_id, now),
        )
        conn.execute("UPDATE approvals SET consumed_at = ? WHERE id = ?", (now, approval_id))
        conn.execute("UPDATE drafts SET state = 'PUBLISHING', updated_at = ? WHERE id = ?", (now, draft["id"]))
    return intent_id


def mark_sending(conn: sqlite3.Connection, intent_id: str, now: str | None = None) -> None:
    now = now or utcnow()
    with transaction(conn):
        intent = _intent(conn, intent_id)
        if intent["state"] != "CREATED":
            raise StoreError("INVALID_STATE", f"envoi déjà commencé ou résolu: {intent['state']}")
        conn.execute("UPDATE publication_intents SET state = 'SENDING', sending_at = ? WHERE id = ?", (now, intent_id))


def record_success(
    conn: sqlite3.Connection,
    intent_id: str,
    receipt: dict,
    now: str | None = None,
) -> str:
    now = now or utcnow()
    with transaction(conn):
        intent = _intent(conn, intent_id)
        if intent["state"] != "SENDING":
            raise StoreError("INVALID_STATE", "succès enregistré sans envoi commencé")
        draft = conn.execute("SELECT * FROM drafts WHERE id = ?", (intent["draft_id"],)).fetchone()
        version = _version(conn, draft["id"], draft["current_revision"])
        post_id = new_id()
        version_id = new_id()
        conn.execute(
            "INSERT INTO history_posts (id, account, current_version, published_at, published_at_precision, published_at_tz, confirmed_at, visibility, created_at, updated_at) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?)",
            (
                post_id,
                intent["account"],
                receipt.get("published_at"),
                receipt.get("published_at_precision"),
                receipt.get("published_at_tz"),
                now,
                _loads(version["manifest_json"]).get("visibility"),
                now,
                now,
            ),
        )
        conn.execute(
            "INSERT INTO history_versions (id, post_id, version, text, exact_hash, normalized_hash, norm_version, authorship, observed_at) VALUES (?, ?, 1, ?, ?, ?, ?, 'assistant', ?)",
            (version_id, post_id, version["text"], sha256_text(version["text"]), normalized_hash(version["text"]), NORM_VERSION, now),
        )
        if receipt.get("urn"):
            conn.execute(
                "INSERT INTO history_identifiers (id, post_id, namespace, identifier) VALUES (?, ?, 'linkedin_urn', ?)",
                (new_id(), post_id, receipt["urn"]),
            )
        conn.execute(
            "INSERT INTO history_sources (id, post_id, version_id, origin, method, provider, imported_at, fields_json, policy_json) VALUES (?, ?, ?, 'assistant_published', 'linkedin_api', 'linkedin', ?, ?, '{}')",
            (new_id(), post_id, version_id, now, _json({"urn": receipt.get("urn"), "url": receipt.get("url")})),
        )
        conn.execute(
            "UPDATE publication_intents SET state = 'PUBLISHED', receipt_json = ?, history_post_id = ?, resolved_at = ? WHERE id = ?",
            (_json(receipt), post_id, now, intent_id),
        )
        conn.execute("UPDATE drafts SET state = 'PUBLISHED', updated_at = ? WHERE id = ?", (now, draft["id"]))
    return post_id


def record_failure(conn: sqlite3.Connection, intent_id: str, error: str, now: str | None = None) -> None:
    now = now or utcnow()
    with transaction(conn):
        intent = _intent(conn, intent_id)
        if intent["state"] != "SENDING":
            raise StoreError("INVALID_STATE", "échec enregistré sans envoi commencé")
        conn.execute(
            "UPDATE publication_intents SET state = 'FAILED', error = ?, resolved_at = ? WHERE id = ?",
            (error, now, intent_id),
        )
        conn.execute(
            "UPDATE drafts SET state = 'BLOCKED', blocked_reason = 'publication_failed', updated_at = ? WHERE id = ?",
            (now, intent["draft_id"]),
        )


def mark_unknown(conn: sqlite3.Connection, intent_id: str, reason: str, now: str | None = None) -> None:
    now = now or utcnow()
    with transaction(conn):
        intent = _intent(conn, intent_id)
        if intent["state"] != "SENDING":
            raise StoreError("INVALID_STATE", "incertitude enregistrée sans envoi commencé")
        conn.execute(
            "UPDATE publication_intents SET state = 'UNKNOWN_OUTCOME', error = ? WHERE id = ?",
            (reason, intent_id),
        )
        conn.execute(
            "UPDATE drafts SET state = 'BLOCKED', blocked_reason = 'unknown_outcome', updated_at = ? WHERE id = ?",
            (now, intent["draft_id"]),
        )


def get_setting(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row is not None else default


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def find_valid_approval(
    conn: sqlite3.Connection, draft_id: str, revision: int, kind: str, now: str | None = None
) -> str | None:
    now = now or utcnow()
    row = conn.execute(
        "SELECT id FROM approvals WHERE draft_id = ? AND revision = ? AND kind = ? AND consumed_at IS NULL AND (expires_at IS NULL OR expires_at > ?) ORDER BY created_at DESC LIMIT 1",
        (draft_id, revision, kind, now),
    ).fetchone()
    return row["id"] if row is not None else None


def ingest_event(conn: sqlite3.Connection, source: str, external_id: str, payload: dict, now: str | None = None) -> bool:
    now = now or utcnow()
    try:
        conn.execute(
            "INSERT INTO events (id, source, external_id, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (new_id(), source, external_id, _json(payload), now),
        )
        return True
    except sqlite3.IntegrityError:
        return False


def _require_content_approvals(conn: sqlite3.Connection, draft_id: str, revision: int, now: str) -> None:
    rows = conn.execute(
        "SELECT kind, expires_at FROM approvals WHERE draft_id = ? AND revision = ? AND kind IN ('TEXT', 'IMAGE', 'NO_IMAGE')",
        (draft_id, revision),
    ).fetchall()
    valid = [r["kind"] for r in rows if r["expires_at"] is None or r["expires_at"] > now]
    if "TEXT" not in valid or not ({"IMAGE", "NO_IMAGE"} & set(valid)):
        raise StoreError("CONTENT_NOT_APPROVED", "texte et image/absence doivent être approuvés")


def _version(conn: sqlite3.Connection, draft_id: str, revision: int) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM draft_versions WHERE draft_id = ? AND revision = ?", (draft_id, revision)
    ).fetchone()
    if row is None:
        raise StoreError("VERSION_NOT_FOUND", f"{draft_id}:{revision}")
    return row


def _intent(conn: sqlite3.Connection, intent_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM publication_intents WHERE id = ?", (intent_id,)).fetchone()
    if row is None:
        raise StoreError("INTENT_NOT_FOUND", intent_id)
    return row


def _json(obj) -> str:
    return canonical_json(obj)


def _loads(text: str):
    return json.loads(text)
