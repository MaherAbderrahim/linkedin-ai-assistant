import pytest

from linkedin_assistant import db, store

ACCOUNT = "urn:li:person:test"


@pytest.fixture()
def conn(tmp_path):
    connection = db.connect(tmp_path / "test.sqlite")
    yield connection
    connection.close()


def make_manifest(text: str, account: str = ACCOUNT, visibility: str = "PUBLIC", image=None) -> dict:
    return {"account": account, "visibility": visibility, "text": text, "image": image}


def approved_draft(conn, text: str = "Bonjour LinkedIn.", account: str = ACCOUNT, image=None):
    draft_id = store.create_draft(conn)
    revision = store.add_revision(conn, draft_id, text, make_manifest(text, account, image=image))
    store.record_approval(conn, draft_id, revision, "TEXT", "owner")
    store.record_approval(conn, draft_id, revision, "IMAGE" if image else "NO_IMAGE", "owner")
    final = store.record_approval(conn, draft_id, revision, "FINAL", "owner")
    return draft_id, revision, final
