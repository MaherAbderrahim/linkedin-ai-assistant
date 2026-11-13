from __future__ import annotations

import json
import sqlite3

from . import history, store
from .db import transaction
from .hashing import NORM_VERSION, canonical_json, normalized_hash, sha256_text

SOURCES = ("user_original", "assistant_published", "apify_skill", "other_api", "other_tool")
NAMESPACES = ("linkedin_urn", "linkedin_url", "provider_id")
PRECISIONS = ("second", "minute", "hour", "day", "month", "year")
MAX_ITEMS = 100
MAX_BYTES = 2 * 1024 * 1024
SCHEMA_VERSION = "1"
ACCEPTABLE = ("NEW", "KNOWN", "TEXT_CHANGED")


class ImportError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def parse_envelope(raw) -> dict:
    if isinstance(raw, str):
        if len(raw.encode("utf-8")) > MAX_BYTES:
            raise ImportError("BATCH_TOO_LARGE", "lot au-delà de 2 Mio")
        raw = json.loads(raw)
    if not isinstance(raw, dict):
        raise ImportError("BAD_ENVELOPE", "enveloppe attendue : objet JSON")
    if len(canonical_json(raw).encode("utf-8")) > MAX_BYTES:
        raise ImportError("BATCH_TOO_LARGE", "lot au-delà de 2 Mio")
    source = raw.get("source")
    if source not in SOURCES:
        raise ImportError("BAD_SOURCE", f"origine inconnue : {source}")
    account = raw.get("account")
    if not isinstance(account, str) or not account:
        raise ImportError("BAD_ACCOUNT", "account requis")
    posts = raw.get("posts")
    if not isinstance(posts, list) or not 1 <= len(posts) <= MAX_ITEMS:
        raise ImportError("BAD_POSTS", f"1 à {MAX_ITEMS} posts par lot")
    policy = raw.get("policy") or {}
    if policy.get("storage") != "allowed" or not policy.get("basis"):
        raise ImportError("POLICY_BLOCKED", "droits de stockage non établis : aucune persistance")
    for post in posts:
        if not isinstance(post, dict):
            raise ImportError("BAD_POST", "post attendu : objet")
        if "text" in post and not isinstance(post["text"], str):
            raise ImportError("BAD_POST", "text doit être une chaîne")
        for ident in post.get("identifiers") or []:
            if not isinstance(ident, dict) or ident.get("namespace") not in NAMESPACES or not ident.get("value"):
                raise ImportError("BAD_IDENTIFIER", "identifiant typé requis (namespace + value)")
    return {
        "source": source,
        "provider": raw.get("provider"),
        "account": account,
        "posts": posts,
        "coverage": raw.get("coverage") or {},
        "policy": policy,
    }


def _dates_compatible(a: str | None, b: str | None) -> bool:
    return a is None or b is None or a == b


def _classify(conn: sqlite3.Connection, post: dict, account: str) -> dict:
    reasons: list[str] = []
    item = {"status": None, "post_id": None, "expected_version": None, "reasons": reasons}
    post_policy = post.get("policy")
    if post_policy is not None and post_policy.get("storage") != "allowed":
        item["status"] = "POLICY_BLOCKED"
        reasons.append("droits de stockage du post non établis")
        return item
    text = post.get("text")
    if not text or not text.strip():
        item["status"] = "INCOMPLETE"
        reasons.append("texte absent")
        return item
    published_at = post.get("published_at")
    if published_at is not None and post.get("precision") not in PRECISIONS:
        item["status"] = "INCOMPLETE"
        reasons.append("published_at sans précision valide")
        return item
    author = post.get("author")
    if author is not None and author != account:
        item["status"] = "METADATA_CONFLICT"
        reasons.append("auteur différent du compte du lot")
        return item

    matched = set()
    for ident in post.get("identifiers") or []:
        post_id = history.find_by_identifier(conn, ident["namespace"], ident["value"])
        if post_id is not None:
            matched.add(post_id)
    if len(matched) > 1:
        item["status"] = "AMBIGUOUS"
        reasons.append("identifiants pointant vers plusieurs posts existants")
        return item
    if len(matched) == 1:
        post_id = matched.pop()
        existing = conn.execute(
            "SELECT p.published_at, p.current_version, v.text FROM history_posts p "
            "JOIN history_versions v ON v.post_id = p.id AND v.version = p.current_version WHERE p.id = ?",
            (post_id,),
        ).fetchone()
        item["post_id"] = post_id
        item["expected_version"] = existing["current_version"]
        if not _dates_compatible(existing["published_at"], published_at):
            item["status"] = "METADATA_CONFLICT"
            reasons.append("date de publication en conflit")
        elif sha256_text(existing["text"]) != sha256_text(text):
            item["status"] = "TEXT_CHANGED"
            reasons.append("texte différent de la version archivée")
        else:
            item["status"] = "KNOWN"
        return item

    if post.get("identifiers"):
        item["status"] = "NEW"
        reasons.append("identifiants typés inconnus : post distinct, pas de repli texte")
        return item
    if published_at is None:
        item["status"] = "AMBIGUOUS"
        reasons.append("ni identifiant connu ni date : rapprochement non fiable")
        return item
    candidates = [
        c for c in history.normalized_candidates(conn, account, text)
        if _dates_compatible(c["published_at"], published_at)
    ]
    if len(candidates) == 1:
        item["status"] = "KNOWN"
        item["post_id"] = candidates[0]["id"]
        item["expected_version"] = candidates[0]["current_version"]
        reasons.append("rapprochement texte normalisé + date")
    elif len(candidates) > 1:
        item["status"] = "AMBIGUOUS"
        reasons.append("plusieurs candidats texte normalisé + date")
    else:
        item["status"] = "NEW"
    return item


