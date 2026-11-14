"""Chantier 3 : paramètres progressifs partagés (Telegram + dashboard, même SQLite)."""

import pytest

from linkedin_assistant import prefs, reminders, store
from linkedin_assistant.conversation import Conversation
from linkedin_assistant.config import Config
from linkedin_assistant.publisher import SimulatedPublisher
from linkedin_assistant.prefs import PreferencesError

from test_phase2 import FakeClient, msg


def test_spec_covers_expected_keys():
    keys = {entry.key for entry in prefs.spec()}
    assert keys >= {
        "editorial_topics", "editorial_tone", "editorial_audience", "editorial_length",
        "editorial_language", "search_provider", "search_max_queries", "search_max_pages",
        "images_enabled", "image_provider", "llm_provider", "llm_model",
        "reminders_enabled", "reminder_hour", "reminder_days", "inactivity_hours",
    }


def test_int_bounds_fail_closed(conn):
    prefs.set_value(conn, "reminder_hour", "7")
    assert prefs.get(conn, "reminder_hour") == "7"
    with pytest.raises(PreferencesError) as exc:
        prefs.set_value(conn, "reminder_hour", "24")
    assert exc.value.code == "INVALID_VALUE"
    with pytest.raises(PreferencesError):
        prefs.set_value(conn, "editorial_length", "abc")
    with pytest.raises(PreferencesError):
        prefs.set_value(conn, "search_max_queries", "4")  # borne haute 3


def test_text_cap_and_choice(conn):
    prefs.set_value(conn, "editorial_audience", "Étudiants ingénieurs")
    assert prefs.get(conn, "editorial_audience") == "Étudiants ingénieurs"
    with pytest.raises(PreferencesError):
        prefs.set_value(conn, "editorial_audience", "x" * 201)
    assert prefs.set_value(conn, "editorial_tone", "Expert") == "expert"
    with pytest.raises(PreferencesError):
        prefs.set_value(conn, "editorial_tone", "agressif")


def test_bool_normalization(conn):
    assert prefs.set_value(conn, "images_enabled", "oui") == "1"
    assert prefs.set_value(conn, "images_enabled", "OFF") == "0"
    with pytest.raises(PreferencesError):
        prefs.set_value(conn, "images_enabled", "peut-être")


def test_list_parsing_and_caps(conn):
    assert prefs.set_value(conn, "editorial_topics", " IA , PFE,,tunisie ") == "IA, PFE, tunisie"
    with pytest.raises(PreferencesError):
        prefs.set_value(conn, "editorial_topics", ",".join(f"t{i}" for i in range(21)))


def test_days_normalized_and_bounded(conn):
    assert prefs.set_value(conn, "reminder_days", "6,0,0") == "0,6"
    with pytest.raises(PreferencesError):
        prefs.set_value(conn, "reminder_days", "7")
    with pytest.raises(PreferencesError):
        prefs.set_value(conn, "reminder_days", "")


def test_unknown_key_fails_closed(conn):
    with pytest.raises(PreferencesError) as exc:
        prefs.set_value(conn, "secret_key", "x")
    assert exc.value.code == "UNKNOWN_KEY"
    with pytest.raises(PreferencesError):
        prefs.get(conn, "secret_key")


def test_reminders_read_the_same_keys(conn):
    prefs.set_value(conn, "reminder_hour", "8")
    prefs.set_value(conn, "reminder_days", "0,2")
    prefs.set_value(conn, "inactivity_hours", "200")
    settings = reminders._settings(conn)
    assert settings["hour"] == 8
    assert settings["days"] == {0, 2}
    assert settings["inactivity_hours"] == 200


def test_display_and_show(conn):
    text = prefs.display(conn)
    assert "non défini" in text and "llm_model" in text
    prefs.set_value(conn, "editorial_tone", "direct")
    assert "direct" in prefs.show(conn, "editorial_tone")
    with pytest.raises(PreferencesError):
        prefs.show(conn, "inconnu")


@pytest.fixture()
def conv(conn, tmp_path):
    config = Config(owner_id=42, chat_id=42, db_path=tmp_path / "c.db")
    return Conversation(conn, config, FakeClient(), SimulatedPublisher())


def test_conversation_settings_command(conn, conv):
    client = conv.client
    conv.handle(msg("/settings", uid=1))
    assert "Paramètres progressifs" in client.sent[-1][1]
    conv.handle(msg("/settings editorial_tone expert", uid=2))
    assert "Réglage enregistré" in client.sent[-1][1]
    assert prefs.get(conn, "editorial_tone") == "expert"
    conv.handle(msg("/settings editorial_tone", uid=3))
    assert "expert" in client.sent[-1][1]
    conv.handle(msg("/settings editorial_tone agressif", uid=4))
    assert "Réglage refusé" in client.sent[-1][1]
    conv.handle(msg("/settings cle_inexistante valeur", uid=5))
    assert "UNKNOWN_KEY" in client.sent[-1][1]


def test_settings_are_shared_single_source(conn, conv):
    conv.handle(msg("/settings reminder_hour 6", uid=1))
    assert store.get_setting(conn, "reminder_hour") == "6"
    assert reminders._settings(conn)["hour"] == 6
