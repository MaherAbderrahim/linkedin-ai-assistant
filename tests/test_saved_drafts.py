"""Brouillons sauvegardés : /drafts liste, bouton Reprendre réactive, publication ensuite.

Les images restent en RAM : un brouillon repris conserve son texte, mais les
octets d'images doivent être rattachés à nouveau avant validation.
"""

import pytest

from linkedin_assistant import media, store
from linkedin_assistant.conversation import Conversation
from linkedin_assistant.config import Config
from linkedin_assistant.publisher import SimulatedPublisher

from test_phase2 import FakeClient, button_data, cb, msg


@pytest.fixture()
def config(tmp_path):
    return Config(owner_id=42, chat_id=42, db_path=tmp_path / "x.db", linkedin_account="urn:li:person:test")


@pytest.fixture()
def conv(conn, config):
    return Conversation(conn, config, FakeClient(), SimulatedPublisher(), buffer=media.ImageBuffer())


def test_drafts_empty(conv):
    conv.handle(msg("/drafts"))
    assert "Aucun brouillon sauvegardé" in conv.client.sent[-1][1]


def test_drafts_lists_saved_drafts(conv, conn):
    conv.handle(msg("/new", uid=1))
    conv.handle(msg("Texte du premier brouillon.", uid=2))
    conv.handle(msg("/new", uid=3))
    conv.handle(msg("Texte du second brouillon.", uid=4))
    conv.handle(msg("/drafts", uid=5))
    text = conv.client.sent[-1][1]
    assert "Texte du second brouillon." in text
    assert "Texte du premier brouillon." in text
    markup = conv.client.sent[-1][2]
    buttons = [b["callback_data"] for row in markup["inline_keyboard"] for b in row]
    assert len(buttons) == 2 and all(b.startswith("resume:") for b in buttons)


def test_drafts_exclude_published(conv, conn):
    from conftest import approved_draft
    from linkedin_assistant.publisher import publish

    draft_id, _, final = approved_draft(conn, "Déjà publié.")
    intent = store.consume_final_and_create_intent(conn, final, "owner")
    publish(conn, intent, SimulatedPublisher(receipt={"urn": "urn:li:share:1"}))
    conv.handle(msg("/drafts"))
    assert "Déjà publié." not in conv.client.sent[-1][1]


def test_resume_sets_active_draft(conn, conv):
    conv.handle(msg("/new", uid=1))
    conv.handle(msg("Brouillon à reprendre.", uid=2))
    first = store.get_setting(conn, "active_draft")
    conv.handle(msg("/new", uid=3))
    conv.handle(msg("Autre brouillon actif.", uid=4))
    conv.handle(cb(f"resume:{first}", uid=5))
    assert store.get_setting(conn, "active_draft") == first
    assert "Brouillon réactivé" in conv.client.sent[-1][1]
    assert "Brouillon à reprendre." in conv.client.sent[-1][1]


def test_resume_reports_ram_images(conn, conv):
    from test_images_flow import PNG

    conv.handle(msg("/new", uid=1))
    conv.handle(msg("Texte avec image.", uid=2))
    draft_id = store.get_setting(conn, "active_draft")
    asset = conv.buffer.add(PNG, content_type="image/png", filename="a.png", source="telegram")
    conv._attach_asset(asset)
    conv.handle(msg("/cancel", uid=3))
    conv.handle(cb(f"resume:{draft_id}", uid=4))
    assert "ne sont plus en RAM" in conv.client.sent[-1][1]


def test_resume_refuses_published(conn, conv):
    from conftest import approved_draft
    from linkedin_assistant.publisher import publish

    draft_id, _, final = approved_draft(conn, "Publié.")
    intent = store.consume_final_and_create_intent(conn, final, "owner")
    publish(conn, intent, SimulatedPublisher(receipt={"urn": "urn:li:share:2"}))
    conv.handle(cb(f"resume:{draft_id}", uid=3))
    assert "déjà publié" in conv.client.sent[-1][1]


def test_resume_unknown_draft(conv):
    conv.handle(cb("resume:inconnu", uid=1))
    assert "introuvable" in conv.client.sent[-1][1]


def test_resumed_draft_publishes_after_validations(conn, conv):
    conv.handle(msg("/new", uid=1))
    conv.handle(msg("Post repris et publié.", uid=2))
    draft_id = store.get_setting(conn, "active_draft")
    conv.handle(msg("/cancel", uid=3))
    conv.handle(cb(f"resume:{draft_id}", uid=4))
    conv.handle(msg("/preview", uid=5))
    conv.handle(cb(button_data(conv.client, "text:"), uid=6))
    revision = conn.execute("SELECT current_revision FROM drafts WHERE id = ?", (draft_id,)).fetchone()[
        "current_revision"
    ]
    assert store.find_valid_approval(conn, draft_id, revision, "TEXT") is not None