def preview(conn: sqlite3.Connection, envelope: dict, now: str | None = None) -> dict:
    now = now or store.utcnow()
    batch_hash = sha256_text(canonical_json(envelope))
    existing = conn.execute("SELECT * FROM import_batches WHERE batch_hash = ?", (batch_hash,)).fetchone()
    if existing is not None:
        return {
            "batch_id": existing["id"],
            "plan": json.loads(existing["plan_json"]),
            "state": existing["state"],
            "reused": True,
        }
    items = []
    for index, post in enumerate(envelope["posts"]):
        item = _classify(conn, post, envelope["account"])
        item["index"] = index
        items.append(item)
    plan = {
        "account": envelope["account"],
        "source": envelope["source"],
        "provider": envelope.get("provider"),
        "policy": envelope["policy"],
        "posts": envelope["posts"],
        "items": items,
    }
    batch_id = store.new_id()
    with transaction(conn):
        conn.execute(
            "INSERT INTO import_batches (id, origin, batch_hash, schema_version, plan_json, state, created_at) VALUES (?, ?, ?, ?, ?, 'PREVIEWED', ?)",
            (batch_id, envelope["source"], batch_hash, SCHEMA_VERSION, canonical_json(plan), now),
        )
    return {"batch_id": batch_id, "plan": plan, "state": "PREVIEWED", "reused": False}


def _authorship(source: str) -> str:
    if source == "assistant_published":
        return "assistant"
    if source == "user_original":
        return "user"
    return "external"


def _attach_identifiers(conn, post_id: str, post: dict, source_id: str) -> None:
    for ident in post.get("identifiers") or []:
        owner = history.find_by_identifier(conn, ident["namespace"], ident["value"])
        if owner == post_id:
            continue
        if owner is not None:
            raise ImportError("IDENTIFIER_CONFLICT", "identifiant déjà rattaché à un autre post")
        conn.execute(
            "INSERT INTO history_identifiers (id, post_id, namespace, identifier, source_id) VALUES (?, ?, ?, ?, ?)",
            (store.new_id(), post_id, ident["namespace"], ident["value"], source_id),
        )


def _fill_dates(conn, post_id: str, post: dict, now: str) -> None:
    existing = conn.execute("SELECT published_at FROM history_posts WHERE id = ?", (post_id,)).fetchone()
    if existing["published_at"] is None and post.get("published_at") is not None:
        conn.execute(
            "UPDATE history_posts SET published_at = ?, published_at_precision = ?, published_at_tz = ?, updated_at = ? WHERE id = ?",
            (post["published_at"], post.get("precision"), post.get("tz"), now, post_id),
        )


def _observation(conn, post_id, version_id, post, envelope, now) -> str:
    source_id = store.new_id()
    policy = post.get("policy") or envelope["policy"]
    conn.execute(
        "INSERT INTO history_sources (id, post_id, version_id, origin, method, provider, provider_ref, imported_at, fields_json, policy_json, expires_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            source_id,
            post_id,
            version_id,
            envelope["source"],
            post.get("method") or envelope.get("provider") or "import",
            envelope.get("provider"),
            post.get("provider_ref"),
            now,
            canonical_json({"url": post.get("url"), "visibility": post.get("visibility")}),
            canonical_json(policy),
            policy.get("expires_at"),
        ),
    )
    return source_id


