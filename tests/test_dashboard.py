"""Chantier 6 : squelette du tableau de bord local (127.0.0.1, même SQLite)."""

import threading
import urllib.request

import pytest

from linkedin_assistant import dashboard, store
from linkedin_assistant.config import Config
from linkedin_assistant.db import connect

MISSING = ("TELEGRAM_BOT_TOKEN", "GROQ_API_KEY")


def make(tmp_path):
    config = Config(owner_id=42, chat_id=42, db_path=tmp_path / "dash.db")
    conn = connect(config.db_path)
    return config, conn


def test_index_links_sections(tmp_path):
    config, conn = make(tmp_path)
    try:
        code, page = dashboard.render(conn, "/")
        assert code == 200
        assert "Configuration générale" in page and "État système" in page
        assert "ne jamais exposer publiquement" in page
    finally:
        conn.close()


def test_config_page_lists_registry(tmp_path):
    config, conn = make(tmp_path)
    try:
        code, page = dashboard.render(conn, "/config")
        assert code == 200
        for key in ("editorial_tone", "llm_model", "reminder_hour"):
            assert key in page
        assert "non défini" in page
    finally:
        conn.close()


def test_config_post_sets_and_renders_value(tmp_path):
    config, conn = make(tmp_path)
    try:
        code, page = dashboard.render(conn, "/config", "POST", {"key": ["editorial_tone"], "value": ["expert"]})
        assert code == 200 and "Réglage enregistré" in page
        assert store.get_setting(conn, "editorial_tone") == "expert"
        _, page = dashboard.render(conn, "/config")
        assert "expert" in page
    finally:
        conn.close()


def test_config_post_invalid_and_unknown_fail_closed(tmp_path):
    config, conn = make(tmp_path)
    try:
        code, page = dashboard.render(conn, "/config", "POST", {"key": ["editorial_tone"], "value": ["agressif"]})
        assert code == 400 and "Réglage refusé" in page
        assert store.get_setting(conn, "editorial_tone") is None
        code, page = dashboard.render(conn, "/config", "POST", {"key": ["inconnu"], "value": ["x"]})
        assert code == 400 and "UNKNOWN_KEY" in page
    finally:
        conn.close()


def test_config_values_are_escaped(tmp_path):
    config, conn = make(tmp_path)
    try:
        dashboard.render(conn, "/config", "POST", {"key": ["editorial_audience"], "value": ["<script>x</script>"]})
        _, page = dashboard.render(conn, "/config")
        assert "<script>" not in page
        assert "&lt;script&gt;" in page
    finally:
        conn.close()


def test_state_page_reports_system(tmp_path):
    config, conn = make(tmp_path)
    try:
        store.create_draft(conn)
        code, page = dashboard.render(conn, "/state", missing_env=MISSING)
        assert code == 200
        assert "Africa/Tunis" in page
        assert "TELEGRAM_BOT_TOKEN, GROQ_API_KEY" in page
        assert "Archive : 0" in page
        assert "aucune publication possible depuis ce tableau de bord" in page
    finally:
        conn.close()


def test_unknown_path_and_bad_method(tmp_path):
    config, conn = make(tmp_path)
    try:
        assert dashboard.render(conn, "/nope")[0] == 404
        assert dashboard.render(conn, "/state", "POST")[0] == 405
        assert dashboard.render(conn, "/config", "DELETE")[0] == 405
    finally:
        conn.close()


def test_server_serves_loopback(tmp_path):
    config, conn = make(tmp_path)
    conn.close()
    server = dashboard.make_server(config, missing_env=MISSING, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/state"
        with urllib.request.urlopen(url, timeout=5) as response:
            body = response.read().decode("utf-8")
            assert response.status == 200
            assert "État système" in body
            assert "TELEGRAM_BOT_TOKEN, GROQ_API_KEY" in body
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
