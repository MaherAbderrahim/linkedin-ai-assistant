"""Parcours image : photo → révision → aperçu → TEXT → IMAGE → FINAL.

Le tampon est en RAM : si l'image disparaît (redémarrage), les validations
d'image et finales doivent être refusées, jamais contournées.
"""

import json

import pytest

from linkedin_assistant import media, store
from linkedin_assistant.conversation import Conversation
from linkedin_assistant.publisher import SimulatedPublisher

from test_phase2 import button_data, cb, last_button, msg


PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n-\xb4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


class FakeClient:
    def __init__(self):
        self.sent = []
        self.photos = []
        self.callbacks = []

    def get_updates(self, offset, timeout):
        return []

    def send_message(self, chat_id, text, reply_markup=None):
        self.sent.append((chat_id, text, reply_markup))
        return {"message_id": len(self.sent)}

    def send_photo(self, chat_id, photo, caption=None, content_type="image/png"):
        self.photos.append((chat_id, photo, caption, content_type))
        return {"message_id": len(self.photos)}

    def answer_callback(self, callback_query_id, text=None):
        self.callbacks.append(callback_query_id)
        return {}


@pytest.fixture()
def client():
    return FakeClient()


@pytest.fixture()
def config(tmp_path):
    from linkedin_assistant.config import Config

    return Config(owner_id=42, chat_id=42, db_path=tmp_path / "x.db", linkedin_account="urn:li:person:test")


@pytest.fixture()
def buffer():
    return media.ImageBuffer()


@pytest.fixture()
def conv(conn, config, client, buffer):
    return Conversation(conn, config, client, SimulatedPublisher(), buffer=buffer)


def attach_image(conv, buffer, client):
    asset = buffer.add(PNG, content_type="image/png", filename="a.png", source="telegram")
    conv.handle(msg("/new", uid=1))
    conv.handle(msg("Texte du post avec image.", uid=2))
    conv._attach_asset(asset)
    return asset


def test_photo_creates_revision_with_image_metadata(conn, conv, buffer, client):
    asset = attach_image(conv, buffer, client)
    row = conn.execute(
        "SELECT v.manifest_json, v.content_hash FROM draft_versions v "
        "JOIN drafts d ON d.id = v.draft_id AND d.current_revision = v.revision"
    ).fetchone()
    manifest = json.loads(row["manifest_json"])
    assert manifest["images"][0]["sha256"] == asset.sha256
    assert manifest["images"][0]["token"] == asset.token
    assert "data" not in manifest["images"][0]


def test_image_changes_content_fingerprint(conn, conv, buffer, client):
    """L'empreinte de contenu inclut l'image : un post avec image ≠ sans image."""

    def current_hash() -> str:
        draft_id = store.get_setting(conn, "active_draft")
        return conn.execute(
            "SELECT v.content_hash FROM draft_versions v JOIN drafts d ON d.id = v.draft_id "
            "AND d.current_revision = v.revision WHERE d.id = ?",
            (draft_id,),
        ).fetchone()["content_hash"]

    attach_image(conv, buffer, client)
    with_image = current_hash()
    conv.handle(msg("/new", uid=10))
    conv.handle(msg("Texte du post avec image.", uid=11))
    without_image = current_hash()
    assert with_image != without_image


def test_preview_sends_photo_and_text_button(conn, conv, buffer, client):
    attach_image(conv, buffer, client)
    client.sent.clear()
    client.photos.clear()
    conv.handle(msg("/preview", uid=3))
    assert len(client.photos) == 1
    assert client.photos[0][1] == PNG
    assert last_button(client) .startswith("text:")


def test_approval_chain_requires_image_approval(conn, conv, buffer, client):
    attach_image(conv, buffer, client)
    conv.handle(msg("/preview", uid=3))
    conv.handle(cb(last_button(client), uid=4))  # texte
    assert last_button(client).startswith("image:")
    conv.handle(cb(last_button(client), uid=5))  # image
    assert last_button(client).startswith("pub:")
    kinds = {r["kind"] for r in conn.execute("SELECT kind FROM approvals")}
    assert {"TEXT", "IMAGE", "FINAL"} <= kinds


def test_publish_with_image_archives_exact_text(conn, conv, buffer, client):
    attach_image(conv, buffer, client)
    conv.handle(msg("/preview", uid=3))
    conv.handle(cb(last_button(client), uid=4))
    conv.handle(cb(last_button(client), uid=5))
    conv.handle(cb(last_button(client), uid=6))
    assert "archivé" in client.sent[-1][1]
    version = conn.execute("SELECT text FROM history_versions").fetchone()
    assert version["text"] == "Texte du post avec image."


def test_image_approval_refused_when_buffer_lost(conn, conv, buffer, client):
    attach_image(conv, buffer, client)
    conv.handle(msg("/preview", uid=3))
    conv.handle(cb(last_button(client), uid=4))  # texte
    buffer.clear()  # redémarrage : les octets sont perdus
    conv.handle(cb(last_button(client), uid=5))  # image
    assert "IMAGE_BUFFER_LOST" in client.sent[-1][1]
    assert conn.execute("SELECT COUNT(*) c FROM publication_intents").fetchone()["c"] == 0


def test_no_image_approval_kind_when_no_image(conn, conv, client):
    conv.handle(msg("/new", uid=1))
    conv.handle(msg("Texte simple.", uid=2))
    conv.handle(msg("/preview", uid=3))
    conv.handle(cb(last_button(client), uid=4))  # texte
    # Un bouton d'ajout d'image est proposé AVANT la validation « sans image ».
    assert button_data(client, "imgadd:") is not None
    conv.handle(cb(button_data(client, "noimg:"), uid=5))
    kinds = {r["kind"] for r in conn.execute("SELECT kind FROM approvals")}
    assert "NO_IMAGE" in kinds
    assert "IMAGE" not in kinds


def test_image_url_command_refuses_private_url(conn, conv, client):
    conv.handle(msg("/new", uid=1))
    conv.handle(msg("/image http://127.0.0.1/x.png", uid=2))
    assert "BLOCKED_URL" in client.sent[-1][1]
    assert len(conv.buffer) == 0


def test_photo_message_attaches_image(conn, conv, buffer, client):
    class PhotoClient(FakeClient):
        def get_file(self, file_id):
            return {"file_path": "photos/file_1.jpg"}

        def download(self, file_path):
            return PNG

    photo_client = PhotoClient()
    conv2 = Conversation(conn, conv.config, photo_client, SimulatedPublisher(), buffer=buffer)
    conv2.handle(
        {
            "update_id": 9,
            "message": {
                "message_id": 9,
                "from": {"id": 42},
                "chat": {"id": 42, "type": "private"},
                "photo": [{"file_id": "abc", "file_unique_id": "u1", "width": 10, "height": 10}],
            },
        }
    )
    assert len(buffer) == 1
    asset = buffer.assets()[0]
    assert asset.source == "telegram"
    assert asset.sha256
