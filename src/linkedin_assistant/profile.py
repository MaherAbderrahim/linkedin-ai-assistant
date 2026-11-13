from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter

from . import store
from .db import transaction
from .hashing import canonical_json

MAX_PROFILE_CHARS = 4000
_TOKEN = re.compile(r"[a-zà-ÿ0-9]{3,}")
_STOPWORDS = frozenset(
    "le la les de des du un une et en dans pour que qui sur avec ce ces son sa ses au aux "
    "est sont pas plus par ou où ne je tu il elle nous vous ils elles on se si comme mais donc "
    "ni car a à y été être avoir fait faire peut peuvent tout tous toute toutes mon ma mes ton ta tes "
    "notre votre leur leurs the and for with this that from are was were been being have has had "
    "do does did will would can could should may might must shall of in on at to by an as or if then "
    "than so such into over under again further once here there when where why how all any both each "
    "few more most other some no nor not only own same too very just because until while about against "
    "between through during before after above below up down out off it its is be".split()
)


def _top_terms(texts: list[str], limit: int) -> list[list]:
    counter: Counter = Counter()
    for text in texts:
        counter.update(t for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS)
    return [[term, count] for term, count in counter.most_common(limit)]


def refresh(conn: sqlite3.Connection, account: str, now: str | None = None) -> dict:
    now = now or store.utcnow()
    rows = conn.execute(
        "SELECT p.id, p.published_at, p.updated_at, v.id AS version_id, v.text, v.authorship "
        "FROM history_posts p JOIN history_versions v ON v.post_id = p.id AND v.version = p.current_version "
        "WHERE p.account = ?",
        (account,),
    ).fetchall()
    texts = [r["text"] for r in rows]
    lengths = [len(t) for t in texts]
    dates = sorted(r["published_at"] for r in rows if r["published_at"] is not None)
    by_authorship: dict = {}
    for r in rows:
        by_authorship[r["authorship"]] = by_authorship.get(r["authorship"], 0) + 1
    profile = {
        "version": "1",
        "account": account,
        "posts": len(rows),
        "by_authorship": by_authorship,
        "period": {"from": dates[0] if dates else None, "to": dates[-1] if dates else None},
        "length": {
            "avg": round(sum(lengths) / len(lengths)) if lengths else 0,
            "min": min(lengths) if lengths else 0,
            "max": max(lengths) if lengths else 0,
        },
    }
    for term_limit in (15, 10, 5, 0):
        profile["top_terms"] = _top_terms(texts, term_limit)
        profile["top_terms_reduced"] = term_limit < 15
        if len(canonical_json(profile)) <= MAX_PROFILE_CHARS:
            break
    refs = {
        "version_ids": [r["version_id"] for r in rows],
        "coverage": "versions courantes de l'archive autorisée",
        "confidence": "descriptif, recalculable, sans inférence sensible",
        "computed_at": now,
    }
    with transaction(conn):
        conn.execute("UPDATE style_profile SET valid = 0 WHERE valid = 1")
        conn.execute(
            "INSERT INTO style_profile (id, profile_json, source_refs_json, coverage, computed_at, valid) VALUES (?, ?, ?, ?, ?, 1)",
            (store.new_id(), canonical_json(profile), canonical_json(refs), refs["coverage"], now),
        )
    return {"profile": profile, "source_refs": refs, "computed_at": now, "stale": False}


def get(conn: sqlite3.Connection, account: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM style_profile WHERE valid = 1 ORDER BY computed_at DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    profile = json.loads(row["profile_json"])
    if profile.get("account") != account:
        return None
    latest = conn.execute(
        "SELECT MAX(updated_at) AS m FROM history_posts WHERE account = ?", (account,)
    ).fetchone()["m"]
    stale = latest is not None and latest > row["computed_at"]
    return {
        "profile": profile,
        "source_refs": json.loads(row["source_refs_json"]),
        "computed_at": row["computed_at"],
        "stale": stale,
    }