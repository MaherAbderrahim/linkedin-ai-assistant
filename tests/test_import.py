import pytest

from linkedin_assistant import history, importing, store
from linkedin_assistant.importing import ImportError as ImpErr
from linkedin_assistant.publisher import SimulatedPublisher, publish

from conftest import ACCOUNT, approved_draft


def envelope(posts, source="user_original", account=ACCOUNT, policy=None, provider=None):
    return {
        "source": source,
        "provider": provider,
        "account": account,
        "posts": posts,
        "coverage": {},
        "policy": policy or {"storage": "allowed", "basis": "test : textes fournis directement"},
    }


def post(text="Bonjour LinkedIn.", published_at="2026-11-01T10:00:00+01:00", precision="second", ids=None, **kw):
    p = {
        "text": text,
        "published_at": published_at,
        "precision": precision,
        "tz": "Africa/Tunis",
        "identifiers": ids or [],
    }
    p.update(kw)
    return p


def urn(value):
    return {"namespace": "linkedin_urn", "value": value}


def count(conn, table):
    return conn.execute(f"SELECT COUNT(*) c FROM {table}").fetchone()["c"]


def test_parse_bounds():
    with pytest.raises(ImpErr) as exc:
        importing.parse_envelope(envelope([post() for _ in range(101)]))
    assert exc.value.code == "BAD_POSTS"
    with pytest.raises(ImpErr) as exc:
        importing.parse_envelope(envelope([post(text="x" * (2 * 1024 * 1024))]))
    assert exc.value.code == "BATCH_TOO_LARGE"
    with pytest.raises(ImpErr) as exc:
        importing.parse_envelope(envelope([post()], source="inconnu"))
    assert exc.value.code == "BAD_SOURCE"
    with pytest.raises(ImpErr) as exc:
        importing.parse_envelope(envelope([post()], policy={"storage": "unknown"}))
    assert exc.value.code == "POLICY_BLOCKED"
    with pytest.raises(ImpErr) as exc:
        importing.parse_envelope(envelope([post()], policy={"storage": "allowed"}))
    assert exc.value.code == "POLICY_BLOCKED"


def test_preview_persists_nothing(conn):
    env = importing.parse_envelope(envelope([post(ids=[urn("urn:li:share:1")])]))
    result = importing.preview(conn, env)
    assert result["plan"]["items"][0]["status"] == "NEW"
    assert count(conn, "history_posts") == 0
    assert result["state"] == "PREVIEWED"


def test_commit_new_full_provenance(conn):
    env = importing.parse_envelope(envelope([post(ids=[urn("urn:li:share:1")], url="https://linkedin.com/posts/1")]))
    batch = importing.preview(conn, env)
    result = importing.commit(conn, batch["batch_id"], None, "owner")
    assert result["imported"] == 1
    row = conn.execute("SELECT * FROM history_posts").fetchone()
    assert row["published_at"] == "2026-11-01T10:00:00+01:00"
    assert row["confirmed_at"] is None
    version = conn.execute("SELECT * FROM history_versions").fetchone()
    assert version["authorship"] == "user"
    source = conn.execute("SELECT * FROM history_sources").fetchone()
    assert source["origin"] == "user_original"
    ident = conn.execute("SELECT * FROM history_identifiers").fetchone()
    assert ident["identifier"] == "urn:li:share:1"


def test_post_policy_blocked(conn):
    env = importing.parse_envelope(envelope([post(policy={"storage": "unknown"})]))
    batch = importing.preview(conn, env)
    assert batch["plan"]["items"][0]["status"] == "POLICY_BLOCKED"
    with pytest.raises(ImpErr) as exc:
        importing.commit(conn, batch["batch_id"], [0], "owner")
    assert exc.value.code == "ITEM_NOT_ACCEPTABLE"
    assert count(conn, "history_posts") == 0


