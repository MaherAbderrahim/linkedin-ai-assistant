from __future__ import annotations

import html
import http.server
import sqlite3
import urllib.parse
from datetime import datetime
from zoneinfo import ZoneInfo

from . import prefs, store
from .config import Config
from .db import connect

# Tableau de bord local (ADR-14) : serveur HTTP stdlib lié à 127.0.0.1.
# - Même SQLite que Telegram : lecture/écriture des paramètres via le même
#   registre `prefs` (mêmes validations déterministes).
# - AUCUN second chemin de publication : rien ici ne publie, ne consomme
#   d'approbation et ne touche aux intents.
# - Jamais exposé publiquement sans authentification et protection des secrets ;
#   aucune clé/jeton n'est affiché, même manquant (noms seuls).

TZ = ZoneInfo("Africa/Tunis")

_PAGE = """<!doctype html>
<html lang="fr">
<head><meta charset="utf-8"><title>Assistant LinkedIn — {title}</title></head>
<body>
<h1>Assistant LinkedIn — tableau de bord local</h1>
<nav><a href="/">Accueil</a> · <a href="/config">Configuration générale</a> · <a href="/state">État système</a></nav>
{body}
<p><em>Lié à 127.0.0.1 — ne jamais exposer publiquement sans authentification.
Aucune publication depuis ce tableau de bord.</em></p>
</body></html>"""


def _esc(text: str) -> str:
    return html.escape(str(text), quote=True)


def render(conn: sqlite3.Connection, path: str, method: str = "GET", form: dict | None = None, missing_env: tuple[str, ...] = ()) -> tuple[int, str]:
    """Logique pure du tableau de bord : (code HTTP, corps HTML). Testable sans socket."""
    if method not in ("GET", "POST"):
        return 405, _PAGE.format(title="Erreur", body="<p>Méthode non autorisée.</p>")
    if path == "/":
        body = (
            "<ul><li><a href=\"/config\">Configuration générale</a> — paramètres progressifs"
            " partagés avec Telegram (mêmes validations).</li>"
            "<li><a href=\"/state\">État système</a> — brouillons, intents, archive, rappels,"
            " benchmarks, variables d'environnement absentes (noms seuls).</li></ul>"
        )
        return 200, _PAGE.format(title="Accueil", body=body)
    if path == "/config":
        if method == "POST":
            return _config_post(conn, form or {})
        return 200, _PAGE.format(title="Configuration", body=_config_body(conn, message=None))
    if path == "/state":
        if method != "GET":
            return 405, _PAGE.format(title="Erreur", body="<p>Méthode non autorisée.</p>")
        return 200, _PAGE.format(title="État système", body=_state_body(conn, missing_env))
    return 404, _PAGE.format(title="Introuvable", body="<p>Page inconnue.</p>")


def _config_body(conn: sqlite3.Connection, message: str | None) -> str:
    rows = []
    for entry in prefs.spec():
        raw = prefs.get(conn, entry.key)
        shown = _esc(raw) if raw is not None else "<em>non défini</em>"
        rows.append(f"<tr><td><code>{_esc(entry.key)}</code></td><td>{_esc(entry.label)}</td><td>{shown}</td></tr>")
    form = (
        "<form method=\"post\" action=\"/config\">"
        "<label>Clé <select name=\"key\">"
        + "".join(f"<option value=\"{_esc(e.key)}\">{_esc(e.key)}</option>" for e in prefs.spec())
        + "</select></label> "
        "<label>Valeur <input name=\"value\" required maxlength=\"200\"></label> "
        "<button type=\"submit\">Enregistrer</button></form>"
    )
    message_html = f"<p><strong>{_esc(message)}</strong></p>" if message else ""
    return (
        message_html
        + form
        + "<table border=\"1\"><tr><th>Clé</th><th>Description</th><th>Valeur</th></tr>"
        + "".join(rows)
        + "</table>"
    )


