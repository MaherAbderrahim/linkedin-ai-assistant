import pytest

from linkedin_assistant import reminders, store
from linkedin_assistant.config import Config
from linkedin_assistant.conversation import Conversation
from linkedin_assistant.publisher import SimulatedPublisher

from conftest import ACCOUNT
from test_phase2 import FakeClient, msg

NOW = "2026-11-13T09:00:00+00:00"  # 10:00 Africa/Tunis, vendredi (défaut rappel 10 h)


def declare(conn, at, precision="second", confirmed=None):
    post_id = store.new_id()
    now = store.utcnow()
    conn.execute(
        "INSERT INTO history_posts (id, account, current_version, published_at, published_at_precision, confirmed_at, created_at, updated_at) "
        "VALUES (?, ?, 1, ?, ?, ?, ?, ?)",
        (post_id, ACCOUNT, at, precision, confirmed, now, now),
    )
    conn.execute(
        "INSERT INTO history_versions (id, post_id, version, text, exact_hash, normalized_hash, norm_version, authorship, observed_at) "
        "VALUES (?, ?, 1, '', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'nfc-ws-v1', 'user', ?)",
        (store.new_id(), post_id, now),
    )
    return post_id


@pytest.fixture()
def client():
    return FakeClient()


@pytest.fixture()
def conv(conn, tmp_path, client):
    config = Config(owner_id=42, chat_id=42, db_path=tmp_path / "r.db")
    return Conversation(conn, config, client, SimulatedPublisher())


def test_disabled(conn):
    decision = reminders.due(conn, NOW)
    assert decision["send"] is False
    assert decision["reasons"] == ["disabled"]


def test_before_hour(conn):
    reminders.set_enabled(conn, True)
    decision = reminders.due(conn, "2026-11-13T07:00:00+00:00")
    assert decision["reasons"] == ["before_hour"]


def test_wrong_day(conn):
    reminders.set_enabled(conn, True)
    store.set_setting(conn, "reminder_days", "0")
    assert reminders.due(conn, NOW)["reasons"] == ["wrong_day"]


def test_inactivity_once_per_day(conn, client):
    reminders.set_enabled(conn, True)
    declare(conn, "2026-11-01T08:00:00+00:00")
    decision = reminders.due(conn, NOW)
    assert decision["send"] is True
    assert "inactivity" in decision["reasons"]
    reminders.tick(conn, client, 42, NOW)
    assert len(client.sent) == 1
    reminders.tick(conn, client, 42, NOW)
    assert len(client.sent) == 1
    reminders.tick(conn, client, 42, "2026-11-14T09:00:00+00:00")
    assert len(client.sent) == 2


def test_recent_publication_no_reminder(conn):
    reminders.set_enabled(conn, True)
    declare(conn, "2026-11-13T07:00:00+00:00")
    assert reminders.due(conn, NOW)["send"] is False


def test_date_missing(conn):
    reminders.set_enabled(conn, True)
    decision = reminders.due(conn, NOW)
    assert decision["send"] is True
    assert decision["reasons"] == ["date_missing"]
    assert decision["basis"] is None


def test_future_date(conn):
    reminders.set_enabled(conn, True)
    declare(conn, "2026-11-20T08:00:00+00:00")
    assert "future_date" in reminders.due(conn, NOW)["reasons"]


def test_approximate_precision(conn):
    reminders.set_enabled(conn, True)
    declare(conn, "2026-11-01", precision="day")
    assert "approximate_date" in reminders.due(conn, NOW)["reasons"]


def test_confirmed_at_only_approximation(conn):
    reminders.set_enabled(conn, True)
    declare(conn, None, confirmed="2026-11-01T08:00:00+00:00")
    decision = reminders.due(conn, NOW)
    assert decision["basis"] == "confirmed_at_approx"
    assert "approximate_confirmed_at" in decision["reasons"]
    assert "inactivity" in decision["reasons"]


def test_created_at_never_used(conn):
    reminders.set_enabled(conn, True)
    declare(conn, None, confirmed=None)
    decision = reminders.due(conn, NOW)
    assert decision["reasons"] == ["date_missing"]
    assert decision["basis"] is None


def test_resume_without_burst(conn, client):
    reminders.set_enabled(conn, True)
    declare(conn, "2026-11-01T08:00:00+00:00")
    for day in range(13, 18):
        now = f"2026-11-{day:02d}T09:00:00+00:00"
        reminders.tick(conn, client, 42, now)
        reminders.tick(conn, client, 42, now)
    assert len(client.sent) == 5


def test_reminders_never_publish(conn, client):
    reminders.set_enabled(conn, True)
    declare(conn, "2026-11-01T08:00:00+00:00")
    reminders.tick(conn, client, 42, NOW)
    assert conn.execute("SELECT COUNT(*) c FROM publication_intents").fetchone()["c"] == 0


def test_lastpost_command(conn, conv, client):
    conv.handle(msg("/lastpost 2026-11-10T09:00:00+01:00", uid=1))
    row = conn.execute("SELECT published_at, published_at_precision FROM history_posts").fetchone()
    assert row["published_at"] == "2026-11-10T09:00:00+01:00"
    assert row["published_at_precision"] == "second"
    source = conn.execute("SELECT origin, method FROM history_sources").fetchone()
    assert source["origin"] == "user_declared"
    assert "déclarée" in client.sent[-1][1]
    conv.handle(msg("/lastpost 2027-01-01T00:00:00+01:00", uid=2))
    assert "future" in client.sent[-1][1]
    conv.handle(msg("/lastpost pas-une-date", uid=3))
    assert "invalide" in client.sent[-1][1]
    conv.handle(msg("/lastpost 2026-11-10T09:00:00", uid=4))
    assert "décalage" in client.sent[-1][1]
    conv.handle(msg("/lastpost 2026-11-09", uid=5))
    assert conn.execute("SELECT COUNT(*) c FROM history_posts").fetchone()["c"] == 2
    row = conn.execute("SELECT published_at_precision FROM history_posts WHERE published_at = '2026-11-09'").fetchone()
    assert row["published_at_precision"] == "day"


def test_reminder_toggle(conn, conv, client):
    conv.handle(msg("/reminder on", uid=1))
    assert store.get_setting(conn, "reminders_enabled") == "1"
    conv.handle(msg("/reminder", uid=2))
    assert "activés" in client.sent[-1][1]
    conv.handle(msg("/reminder off", uid=3))
    assert store.get_setting(conn, "reminders_enabled") == "0"