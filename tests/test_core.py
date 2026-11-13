import pytest

from linkedin_assistant import store
from linkedin_assistant.hashing import content_fingerprint, normalize_for_comparison
from linkedin_assistant.publisher import SimulatedPublisher, publish
from conftest import ACCOUNT, approved_draft, make_manifest


def test_stale_revision_approval_rejected(conn):
    draft_id, rev1, final = approved_draft(conn)
    store.add_revision(conn, draft_id, "Texte corrigé.", make_manifest("Texte corrigé."))
    with pytest.raises(store.StoreError) as exc:
        store.consume_final_and_create_intent(conn, final, "owner")
    assert exc.value.code == "STALE_REVISION"


def test_final_requires_text_and_media_approval(conn):
    draft_id = store.create_draft(conn)
    rev = store.add_revision(conn, draft_id, "Texte.", make_manifest("Texte."))
    with pytest.raises(store.StoreError) as exc:
        store.record_approval(conn, draft_id, rev, "FINAL", "owner")
    assert exc.value.code == "CONTENT_NOT_APPROVED"


def test_double_consumption_rejected(conn):
    _, _, final = approved_draft(conn)
    store.consume_final_and_create_intent(conn, final, "owner")
    with pytest.raises(store.StoreError) as exc:
        store.consume_final_and_create_intent(conn, final, "owner")
    assert exc.value.code == "APPROVAL_CONSUMED"


def test_two_final_buttons_one_intent(conn):
    draft_id, rev, _ = approved_draft(conn)
    second = store.record_approval(conn, draft_id, rev, "FINAL", "owner")
    store.consume_final_and_create_intent(conn, second, "owner")
    first = conn.execute(
        "SELECT id FROM approvals WHERE draft_id = ? AND kind = 'FINAL' AND id != ?", (draft_id, second)
    ).fetchone()["id"]
    with pytest.raises(store.StoreError) as exc:
        store.consume_final_and_create_intent(conn, first, "owner")
    assert exc.value.code == "ACCOUNT_LOCKED"
    assert conn.execute("SELECT COUNT(*) c FROM publication_intents").fetchone()["c"] == 1


def test_expired_approval_rejected(conn):
    draft_id, rev, _ = approved_draft(conn)
    expired = store.record_approval(
        conn, draft_id, rev, "FINAL", "owner", now="2026-11-13T10:00:00+00:00", expires_at="2026-11-13T10:10:00+00:00"
    )
    with pytest.raises(store.StoreError) as exc:
        store.consume_final_and_create_intent(conn, expired, "owner", now="2026-11-13T10:11:00+00:00")
    assert exc.value.code == "APPROVAL_EXPIRED"


def test_actor_mismatch_rejected(conn):
    _, _, final = approved_draft(conn)
    with pytest.raises(store.StoreError) as exc:
        store.consume_final_and_create_intent(conn, final, "intrus")
    assert exc.value.code == "ACTOR_MISMATCH"


def test_duplicate_content_across_drafts(conn):
    _, _, final1 = approved_draft(conn, "Même texte.")
    intent1 = store.consume_final_and_create_intent(conn, final1, "owner")
    publish(conn, intent1, SimulatedPublisher())
    _, _, final2 = approved_draft(conn, "Même texte.")
    with pytest.raises(store.StoreError) as exc:
        store.consume_final_and_create_intent(conn, final2, "owner")
    assert exc.value.code == "DUPLICATE_CONTENT"


def test_success_archives_exact_text_atomically(conn):
    text = "Texte exact avec accents éàù et\nretours."
    _, _, final = approved_draft(conn, text)
    intent = store.consume_final_and_create_intent(conn, final, "owner")
    receipt = {"urn": "urn:li:share:123", "published_at": "2026-11-13T09:00:00Z", "published_at_precision": "second", "published_at_tz": "UTC"}
    assert publish(conn, intent, SimulatedPublisher(receipt=receipt)) == "PUBLISHED"
    post = conn.execute("SELECT * FROM history_posts").fetchone()
    version = conn.execute("SELECT * FROM history_versions").fetchone()
    assert version["text"] == text
    assert version["authorship"] == "assistant"
    assert post["published_at"] == "2026-11-13T09:00:00Z"
    assert post["confirmed_at"] is not None
    identifier = conn.execute("SELECT * FROM history_identifiers").fetchone()
    assert identifier["identifier"] == "urn:li:share:123"
    source = conn.execute("SELECT * FROM history_sources").fetchone()
    assert source["origin"] == "assistant_published"
    intent_row = conn.execute("SELECT * FROM publication_intents WHERE id = ?", (intent,)).fetchone()
    assert intent_row["state"] == "PUBLISHED"
    assert intent_row["history_post_id"] == post["id"]


