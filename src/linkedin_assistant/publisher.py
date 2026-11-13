from __future__ import annotations

import sqlite3

from . import store


class CertainPublicationError(Exception):
    """Rejet documenté sans effet externe : une nouvelle autorisation sera requise."""


class AmbiguousPublicationError(Exception):
    """L'envoi a pu aboutir côté LinkedIn : aucune nouvelle tentative automatique."""


class SimulatedPublisher:
    def __init__(self, outcome: str = "success", receipt: dict | None = None):
        self.outcome = outcome
        self.receipt = {"urn": "urn:li:share:simulated"} if receipt is None else receipt
        self.calls = 0

    def post(self, manifest: dict) -> dict:
        self.calls += 1
        if self.outcome == "success":
            return self.receipt
        if self.outcome == "certain_failure":
            raise CertainPublicationError("refus documenté simulé")
        raise AmbiguousPublicationError("réponse perdue simulée")


def publish(conn: sqlite3.Connection, intent_id: str, adapter, now: str | None = None) -> str:
    intent = conn.execute("SELECT * FROM publication_intents WHERE id = ?", (intent_id,)).fetchone()
    if intent is None:
        raise store.StoreError("INTENT_NOT_FOUND", intent_id)
    version = conn.execute(
        "SELECT v.manifest_json FROM draft_versions v JOIN drafts d ON d.id = v.draft_id AND d.current_revision = v.revision WHERE d.id = ?",
        (intent["draft_id"],),
    ).fetchone()
    manifest = store._loads(version["manifest_json"])
    store.mark_sending(conn, intent_id, now)
    try:
        receipt = adapter.post(manifest)
    except CertainPublicationError as exc:
        store.record_failure(conn, intent_id, str(exc), now)
        return "FAILED"
    except (AmbiguousPublicationError, TimeoutError) as exc:
        store.mark_unknown(conn, intent_id, str(exc), now)
        return "UNKNOWN_OUTCOME"
    store.record_success(conn, intent_id, receipt, now)
    return "PUBLISHED"
