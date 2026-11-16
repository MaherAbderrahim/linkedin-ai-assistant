import io

from linkedin_assistant import db
from linkedin_assistant.config import Config
from linkedin_assistant.local import run_local


def test_local_repl_full_flow(tmp_path):
    config = Config(owner_id=42, chat_id=42, db_path=tmp_path / "local.db")
    conn = db.connect(config.db_path)
    inp = io.StringIO("/new\nMon post local.\n/preview\n1\n2\n1\nquit\n")
    out = io.StringIO()
    run_local(conn, config, inp, out)
    printed = out.getvalue()
    assert "Mon post local." in printed
    assert "archivé" in printed
    assert conn.execute("SELECT COUNT(*) c FROM history_posts").fetchone()["c"] == 1
    assert conn.execute("SELECT text FROM history_versions").fetchone()["text"] == "Mon post local."
    conn.close()


def test_local_repl_free_text_does_not_publish(tmp_path):
    config = Config(owner_id=42, chat_id=42, db_path=tmp_path / "local.db")
    conn = db.connect(config.db_path)
    inp = io.StringIO("Bonjour.\n/preview\nOK\npublie\nquit\n")
    out = io.StringIO()
    run_local(conn, config, inp, out)
    assert conn.execute("SELECT COUNT(*) c FROM publication_intents").fetchone()["c"] == 0
    conn.close()