def _insert_post(conn, post, envelope, now) -> str:
    post_id = store.new_id()
    version_id = store.new_id()
    text = post["text"]
    conn.execute(
        "INSERT INTO history_posts (id, account, current_version, published_at, published_at_precision, published_at_tz, confirmed_at, visibility, created_at, updated_at) "
        "VALUES (?, ?, 1, ?, ?, ?, NULL, ?, ?, ?)",
        (post_id, envelope["account"], post.get("published_at"), post.get("precision"), post.get("tz"), post.get("visibility"), now, now),
    )
    conn.execute(
        "INSERT INTO history_versions (id, post_id, version, text, exact_hash, normalized_hash, norm_version, authorship, observed_at) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?)",
        (version_id, post_id, text, sha256_text(text), normalized_hash(text), NORM_VERSION, _authorship(envelope["source"]), now),
    )
    source_id = _observation(conn, post_id, version_id, post, envelope, now)
    _attach_identifiers(conn, post_id, post, source_id)
    return post_id


def _current_version_id(conn, post_id: str) -> str:
    row = conn.execute(
        "SELECT v.id FROM history_versions v JOIN history_posts p ON p.id = v.post_id AND v.version = p.current_version WHERE p.id = ?",
        (post_id,),
    ).fetchone()
    return row["id"]


def commit(conn: sqlite3.Connection, batch_id: str, accept: list[int] | None, actor: str, now: str | None = None) -> dict:
    now = now or store.utcnow()
    batch = conn.execute("SELECT * FROM import_batches WHERE id = ?", (batch_id,)).fetchone()
    if batch is None:
        raise ImportError("BATCH_NOT_FOUND", batch_id)
    plan = json.loads(batch["plan_json"])
    items = plan["items"]
    if accept is None:
        accept = [i["index"] for i in items if i["status"] in ACCEPTABLE]
    accept = sorted(set(accept))
    if batch["state"] in ("COMMITTED", "REJECTED"):
        prior = json.loads(batch["decisions_json"])
        if prior.get("accept") == accept and prior.get("actor") == actor:
            return {"batch_id": batch_id, "state": batch["state"], "imported": prior.get("imported", 0)}
        raise ImportError("BATCH_ALREADY_COMMITTED", "lot déjà traité avec d'autres décisions")
    if batch["state"] != "PREVIEWED":
        raise ImportError("BAD_BATCH_STATE", batch["state"])

    by_index = {i["index"]: i for i in items}
    for index in accept:
        item = by_index.get(index)
        if item is None or item["status"] not in ACCEPTABLE:
            raise ImportError("ITEM_NOT_ACCEPTABLE", f"élément {index} non importable")

    posts = plan["posts"]
    seen: set[tuple] = set()
    imported = 0
    with transaction(conn):
        for index in accept:
            item = by_index[index]
            post = posts[index]
            text = post["text"]
            exact = sha256_text(text)
            id_key = tuple(sorted((i["namespace"], i["value"]) for i in post.get("identifiers") or []))
            if (exact, id_key) in seen:
                raise ImportError("DUPLICATE_IN_BATCH", "deux posts identiques dans le même lot")
            seen.add((exact, id_key))
            if item["status"] == "NEW":
                if not id_key:
                    known = conn.execute(
                        "SELECT v.id FROM history_versions v JOIN history_posts p ON p.id = v.post_id WHERE v.exact_hash = ? AND p.account = ?",
                        (exact, plan["account"]),
                    ).fetchone()
                    if known is not None:
                        raise ImportError("BATCH_STALE", "contenu archivé depuis l'aperçu : nouvel aperçu requis")
                _insert_post(conn, post, plan, now)
            else:
                post_id = item["post_id"]
                current = conn.execute("SELECT current_version FROM history_posts WHERE id = ?", (post_id,)).fetchone()
                if current is None or current["current_version"] != item["expected_version"]:
                    raise ImportError("BATCH_STALE", "post modifié depuis l'aperçu : nouvel aperçu requis")
                if item["status"] == "TEXT_CHANGED":
                    version = current["current_version"] + 1
                    version_id = store.new_id()
                    conn.execute(
                        "INSERT INTO history_versions (id, post_id, version, text, exact_hash, normalized_hash, norm_version, authorship, observed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (version_id, post_id, version, text, exact, normalized_hash(text), NORM_VERSION, _authorship(plan["source"]), now),
                    )
                    conn.execute(
                        "UPDATE history_posts SET current_version = ?, updated_at = ? WHERE id = ?", (version, now, post_id)
                    )
                else:
                    version_id = _current_version_id(conn, post_id)
                source_id = _observation(conn, post_id, version_id, post, plan, now)
                _attach_identifiers(conn, post_id, post, source_id)
                _fill_dates(conn, post_id, post, now)
            imported += 1
        decisions = {"actor": actor, "accept": accept, "imported": imported}
        state = "COMMITTED" if accept else "REJECTED"
        conn.execute(
            "UPDATE import_batches SET state = ?, decisions_json = ?, committed_at = ? WHERE id = ?",
            (state, canonical_json(decisions), now, batch_id),
        )
    return {"batch_id": batch_id, "state": state, "imported": imported}