"""Phase 1 (volet B) : secrets `.env` au démarrage, rappel 10 h, contrat Publisher."""

import os

import pytest

from linkedin_assistant import publisher, reminders, store
from linkedin_assistant.config import load
from linkedin_assistant.envfile import EnvFileError, load_env, missing_names

from conftest import approved_draft

ENV_NAMES = ("TELEGRAM_BOT_TOKEN", "GROQ_API_KEY", "OPENROUTER_API_KEY", "TAVILY_API_KEY")


def _clear_env(monkeypatch):
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


# --- Chantier 1 : fichier .env, validation par nom sans contenu ---


def test_env_parses_quotes_comments_export(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    path = tmp_path / ".env"
    path.write_text(
        "# commentaire\n\nGROQ_API_KEY=abc-123\nOPENROUTER_API_KEY=\"deux mots\"\nexport TAVILY_API_KEY='trois'\n",
        encoding="utf-8",
    )
    loaded = load_env(path)
    assert loaded["GROQ_API_KEY"] == "abc-123"
    assert loaded["OPENROUTER_API_KEY"] == "deux mots"
    assert loaded["TAVILY_API_KEY"] == "trois"
    assert os.environ["GROQ_API_KEY"] == "abc-123"


def test_env_missing_file_is_optional(tmp_path):
    assert load_env(tmp_path / "absent.env") == {}


def test_env_malformed_fails_closed_without_leaking(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    path = tmp_path / ".env"
    path.write_text("GROQ_API_KEY=ok-1\nCECI_N_EST_PAS_UNE_VARIABLE sk-secret-valeur\n", encoding="utf-8")
    with pytest.raises(EnvFileError) as exc:
        load_env(path)
    message = str(exc.value)
    assert "ligne 2" in message
    assert "sk-secret-valeur" not in message
    # Tout-ou-rien : la ligne valide n'a pas été appliquée.
    assert os.environ.get("GROQ_API_KEY") is None


def test_env_never_overrides_existing(monkeypatch, tmp_path):
    monkeypatch.setenv("GROQ_API_KEY", "depuis-shell")
    path = tmp_path / ".env"
    path.write_text("GROQ_API_KEY=depuis-fichier\n", encoding="utf-8")
    load_env(path)
    assert os.environ["GROQ_API_KEY"] == "depuis-shell"
    load_env(path, override=True)
    assert os.environ["GROQ_API_KEY"] == "depuis-fichier"


def test_missing_names_reports_names_only(monkeypatch):
    _clear_env(monkeypatch)
    assert missing_names(environ={}) == list(ENV_NAMES)


def test_missing_names_counts_blank_value():
    assert "GROQ_API_KEY" in missing_names(environ={"GROQ_API_KEY": "   "})


def test_config_loads_env_file_and_reports_missing(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    config_path = tmp_path / "config.toml"
    config_path.write_text('owner_id = 42\nchat_id = 42\ndb_path = "test.db"\n', encoding="utf-8")
    (tmp_path / ".env").write_text("GROQ_API_KEY=cle-fichier\n", encoding="utf-8")
    config = load(config_path)
    assert os.environ["GROQ_API_KEY"] == "cle-fichier"
    assert "OPENROUTER_API_KEY" in config.missing_env
    assert "GROQ_API_KEY" not in config.missing_env
    assert config.simulation is True  # TELEGRAM_BOT_TOKEN absent


def test_config_custom_env_file_name(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    config_path = tmp_path / "config.toml"
    config_path.write_text('owner_id = 1\nchat_id = 2\nenv_file = "secrets.env"\n', encoding="utf-8")
    (tmp_path / "secrets.env").write_text("OPENROUTER_API_KEY=cle-dediee\n", encoding="utf-8")
    config = load(config_path)
    assert os.environ["OPENROUTER_API_KEY"] == "cle-dediee"
    assert config.env_file == tmp_path / "secrets.env"


def test_config_without_env_file_still_loads(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    config_path = tmp_path / "config.toml"
    config_path.write_text("owner_id = 1\nchat_id = 2\n", encoding="utf-8")
    config = load(config_path)
    assert config.missing_env == ENV_NAMES
    assert config.simulation is True


# --- Chantier 2 : rappel quotidien 10 h ---


def test_default_reminder_hour_is_10(conn):
    assert reminders.DEFAULT_HOUR == 10
    assert reminders._settings(conn)["hour"] == 10


def test_reminder_fires_at_10h_not_before(conn):
    reminders.set_enabled(conn, True)
    assert reminders.due(conn, "2026-11-13T08:59:00+00:00")["reasons"] == ["before_hour"]
    decision = reminders.due(conn, "2026-11-13T09:00:00+00:00")  # 10:00 Africa/Tunis
    assert decision["send"] is True


# --- Chantier 5 : contrat Publisher formalisé ---


def test_simulated_publisher_satisfies_contract():
    assert isinstance(publisher.SimulatedPublisher(), publisher.Publisher)


def test_resolve_treg_connection_finds_single_healthy():
    connections = [
        {"tool": "linkedin", "provider": "linkedin", "health": "invalid"},
        {"tool": "linkedin-2", "provider": "linkedin", "health": "ok"},
    ]
    assert publisher.resolve_treg_connection(connections) == "linkedin-2"


def test_resolve_treg_connection_accepts_name_and_status_keys():
    assert publisher.resolve_treg_connection([{"name": "linkedin-9", "provider": "LinkedIn", "status": "OK"}]) == "linkedin-9"


def test_resolve_treg_connection_missing_fails_closed():
    with pytest.raises(publisher.PublisherError) as exc:
        publisher.resolve_treg_connection([{"tool": "linkedin", "provider": "linkedin", "health": "invalid"}])
    assert "MISSING" in str(exc.value)
    with pytest.raises(publisher.PublisherError):
        publisher.resolve_treg_connection([])


def test_resolve_treg_connection_ambiguous_fails_closed():
    healthy = [
        {"tool": "linkedin-a", "provider": "linkedin", "health": "ok"},
        {"tool": "linkedin-b", "provider": "linkedin", "health": "ok"},
    ]
    with pytest.raises(publisher.PublisherError) as exc:
        publisher.resolve_treg_connection(healthy)
    assert "AMBIGUOUS" in str(exc.value)


def test_resolve_treg_connection_ignores_other_providers():
    with pytest.raises(publisher.PublisherError):
        publisher.resolve_treg_connection([{"tool": "github", "provider": "github", "health": "ok"}])


def test_publish_rejects_non_dict_receipt(conn):
    _, _, final = approved_draft(conn)
    intent = store.consume_final_and_create_intent(conn, final, "owner")

    class BadAdapter(publisher.Publisher):
        calls = 0

        def post(self, manifest):
            BadAdapter.calls += 1
            return "urn:li:share:pas-un-dict"  # violation du contrat

    assert publisher.publish(conn, intent, BadAdapter()) == "UNKNOWN_OUTCOME"
    assert BadAdapter.calls == 1
    row = conn.execute("SELECT state FROM publication_intents").fetchone()
    assert row["state"] == "UNKNOWN_OUTCOME"
    assert conn.execute("SELECT COUNT(*) c FROM history_posts").fetchone()["c"] == 0