def test_known_by_id_and_null_never_erases(conn):
    env1 = importing.parse_envelope(envelope([post(ids=[urn("urn:li:share:1")])]))
    b1 = importing.preview(conn, env1)
    importing.commit(conn, b1["batch_id"], None, "owner")
    env2 = importing.parse_envelope(
        envelope([post(published_at=None, precision=None, ids=[urn("urn:li:share:1"), urn("urn:li:activity:9")])])
    )
    b2 = importing.preview(conn, env2)
    assert b2["plan"]["items"][0]["status"] == "KNOWN"
    importing.commit(conn, b2["batch_id"], None, "owner")
    assert count(conn, "history_posts") == 1
    assert count(conn, "history_versions") == 1
    assert count(conn, "history_sources") == 2
    assert count(conn, "history_identifiers") == 2
    assert conn.execute("SELECT published_at FROM history_posts").fetchone()["published_at"] is not None


def test_text_changed_keeps_old_version(conn):
    env1 = importing.parse_envelope(envelope([post(ids=[urn("urn:li:share:1")])]))
    importing.commit(conn, importing.preview(conn, env1)["batch_id"], None, "owner")
    env2 = importing.parse_envelope(envelope([post(text="Texte corrigé.", ids=[urn("urn:li:share:1")])]))
    b2 = importing.preview(conn, env2)
    assert b2["plan"]["items"][0]["status"] == "TEXT_CHANGED"
    importing.commit(conn, b2["batch_id"], None, "owner")
    assert conn.execute("SELECT current_version FROM history_posts").fetchone()["current_version"] == 2
    texts = [r["text"] for r in conn.execute("SELECT text FROM history_versions ORDER BY version")]
    assert texts == ["Bonjour LinkedIn.", "Texte corrigé."]


def test_metadata_conflict_not_importable(conn):
    env1 = importing.parse_envelope(envelope([post(ids=[urn("urn:li:share:1")])]))
    importing.commit(conn, importing.preview(conn, env1)["batch_id"], None, "owner")
    env2 = importing.parse_envelope(
        envelope([post(published_at="2026-11-02T10:00:00+01:00", ids=[urn("urn:li:share:1")])])
    )
    b2 = importing.preview(conn, env2)
    assert b2["plan"]["items"][0]["status"] == "METADATA_CONFLICT"
    with pytest.raises(ImpErr):
        importing.commit(conn, b2["batch_id"], [0], "owner")


def test_ambiguous_multiple_candidates(conn):
    env = importing.parse_envelope(
        envelope([post(ids=[urn("urn:li:share:1")]), post(ids=[urn("urn:li:share:2")])])
    )
    importing.commit(conn, importing.preview(conn, env)["batch_id"], None, "owner")
    env2 = importing.parse_envelope(envelope([post()]))
    b2 = importing.preview(conn, env2)
    assert b2["plan"]["items"][0]["status"] == "AMBIGUOUS"


def test_typed_ids_not_assimilated(conn):
    env = importing.parse_envelope(
        envelope([post(ids=[urn("urn:li:share:123")]), post(ids=[urn("urn:li:ugcPost:123")])])
    )
    importing.commit(conn, importing.preview(conn, env)["batch_id"], None, "owner")
    assert count(conn, "history_posts") == 2


def test_idempotent_commit(conn):
    env = importing.parse_envelope(envelope([post(ids=[urn("urn:li:share:1")])]))
    batch = importing.preview(conn, env)
    first = importing.commit(conn, batch["batch_id"], None, "owner")
    again = importing.commit(conn, batch["batch_id"], None, "owner")
    assert again == first
    assert count(conn, "history_posts") == 1
    with pytest.raises(ImpErr) as exc:
        importing.commit(conn, batch["batch_id"], [], "owner")
    assert exc.value.code == "BATCH_ALREADY_COMMITTED"


def test_preview_immutable(conn):
    env = importing.parse_envelope(envelope([post()]))
    first = importing.preview(conn, env)
    second = importing.preview(conn, env)
    assert first["batch_id"] == second["batch_id"]
    assert second["reused"] is True
    assert count(conn, "import_batches") == 1


