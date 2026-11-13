import pytest

from linkedin_assistant import app, config as config_mod, inbox, purge, store
from linkedin_assistant.config import Config, ConfigError
from linkedin_assistant.conversation import Conversation
from linkedin_assistant.publisher import SimulatedPublisher
from linkedin_assistant.telegram import escape_html, redact, split_message


class FakeClient:
    def __init__(self, updates=None):
        self.sent = []
        self.callbacks = []
        self.updates = updates or []

    def get_updates(self, offset, timeout):
        return self.updates

    def send_message(self, chat_id, text, reply_markup=None):
        self.sent.append((chat_id, text, reply_markup))
        return {"message_id": len(self.sent)}

    def answer_callback(self, callback_query_id, text=None):
        self.callbacks.append(callback_query_id)
        return {}


def msg(text, user=42, chat=42, chat_type="private", uid=1):
    return {
        "update_id": uid,
        "message": {"message_id": uid, "from": {"id": user}, "chat": {"id": chat, "type": chat_type}, "text": text},
    }


def cb(data, user=42, chat=42, uid=2):
    return {
        "update_id": uid,
        "callback_query": {
            "id": f"cq{uid}",
            "from": {"id": user},
            "message": {"message_id": 1, "chat": {"id": chat, "type": "private"}},
            "data": data,
        },
    }


def last_button(client):
    markup = client.sent[-1][2]
    return markup["inline_keyboard"][0][0]["callback_data"]


@pytest.fixture()
def client():
    return FakeClient()


@pytest.fixture()
def config(tmp_path):
    return Config(owner_id=42, chat_id=42, db_path=tmp_path / "x.db")


@pytest.fixture()
def publisher():
    return SimulatedPublisher()


@pytest.fixture()
def conv(conn, config, client, publisher):
    return Conversation(conn, config, client, publisher)


def drive_to_final(conv, client, text="Mon post exact."):
    conv.handle(msg("/new", uid=1))
    conv.handle(msg(text, uid=2))
    conv.handle(msg("/preview", uid=3))
    conv.handle(cb(last_button(client), uid=4))
    conv.handle(cb(last_button(client), uid=5))
    return last_button(client)


def test_full_flow_simulated_publish(conn, conv, client, publisher):
    pub_button = drive_to_final(conv, client)
    conv.handle(cb(pub_button, uid=6))
    assert "archivé" in client.sent[-1][1]
    assert publisher.calls == 1
    post = conn.execute("SELECT * FROM history_posts").fetchone()
    assert post is not None
    version = conn.execute("SELECT text FROM history_versions").fetchone()
    assert version["text"] == "Mon post exact."
    intent = conn.execute("SELECT state FROM publication_intents").fetchone()
    assert intent["state"] == "PUBLISHED"


def test_free_text_never_publishes(conn, conv, client):
    conv.handle(msg("/new", uid=1))
    conv.handle(msg("Brouillon.", uid=2))
    conv.handle(msg("/preview", uid=3))
    for free in ("OK", "publie", "oui je confirme"):
        conv.handle(msg(free, uid=10))
    assert conn.execute("SELECT COUNT(*) c FROM publication_intents").fetchone()["c"] == 0
    assert conn.execute("SELECT COUNT(*) c FROM history_posts").fetchone()["c"] == 0
    draft = conn.execute("SELECT current_revision FROM drafts").fetchone()
    assert draft["current_revision"] == 4


def test_double_final_button_one_intent(conn, conv, client, publisher):
    pub_button = drive_to_final(conv, client)
    conv.handle(cb(pub_button, uid=6))
    conv.handle(cb(pub_button, uid=7))
    assert "APPROVAL_CONSUMED" in client.sent[-1][1]
    assert conn.execute("SELECT COUNT(*) c FROM publication_intents").fetchone()["c"] == 1
    assert publisher.calls == 1


def test_stale_final_after_new_revision(conn, conv, client):
    pub_button = drive_to_final(conv, client)
    conv.handle(msg("Texte corrigé.", uid=8))
    conv.handle(cb(pub_button, uid=9))
    assert "STALE_REVISION" in client.sent[-1][1]
    assert conn.execute("SELECT COUNT(*) c FROM publication_intents").fetchone()["c"] == 0


def test_text_approval_reused(conn, conv, client):
    conv.handle(msg("/new", uid=1))
    conv.handle(msg("Texte.", uid=2))
    conv.handle(msg("/preview", uid=3))
    button = last_button(client)
    conv.handle(cb(button, uid=4))
    conv.handle(cb(button, uid=5))
    assert conn.execute("SELECT COUNT(*) c FROM approvals WHERE kind = 'TEXT'").fetchone()["c"] == 1


def test_unauthorized_updates_ignored(conv, client):
    conv.handle(msg("/new", user=99, uid=1))
    conv.handle(cb("text:whatever", user=99, uid=2))
    conv.handle(msg("/new", chat=999, uid=3))
    conv.handle(msg("/new", chat_type="group", uid=4))
    assert client.sent == []
    assert client.callbacks == []


