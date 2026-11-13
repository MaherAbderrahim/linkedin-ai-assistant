from linkedin_assistant import importing, profile, retrieval, store
from linkedin_assistant.hashing import canonical_json

from conftest import ACCOUNT
from test_import import envelope, post, urn


def import_posts(conn, posts, source="user_original", now=None):
    env = importing.parse_envelope(envelope(posts, source=source))
    batch = importing.preview(conn, env, now=now)
    return importing.commit(conn, batch["batch_id"], None, "owner", now=now)


def test_empty_profile(conn):
    result = profile.refresh(conn, ACCOUNT)
    assert result["profile"]["posts"] == 0
    fetched = profile.get(conn, ACCOUNT)
    assert fetched is not None
    assert fetched["stale"] is False


def test_descriptive_profile_only(conn):
    import_posts(conn, [post(text="Premier post utilisateur.", ids=[urn("urn:li:share:1")])])
    import_posts(conn, [post(text="Deuxième post utilisateur.", ids=[urn("urn:li:share:2")])])
    import_posts(
        conn,
        [post(text="Post de l'assistant.", ids=[urn("urn:li:share:3")])],
        source="assistant_published",
    )
    result = profile.refresh(conn, ACCOUNT)
    p = result["profile"]
    assert p["posts"] == 3
    assert p["by_authorship"] == {"user": 2, "assistant": 1}
    assert p["period"]["from"] == "2026-11-01T10:00:00+01:00"
    assert p["length"]["avg"] > 0
    assert set(p) == {"version", "account", "posts", "by_authorship", "period", "length", "top_terms", "top_terms_reduced"}
    assert result["source_refs"]["version_ids"]
    assert "descriptif" in result["source_refs"]["confidence"]


def test_profile_staleness(conn):
    t1 = "2026-11-01T00:00:00+00:00"
    t2 = "2026-11-02T00:00:00+00:00"
    import_posts(conn, [post(ids=[urn("urn:li:share:1")])], now=t1)
    profile.refresh(conn, ACCOUNT, now=t1)
    assert profile.get(conn, ACCOUNT)["stale"] is False
    import_posts(conn, [post(text="Nouveau post.", ids=[urn("urn:li:share:2")])], now=t2)
    assert profile.get(conn, ACCOUNT)["stale"] is True
    profile.refresh(conn, ACCOUNT, now=t2)
    assert profile.get(conn, ACCOUNT)["stale"] is False


def test_profile_bounded(conn):
    posts = [
        post(text=f"mot{i} " * 120, published_at=f"2026-01-{i % 28 + 1:02d}T10:00:00+01:00", ids=[urn(f"urn:li:share:{i}")])
        for i in range(100)
    ]
    import_posts(conn, posts)
    result = profile.refresh(conn, ACCOUNT)
    assert len(canonical_json(result["profile"])) <= 4000
    assert result["profile"]["posts"] == 100


def sample_archive(conn):
    posts = []
    for i in range(10):
        topic = "Python automation" if i < 5 else "Cuisine recette"
        posts.append(
            post(
                text=f"{topic} post {i} " + "x" * 80,
                published_at=f"2026-11-{i + 1:02d}T10:00:00+01:00",
                ids=[urn(f"urn:li:share:{i}")],
            )
        )
    import_posts(conn, posts)
    profile.refresh(conn, ACCOUNT)


def test_retrieval_topic_and_bounds(conn):
    sample_archive(conn)
    result = retrieval.select(conn, ACCOUNT, topic="python")
    assert 1 <= len(result["posts"]) <= 6
    assert result["chars"] <= 12000
    assert any("Python" in p["text"] for p in result["posts"])
    archived = {r["text"] for r in conn.execute("SELECT text FROM history_versions")}
    assert all(p["text"] in archived for p in result["posts"])
    assert result["profile"] is not None


def test_retrieval_rules_separate(conn):
    sample_archive(conn)
    conn.execute(
        "INSERT INTO preferences (id, rule_text, scope, created_at) VALUES (?, ?, 'global', ?)",
        (store.new_id(), "Toujours citer les sources.", store.utcnow()),
    )
    conn.execute(
        "INSERT INTO preferences (id, rule_text, scope, created_at, revoked_at) VALUES (?, ?, 'global', ?, ?)",
        (store.new_id(), "Règle abolie.", store.utcnow(), store.utcnow()),
    )
    result = retrieval.select(conn, ACCOUNT)
    assert result["rules"] == ["Toujours citer les sources."]


def test_retrieval_like_fallback(conn, monkeypatch):
    sample_archive(conn)
    monkeypatch.setattr(retrieval, "_FTS_AVAILABLE", False)
    result = retrieval.select(conn, ACCOUNT, topic="python")
    assert result["fts"] is False
    assert any("Python" in p["text"] for p in result["posts"])


def test_retrieval_char_budget_whole_posts(conn):
    sample_archive(conn)
    result = retrieval.select(conn, ACCOUNT, max_chars=250)
    assert result["stop"] == "char_budget"
    archived = {r["text"] for r in conn.execute("SELECT text FROM history_versions")}
    assert all(p["text"] in archived for p in result["posts"])


def test_retrieval_period(conn):
    sample_archive(conn)
    result = retrieval.select(conn, ACCOUNT, since="2026-11-08T00:00:00+01:00", until="2026-11-09T23:59:59+01:00")
    assert len(result["posts"]) == 2
    assert all("2026-11-08" <= p["published_at"] <= "2026-11-09T23:59:59+01:00" for p in result["posts"])