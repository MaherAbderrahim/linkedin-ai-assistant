from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from . import store
from .db import transaction

ACTIVE_INTENTS = ("CREATED", "SENDING", "UNKNOWN_OUTCOME")


def purge(
    conn: sqlite3.Connection,
    now: str | None = None,
    draft_days: int = 30,
    event_days: int = 7,
) -> dict:
    now_dt = datetime.fromisoformat(now) if now else datetime.now(timezone.utc)
    draft_cutoff = (now_dt - timedelta(days=draft_days)).isoformat()
    event_cutoff = (now_dt - timedelta(days=event_days)).isoformat()
    counts = {"events": 0, "approvals": 0, "drafts": 0}
    with transaction(conn):
        counts["events"] = conn.execute(
            "DELETE FROM events WHERE state != 'NEW' AND created_at < ?", (event_cutoff,)
        ).rowcount
        counts["approvals"] = conn.execute(
            "DELETE FROM approvals WHERE consumed_at IS NULL AND expires_at IS NOT NULL AND expires_at < ?",
            (now_dt.isoformat(),),
        ).rowcount
        drafts = conn.execute(
            "SELECT id FROM drafts WHERE state IN ('IDEA', 'DRAFT', 'PUBLISHED') AND updated_at < ?",
            (draft_cutoff,),
        ).fetchall()
        for draft in drafts:
            active = conn.execute(
                f"SELECT id FROM publication_intents WHERE draft_id = ? AND state IN ({','.join('?' * len(ACTIVE_INTENTS))})",
                (draft["id"], *ACTIVE_INTENTS),
            ).fetchone()
            if active is not None:
                continue
            conn.execute("DELETE FROM publication_intents WHERE draft_id = ?", (draft["id"],))
            conn.execute("DELETE FROM approvals WHERE draft_id = ?", (draft["id"],))
            conn.execute("DELETE FROM draft_versions WHERE draft_id = ?", (draft["id"],))
            conn.execute("DELETE FROM drafts WHERE id = ?", (draft["id"],))
            counts["drafts"] += 1
    return counts