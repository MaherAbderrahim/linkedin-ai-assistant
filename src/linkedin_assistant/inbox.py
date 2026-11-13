from __future__ import annotations

import json
import sqlite3

from . import store
from .db import transaction


def poll_once(conn: sqlite3.Connection, client, timeout: int) -> int:
    offset = int(store.get_setting(conn, "telegram_offset", "0"))
    updates = client.get_updates(offset, timeout)
    if not updates:
        return 0
    new = 0
    with transaction(conn):
        for update in updates:
            update_id = update.get("update_id")
            if update_id is None:
                continue
            if store.ingest_event(conn, "telegram", str(update_id), update):
                new += 1
        store.set_setting(conn, "telegram_offset", str(max(u["update_id"] for u in updates) + 1))
    return new


def process_pending(conn: sqlite3.Connection, handler) -> int:
    rows = conn.execute(
        "SELECT id, payload_json FROM events WHERE source = 'telegram' AND state = 'NEW' ORDER BY CAST(external_id AS INTEGER)"
    ).fetchall()
    done = 0
    for row in rows:
        payload = json.loads(row["payload_json"])
        try:
            handler(payload)
        except Exception:
            conn.execute("UPDATE events SET state = 'FAILED', processed_at = ? WHERE id = ?", (store.utcnow(), row["id"]))
            raise
        conn.execute(
            "UPDATE events SET state = 'PROCESSED', processed_at = ? WHERE id = ?", (store.utcnow(), row["id"])
        )
        done += 1
    return done