def test_missing_receipt_fields_stay_null(conn):
    _, _, final = approved_draft(conn)
    intent = store.consume_final_and_create_intent(conn, final, "owner")
    publish(conn, intent, SimulatedPublisher(receipt={}))
    post = conn.execute("SELECT * FROM history_posts").fetchone()
    assert post["published_at"] is None
    assert post["confirmed_at"] is not None
    assert conn.execute("SELECT COUNT(*) c FROM history_identifiers").fetchone()["c"] == 0


def test_ambiguous_outcome_locks_account_without_retry(conn):
    _, _, final = approved_draft(conn)
    intent = store.consume_final_and_create_intent(conn, final, "owner")
    adapter = SimulatedPublisher(outcome="ambiguous")
    assert publish(conn, intent, adapter) == "UNKNOWN_OUTCOME"
    assert adapter.calls == 1
    with pytest.raises(store.StoreError):
        publish(conn, intent, adapter)
    assert adapter.calls == 1
    _, _, final2 = approved_draft(conn, "Autre texte.")
    with pytest.raises(store.StoreError) as exc:
        store.consume_final_and_create_intent(conn, final2, "owner")
    assert exc.value.code == "ACCOUNT_LOCKED"
    assert conn.execute("SELECT COUNT(*) c FROM history_posts").fetchone()["c"] == 0


def test_certain_failure_then_new_authorization(conn):
    _, _, final = approved_draft(conn)
    intent = store.consume_final_and_create_intent(conn, final, "owner")
    assert publish(conn, intent, SimulatedPublisher(outcome="certain_failure")) == "FAILED"
    draft_id = conn.execute("SELECT draft_id FROM publication_intents WHERE id = ?", (intent,)).fetchone()["draft_id"]
    rev = store.add_revision(conn, draft_id, "Texte corrigé après refus.", make_manifest("Texte corrigé après refus."))
    store.record_approval(conn, draft_id, rev, "TEXT", "owner")
    store.record_approval(conn, draft_id, rev, "NO_IMAGE", "owner")
    final2 = store.record_approval(conn, draft_id, rev, "FINAL", "owner")
    intent2 = store.consume_final_and_create_intent(conn, final2, "owner")
    assert publish(conn, intent2, SimulatedPublisher()) == "PUBLISHED"


def test_success_requires_sending_state(conn):
    _, _, final = approved_draft(conn)
    intent = store.consume_final_and_create_intent(conn, final, "owner")
    with pytest.raises(store.StoreError) as exc:
        store.record_success(conn, intent, {"urn": "urn:li:share:x"})
    assert exc.value.code == "INVALID_STATE"


def test_event_ingest_deduplicated(conn):
    assert store.ingest_event(conn, "telegram", "42", {"text": "idée"}) is True
    assert store.ingest_event(conn, "telegram", "42", {"text": "idée"}) is False
    assert conn.execute("SELECT COUNT(*) c FROM events").fetchone()["c"] == 1


def test_fingerprint_excludes_internal_ids():
    manifest = make_manifest("Texte identique.")
    assert content_fingerprint(manifest) == content_fingerprint(dict(manifest))
    changed = dict(manifest, text="Texte différent.")
    assert content_fingerprint(manifest) != content_fingerprint(changed)


def test_normalization_is_conservative():
    assert normalize_for_comparison("  Bonjour\r\nle  monde  ") == "Bonjour\nle monde"
    assert normalize_for_comparison("Post 1: https://exemple.fr/a,b!") != normalize_for_comparison("Post 2: https://exemple.fr/a,b!")
    assert normalize_for_comparison("café") == normalize_for_comparison("café")