def _config_post(conn: sqlite3.Connection, form: dict) -> tuple[int, str]:
    key = (form.get("key") or [""])[0].strip()
    value = (form.get("value") or [""])[0]
    try:
        normalized = prefs.set_value(conn, key, value)
    except prefs.PreferencesError as exc:
        return 400, _PAGE.format(
            title="Configuration",
            body=_config_body(conn, message=f"Réglage refusé ({exc.code}) : {exc}"),
        )
    return 200, _PAGE.format(
        title="Configuration",
        body=_config_body(conn, message=f"Réglage enregistré : {key} = {normalized}"),
    )


def _state_body(conn: sqlite3.Connection, missing_env: tuple[str, ...] = ()) -> str:
    now = datetime.now(TZ)
    rows = conn.execute("SELECT state, COUNT(*) c FROM drafts GROUP BY state").fetchall()
    drafts = ", ".join(f"{row['state']} : {row['c']}" for row in rows) or "aucun"
    intents = conn.execute("SELECT state, COUNT(*) c FROM publication_intents GROUP BY state").fetchall()
    intents_txt = ", ".join(f"{row['state']} : {row['c']}" for row in intents) or "aucun"
    history = conn.execute("SELECT COUNT(*) c FROM history_posts").fetchone()["c"]
    pending = conn.execute("SELECT COUNT(*) c FROM events WHERE state = 'NEW'").fetchone()["c"]
    benches = conn.execute("SELECT COUNT(*) c FROM llm_benchmarks").fetchone()["c"]
    reminders_enabled = store.get_setting(conn, "reminders_enabled", "0") == "1"
    missing = ", ".join(missing_env) if missing_env else "aucune"
    body = f"""<h2>État système</h2>
<ul>
<li>Heure locale (Africa/Tunis) : {_esc(now.isoformat())}</li>
<li>Brouillons : {_esc(drafts)}</li>
<li>Intentions de publication : {_esc(intents_txt)}</li>
<li>Archive : {history} publication(s) confirmée(s)</li>
<li>Événements en attente : {pending}</li>
<li>Benchmarks LLM : {benches} ligne(s)</li>
<li>Rappels : {"activés" if reminders_enabled else "désactivés"}</li>
<li>Variables d'environnement absentes (noms seuls) : {_esc(missing)}</li>
</ul>
<p>Publication LinkedIn : aucune publication possible depuis ce tableau de bord ;
les validations et l'autorisation finale restent dans Telegram.</p>"""
    return body


class _Handler(http.server.BaseHTTPRequestHandler):
    server_version = "LinkedInAssistantDashboard/0.1"

    def _dispatch(self, method: str) -> None:
        parsed = urllib.parse.urlparse(self.path)
        form: dict = {}
        if method == "POST":
            length = int(self.headers.get("Content-Length", 0) or 0)
            body = self.rfile.read(length).decode("utf-8", errors="replace")
            form = urllib.parse.parse_qs(body, keep_blank_values=True)
        conn = connect(self.server.db_path)  # connexion par requête (thread-safe)
        try:
            code, page = render(conn, parsed.path, method=method, form=form, missing_env=self.server.missing_env)
        finally:
            conn.close()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(page.encode("utf-8"))))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(page.encode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802 (API http.server)
        self._dispatch("GET")

    def do_POST(self) -> None:  # noqa: N802 (API http.server)
        self._dispatch("POST")

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        # Aucun contenu de requête n'est journalisé (paramètres non secrets mais
        # prudence par défaut) ; seule la ligne standard reste sur stderr.
        pass


def make_server(config: Config, missing_env: tuple[str, ...] = (), port: int | None = None):
    """Serveur lié à 127.0.0.1 uniquement (jamais 0.0.0.0)."""
    port = config.dashboard_port if port is None else port
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    server.db_path = config.db_path
    server.missing_env = missing_env
    return server


def run(config: Config, port: int | None = None) -> None:
    server = make_server(config, missing_env=config.missing_env, port=port)
    url = f"http://127.0.0.1:{server.server_address[1]}"
    print(f"Tableau de bord local : {url} (Ctrl+C pour arrêter). Aucune publication ici.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
