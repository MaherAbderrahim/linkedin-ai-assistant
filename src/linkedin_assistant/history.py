from __future__ import annotations

import sqlite3

from .hashing import normalized_hash


def find_by_identifier(conn: sqlite3.Connection, namespace: str, value: str) -> str | None:
    row = conn.execute(
        "SELECT post_id FROM history_identifiers WHERE namespace = ? AND identifier = ?",
        (namespace, value),
    ).fetchone()
    return row["post_id"] if row is not None else None


def normalized_candidates(conn: sqlite3.Connection, account: str, text: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT p.id, p.published_at, p.current_version, v.text FROM history_versions v "
        "JOIN history_posts p ON p.id = v.post_id "
        "WHERE v.normalized_hash = ? AND p.account = ? AND v.version = p.current_version",
        (normalized_hash(text), account),
    ).fetchall()


def query(
    conn: sqlite3.Connection,
    account: str | None = None,
    limit: int = 6,
    max_chars: int = 12000,
    since: str | None = None,
    until: str | None = None,
) -> dict:
    sql = (
        "SELECT p.id, p.account, p.published_at, p.published_at_precision, p.published_at_tz, "
        "p.confirmed_at, p.visibility, p.current_version, v.text, v.authorship, v.observed_at "
        "FROM history_posts p JOIN history_versions v ON v.post_id = p.id AND v.version = p.current_version "
        "WHERE 1=1"
    )
    params: list = []
    if account is not None:
        sql += " AND p.account = ?"
        params.append(account)
    if since is not None:
        sql += " AND p.published_at >= ?"
        params.append(since)
    if until is not None:
        sql += " AND p.published_at <= ?"
        params.append(until)
    sql += " ORDER BY (p.published_at IS NULL), p.published_at DESC, p.created_at DESC"
    posts: list[dict] = []
    chars = 0
    stop = None
    for row in conn.execute(sql, params):
        if len(posts) >= limit:
            stop = "limit"
            break
        if chars + len(row["text"]) > max_chars:
            stop = "char_budget"
            break
        posts.append(dict(row))
        chars += len(row["text"])
    return {"posts": posts, "stop": stop, "chars": chars}