def test_import_never_resolves_unknown_outcome(conn):
    draft_id, _, final = approved_draft(conn, "Texte incertain.")
    intent = store.consume_final_and_create_intent(conn, final, "owner")
    store.mark_sending(conn, intent)
    store.mark_unknown(conn, intent, "réponse perdue")
    env = importing.parse_envelope(envelope([post(text="Texte incertain.", ids=[urn("urn:li:share:7")])]))
    importing.commit(conn, importing.preview(conn, env)["batch_id"], None, "owner")
    state = conn.execute("SELECT state FROM publication_intents WHERE id = ?", (intent,)).fetchone()["state"]
    assert state == "UNKNOWN_OUTCOME"


def test_duplicate_in_batch_rolls_back(conn):
    env = importing.parse_envelope(envelope([post(), post()]))
    batch = importing.preview(conn, env)
    with pytest.raises(ImpErr) as exc:
        importing.commit(conn, batch["batch_id"], None, "owner")
    assert exc.value.code == "DUPLICATE_IN_BATCH"
    assert count(conn, "history_posts") == 0


def test_stale_batch_requires_new_preview(conn):
    env1 = importing.parse_envelope(envelope([post()]))
    b1 = importing.preview(conn, env1)
    env2 = importing.parse_envelope(envelope([post(ids=[urn("urn:li:share:5")])]))
    importing.commit(conn, importing.preview(conn, env2)["batch_id"], None, "owner")
    with pytest.raises(ImpErr) as exc:
        importing.commit(conn, b1["batch_id"], None, "owner")
    assert exc.value.code == "BATCH_STALE"


def test_reject_all(conn):
    env = importing.parse_envelope(envelope([post()]))
    batch = importing.preview(conn, env)
    result = importing.commit(conn, batch["batch_id"], [], "owner")
    assert result["state"] == "REJECTED"
    assert count(conn, "history_posts") == 0
    assert importing.commit(conn, batch["batch_id"], [], "owner")["state"] == "REJECTED"


def test_fallback_known_by_normalized_text_and_date(conn):
    env1 = importing.parse_envelope(envelope([post(ids=[urn("urn:li:share:1")])]))
    importing.commit(conn, importing.preview(conn, env1)["batch_id"], None, "owner")
    env2 = importing.parse_envelope(envelope([post(text="Bonjour  LinkedIn.\n")]))
    b2 = importing.preview(conn, env2)
    assert b2["plan"]["items"][0]["status"] == "KNOWN"
    importing.commit(conn, b2["batch_id"], None, "owner")
    assert count(conn, "history_posts") == 1


def test_incomplete_statuses(conn):
    env = importing.parse_envelope(envelope([post(text=""), post(published_at="2026-11-01", precision=None)]))
    batch = importing.preview(conn, env)
    assert [i["status"] for i in batch["plan"]["items"]] == ["INCOMPLETE", "INCOMPLETE"]


def test_authorship_and_origin_never_relabeled(conn):
    env = importing.parse_envelope(envelope([post()], source="apify_skill", provider="actor/test"))
    importing.commit(conn, importing.preview(conn, env)["batch_id"], None, "owner")
    assert conn.execute("SELECT authorship FROM history_versions").fetchone()["authorship"] == "external"
    source = conn.execute("SELECT origin, method, provider FROM history_sources").fetchone()
    assert source["origin"] == "apify_skill"
    assert source["provider"] == "actor/test"


def test_query_bounds(conn):
    posts = [post(text=f"Post numéro {i} " + "x" * 100, published_at=f"2026-11-{i + 1:02d}T10:00:00+01:00", ids=[urn(f"urn:li:share:{i}")]) for i in range(10)]
    env = importing.parse_envelope(envelope(posts))
    importing.commit(conn, importing.preview(conn, env)["batch_id"], None, "owner")
    result = history.query(conn, account=ACCOUNT, limit=6, max_chars=12000)
    assert len(result["posts"]) == 6
    assert result["stop"] == "limit"
    assert result["posts"][0]["published_at"] == "2026-11-10T10:00:00+01:00"
    tight = history.query(conn, account=ACCOUNT, limit=6, max_chars=250)
    assert len(tight["posts"]) == 2
    assert tight["stop"] == "char_budget"
    window = history.query(conn, since="2026-11-08T00:00:00+01:00", until="2026-11-09T23:59:59+01:00")
    assert len(window["posts"]) == 2