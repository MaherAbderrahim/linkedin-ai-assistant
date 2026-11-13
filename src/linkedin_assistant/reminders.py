from __future__ import annotations

import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from . import store

TZ = ZoneInfo("Africa/Tunis")
DEFAULT_HOUR = 9
DEFAULT_DAYS = "0,1,2,3,4,5,6"
DEFAULT_INACTIVITY_HOURS = 120

_REASONS_FR = {
    "inactivity": "Dernière publication connue au-delà du seuil d'inactivité.",
    "date_missing": "Aucune date de publication connue : déclarez-la avec /lastpost <date ISO>.",
    "future_date": "La dernière date de publication est dans le futur : vérifiez-la avec /lastpost.",
    "approximate_date": "Date de publication imprécise : précisez l'heure avec /lastpost.",
    "approximate_confirmed_at": "Approximation : date de confirmation du bot, pas une heure serveur LinkedIn.",
    "draft_pending": "Un brouillon attend votre validation (/preview).",
}


def set_enabled(conn: sqlite3.Connection, enabled: bool) -> None:
    store.set_setting(conn, "reminders_enabled", "1" if enabled else "0")


def _settings(conn: sqlite3.Connection) -> dict:
    return {
        "enabled": store.get_setting(conn, "reminders_enabled", "0") == "1",
        "hour": int(store.get_setting(conn, "reminder_hour", str(DEFAULT_HOUR))),
        "days": {int(d) for d in store.get_setting(conn, "reminder_days", DEFAULT_DAYS).split(",")},
        "inactivity_hours": int(store.get_setting(conn, "inactivity_hours", str(DEFAULT_INACTIVITY_HOURS))),
        "last_date": store.get_setting(conn, "last_reminder_date"),
    }


def last_known_publication(conn: sqlite3.Connection) -> dict | None:
    row = conn.execute(
        "SELECT published_at, published_at_precision FROM history_posts WHERE published_at IS NOT NULL ORDER BY published_at DESC LIMIT 1"
    ).fetchone()
    if row is not None:
        return {"at": row["published_at"], "precision": row["published_at_precision"], "basis": "published_at"}
    row = conn.execute(
        "SELECT confirmed_at FROM history_posts WHERE confirmed_at IS NOT NULL ORDER BY confirmed_at DESC LIMIT 1"
    ).fetchone()
    if row is not None:
        return {"at": row["confirmed_at"], "precision": "second", "basis": "confirmed_at_approx"}
    return None


def due(conn: sqlite3.Connection, now_utc: str) -> dict:
    now = datetime.fromisoformat(now_utc)
    local = now.astimezone(TZ)
    local_date = local.date().isoformat()
    settings = _settings(conn)
    decision = {"send": False, "reasons": [], "local_date": local_date, "basis": None}
    if not settings["enabled"]:
        decision["reasons"] = ["disabled"]
        return decision
    if local.weekday() not in settings["days"]:
        decision["reasons"] = ["wrong_day"]
        return decision
    if local.hour < settings["hour"]:
        decision["reasons"] = ["before_hour"]
        return decision
    if settings["last_date"] == local_date:
        decision["reasons"] = ["already_today"]
        return decision

    reasons: list[str] = []
    publication = last_known_publication(conn)
    if publication is None:
        reasons.append("date_missing")
    else:
        decision["basis"] = publication["basis"]
        published = datetime.fromisoformat(publication["at"])
        if published.tzinfo is None:
            published = published.replace(tzinfo=TZ)
        if published > now:
            reasons.append("future_date")
        elif publication["basis"] == "confirmed_at_approx":
            if (now - published).total_seconds() >= settings["inactivity_hours"] * 3600:
                reasons.extend(["approximate_confirmed_at", "inactivity"])
        elif publication["precision"] in ("day", "month", "year"):
            reasons.append("approximate_date")
        elif (now - published).total_seconds() >= settings["inactivity_hours"] * 3600:
            reasons.append("inactivity")

    draft_id = store.get_setting(conn, "active_draft")
    if draft_id:
        draft = conn.execute("SELECT state, current_revision FROM drafts WHERE id = ?", (draft_id,)).fetchone()
        if draft is not None and draft["state"] == "DRAFT" and draft["current_revision"] > 0:
            reasons.append("draft_pending")

    decision["reasons"] = reasons
    decision["send"] = bool(reasons)
    return decision


def build_message(decision: dict) -> str:
    parts = [_REASONS_FR[r] for r in decision["reasons"] if r in _REASONS_FR]
    return "Rappel (ne publie rien) :\n- " + "\n- ".join(parts)


def tick(conn: sqlite3.Connection, client, chat_id: int, now_utc: str) -> dict:
    decision = due(conn, now_utc)
    if decision["send"]:
        client.send_message(chat_id, build_message(decision))
        store.set_setting(conn, "last_reminder_date", decision["local_date"])
    return decision