from __future__ import annotations

import sqlite3

from . import history, profile

_FTS_AVAILABLE: bool | None = None


def fts_available(conn: sqlite3.Connection) -> bool:
    global _FTS_AVAILABLE
    if _FTS_AVAILABLE is None:
        try:
            conn.execute("CREATE VIRTUAL TABLE temp._fts_probe USING fts5(x)")
            conn.execute("DROP TABLE temp._fts_probe")
            _FTS_AVAILABLE = True
        except sqlite3.OperationalError:
            _FTS_AVAILABLE = False
    return _FTS_AVAILABLE


def _base_sql(since: str | None, until: str | None) -> tuple[str, list]:
    sql = (
        "SELECT p.id, p.account, p.published_at, p.published_at_precision, p.published_at_tz, "
        "p.confirmed_at, p.visibility, p.current_version, v.text, v.authorship, v.observed_at "
        "FROM history_posts p JOIN history_versions v ON v.post_id = p.id AND v.version = p.current_version "
        "WHERE p.account = ?"
    )
    params: list = []
    if since is not None:
        sql += " AND p.published_at >= ?"
        params.append(since)
    if until is not None:
        sql += " AND p.published_at <= ?"
        params.append(until)
    return sql, params


def _thematic(conn, account, topic, limit, since, until) -> tuple[list[dict], bool]:
    sql, params = _base_sql(since, until)
    params.insert(0, account)
    if fts_available(conn):
        try:
            conn.execute("CREATE VIRTUAL TABLE temp._retrieval_fts USING fts5(post_id UNINDEXED, text)")
            for row in conn.execute(sql, params):
                conn.execute("INSERT INTO temp._retrieval_fts (post_id, text) VALUES (?, ?)", (row["id"], row["text"]))
            phrase = '"' + topic.replace('"', '""') + '"'
            rows = conn.execute(
                "SELECT post_id FROM temp._retrieval_fts WHERE text MATCH ? LIMIT ?", (phrase, limit)
            ).fetchall()
            conn.execute("DROP TABLE temp._retrieval_fts")
            by_id = {r["id"]: dict(r) for r in conn.execute(sql, params)}
            ordered = [by_id[r["post_id"]] for r in rows if r["post_id"] in by_id]
            ordered.sort(key=lambda p: (p["published_at"] is None, p["published_at"] or ""), reverse=True)
            return ordered, True
        except sqlite3.OperationalError:
            conn.execute("DROP TABLE IF EXISTS temp._retrieval_fts")
    escaped = topic.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    rows = conn.execute(
        sql + " AND v.text LIKE ? ESCAPE '\\' ORDER BY (p.published_at IS NULL), p.published_at DESC LIMIT ?",
        (*params, f"%{escaped}%", limit),
    ).fetchall()
    return [dict(r) for r in rows], False


def select(
    conn: sqlite3.Connection,
    account: str,
    topic: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 6,
    max_chars: int = 12000,
) -> dict:
    recent_result = history.query(conn, account=account, limit=3, max_chars=max_chars, since=since, until=until)
    recent = recent_result["posts"]
    thematic, used_fts = _thematic(conn, account, topic, 3, since, until) if topic else ([], False)
    posts: list[dict] = []
    seen: set[str] = set()
    chars = 0
    stop = "char_budget" if recent_result["stop"] == "char_budget" else None
    for candidate in [*recent, *thematic]:
        if candidate["id"] in seen:
            continue
        if len(posts) >= limit:
            stop = "limit"
            break
        if chars + len(candidate["text"]) > max_chars:
            stop = "char_budget"
            break
        posts.append(candidate)
        seen.add(candidate["id"])
        chars += len(candidate["text"])
    rules = [
        r["rule_text"]
        for r in conn.execute("SELECT rule_text FROM preferences WHERE revoked_at IS NULL ORDER BY created_at")
    ]
    return {
        "posts": posts,
        "rules": rules,
        "profile": profile.get(conn, account),
        "stop": stop,
        "chars": chars,
        "fts": used_fts,
    }