def test_expired_final_button(conn, conv, client):
    pub_button = drive_to_final(conv, client)
    approval_id = pub_button[4:]
    conn.execute("UPDATE approvals SET expires_at = '2000-01-01T00:00:00+00:00' WHERE id = ?", (approval_id,))
    conv.handle(cb(pub_button, uid=6))
    assert "APPROVAL_EXPIRED" in client.sent[-1][1]
    assert conn.execute("SELECT COUNT(*) c FROM publication_intents").fetchone()["c"] == 0


def test_split_message_lossless():
    text = "ligne\n" * 2000
    parts = split_message(text)
    assert len(parts) > 1
    assert all(len(p) <= 4096 for p in parts)
    assert "".join(p.split("\n", 1)[1] for p in parts) == text
    long_line = "x" * 10000
    parts = split_message(long_line)
    assert "".join(p.split("\n", 1)[1] for p in parts) == long_line
    assert split_message("court") == ["court"]


def test_escape_html():
    assert escape_html('<b>&"') == '&lt;b&gt;&amp;"'


def test_inbox_dedup_and_offset(conn, client):
    client.updates = [msg("a", uid=10), msg("b", uid=11)]
    assert inbox.poll_once(conn, client, 0) == 2
    assert store.get_setting(conn, "telegram_offset") == "12"
    assert inbox.poll_once(conn, client, 0) == 0
    assert conn.execute("SELECT COUNT(*) c FROM events").fetchone()["c"] == 2


def test_inbox_offset_only_after_persistence(conn, client, monkeypatch):
    client.updates = [msg("a", uid=10), msg("b", uid=11)]
    real = store.ingest_event
    calls = {"n": 0}

    def failing(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("crash simulé avant persistance complète")
        return real(*args, **kwargs)

    monkeypatch.setattr(store, "ingest_event", failing)
    with pytest.raises(RuntimeError):
        inbox.poll_once(conn, client, 0)
    assert store.get_setting(conn, "telegram_offset", "0") == "0"
    assert conn.execute("SELECT COUNT(*) c FROM events").fetchone()["c"] == 0
    monkeypatch.undo()
    assert inbox.poll_once(conn, client, 0) == 2


def test_process_pending_marks_processed(conn, client, conv):
    client.updates = [msg("/status", uid=10)]
    inbox.poll_once(conn, client, 0)
    assert inbox.process_pending(conn, conv.handle) == 1
    assert inbox.process_pending(conn, conv.handle) == 0
    row = conn.execute("SELECT state FROM events").fetchone()
    assert row["state"] == "PROCESSED"


def test_purge_keeps_archive_locks_and_new_events(conn):
    from conftest import approved_draft
    from linkedin_assistant.publisher import publish

    draft_id, _, final = approved_draft(conn, "Post archivé.")
    intent = store.consume_final_and_create_intent(conn, final, "owner")
    publish(conn, intent, SimulatedPublisher())
    conn.execute("UPDATE drafts SET updated_at = '2020-01-01T00:00:00+00:00' WHERE id = ?", (draft_id,))

    locked_id, _, locked_final = approved_draft(conn, "Post verrouillé.")
    store.consume_final_and_create_intent(conn, locked_final, "owner")
    conn.execute("UPDATE drafts SET updated_at = '2020-01-01T00:00:00+00:00' WHERE id = ?", (locked_id,))

    store.ingest_event(conn, "telegram", "1", {})
    store.ingest_event(conn, "telegram", "2", {})
    conn.execute("UPDATE events SET created_at = '2020-01-01T00:00:00+00:00', state = 'PROCESSED' WHERE external_id = '1'")
    conn.execute("UPDATE events SET created_at = '2020-01-01T00:00:00+00:00' WHERE external_id = '2'")

    counts = purge.purge(conn, now="2026-11-13T00:00:00+00:00")
    assert counts["drafts"] == 1
    assert counts["events"] == 1
    assert conn.execute("SELECT COUNT(*) c FROM history_posts").fetchone()["c"] == 1
    assert conn.execute("SELECT COUNT(*) c FROM history_versions").fetchone()["c"] == 1
    assert conn.execute("SELECT id FROM drafts").fetchall()[0]["id"] == locked_id
    assert conn.execute("SELECT external_id FROM events").fetchall()[0]["external_id"] == "2"


def test_config_validation(tmp_path, monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    path = tmp_path / "config.toml"
    path.write_text("owner_id = 42\nchat_id = 42\n", encoding="utf-8")
    cfg = config_mod.load(path)
    assert cfg.simulation is True
    assert cfg.timezone == "Africa/Tunis"
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    assert config_mod.load(path).telegram_token == "tok"
    for bad in ('owner_id = "42"\nchat_id = 42\n', "owner_id = true\nchat_id = 42\n", "owner_id = -1\nchat_id = 42\n"):
        path.write_text(bad, encoding="utf-8")
        with pytest.raises(ConfigError):
            config_mod.load(path)
    with pytest.raises(ConfigError):
        config_mod.load(tmp_path / "absent.toml")


def test_redact_token():
    assert "123:ABC" not in redact("https://api.telegram.org/bot123:ABC/getUpdates failed", "123:ABC")


def test_app_simulation_exits_without_network(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    path = tmp_path / "config.toml"
    path.write_text("owner_id = 42\nchat_id = 42\n", encoding="utf-8")
    assert app.main(["--config", str(path)]) == 0
    assert "simulation" in capsys.readouterr().out.lower()
    assert (tmp_path / "data" / "assistant.db").exists()