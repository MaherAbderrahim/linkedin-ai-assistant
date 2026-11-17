"""Lanceur pour hébergement managé de type Pterodactyl/Pelican (ex. Lunafy).

Le panneau n'exécute qu'un seul fichier (`Main file`) dans `/home/container`.
Ce script fait tout le reste, de façon idempotente (il est relancé à chaque
démarrage du serveur) :

1. récupère le code du dépôt GitHub — `git clone`/`git pull` si `git` est
   présent dans l'image, sinon archive `tar.gz` de la branche téléchargée avec
   la seule bibliothèque standard (aucune dépendance à `git`) ;
2. écrit la configuration à partir des variables d'environnement du panneau
   (aucun identifiant personnel n'est versionné dans le dépôt) ;
3. installe les dépendances listées dans `requirements.txt` ;
4. lance l'assistant (long polling Telegram).

Répartition des répertoires (le code est jetable, les données ne le sont pas) :

- `/home/container/app`   : le code (cloné à chaque mise à jour) ;
- `/home/container/state` : `config.toml` + base SQLite (jamais effacé).

Variables d'environnement attendues (page « Environment » du panneau) :
`TELEGRAM_BOT_TOKEN`, `GROQ_API_KEY`, `TAVILY_API_KEY`, `OWNER_ID`, `CHAT_ID`,
`LINKEDIN_ACCOUNT`, `PUBLISHER_MODE` (`simulated` ou `treg`),
`LINKEDIN_API_VERSION` (`YYYYMM`, obligatoire si `PUBLISHER_MODE=treg`),
et pour la publication réelle `TREG_TOKEN`, `TREG_URL`, `TREG_ORG`.
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.request

ROOT = "/home/container"
CODE_DIR = os.path.join(ROOT, "app")
STATE_DIR = os.path.join(ROOT, "state")
REPO_URL = os.environ.get(
    "REPO_URL", "https://github.com/MaherAbderrahim/linkedin-ai-assistant.git"
)
REPO_BRANCH = os.environ.get("REPO_BRANCH", "main")
PYTHON = sys.executable


def log(message: str) -> None:
    print(f"[bootstrap] {message}", flush=True)


def run(command: list[str]) -> int:
    log("exec: " + " ".join(command))
    try:
        completed = subprocess.run(command, check=False)
    except FileNotFoundError:
        log(f"commande absente : {command[0]}")
        return 127
    return completed.returncode


def _tarball_url() -> str:
    base = REPO_URL[:-4] if REPO_URL.endswith(".git") else REPO_URL
    return f"{base}/archive/refs/heads/{REPO_BRANCH}.tar.gz"


def _fetch_tarball() -> bool:
    """Repli sans `git` : archive de la branche, décompressée en bibliothèque standard."""
    try:
        with urllib.request.urlopen(_tarball_url(), timeout=90) as response:
            payload = response.read()
    except Exception as exc:  # noqa: BLE001 — on rapporte et on continue
        log(f"téléchargement de l'archive impossible : {exc}")
        return False
    staging = os.path.join(ROOT, "_extract")
    shutil.rmtree(staging, ignore_errors=True)
    os.makedirs(staging, exist_ok=True)
    try:
        with tarfile.open(fileobj=io.BytesIO(payload)) as tar:
            try:
                tar.extractall(staging, filter="data")
            except TypeError:  # Python < 3.12 : pas de filtre d'extraction
                tar.extractall(staging)
    except Exception as exc:  # noqa: BLE001
        log(f"décompression impossible : {exc}")
        return False
    entries = [name for name in os.listdir(staging) if os.path.isdir(os.path.join(staging, name))]
    if not entries:
        log("archive vide")
        return False
    source = os.path.join(staging, entries[0])
    shutil.rmtree(CODE_DIR, ignore_errors=True)
    shutil.copytree(source, CODE_DIR, dirs_exist_ok=True)
    shutil.rmtree(staging, ignore_errors=True)
    return os.path.isdir(os.path.join(CODE_DIR, "src"))


def fetch_code() -> bool:
    """Clone, met à jour ou télécharge le dépôt. Vrai si le code est en place."""
    if os.path.isdir(os.path.join(CODE_DIR, ".git")):
        run(["git", "-C", CODE_DIR, "pull", "--ff-only"])
        return os.path.isdir(os.path.join(CODE_DIR, "src"))
    if shutil.which("git"):
        shutil.rmtree(CODE_DIR, ignore_errors=True)
        if run(["git", "clone", "--depth", "1", "--branch", REPO_BRANCH, REPO_URL, CODE_DIR]) == 0:
            return True
        log("git clone impossible, repli sur l'archive de la branche")
    return _fetch_tarball()


CONFIG_TEMPLATE = """# Configuration générée par deploy/bootstrap.py — ne pas versionner.
# Les secrets restent dans les variables d'environnement du panneau.
owner_id = {owner_id}
chat_id = {chat_id}
db_path = "data/assistant.db"
timezone = "{timezone}"
approval_ttl_seconds = 3600
poll_timeout_seconds = 25
linkedin_account = "{linkedin_account}"
publisher = "{publisher}"
linkedin_api_version = "{linkedin_api_version}"
dashboard_port = 8000
"""


def write_config() -> str:
    """Écrit la configuration une seule fois (jamais de secret dedans)."""
    os.makedirs(os.path.join(STATE_DIR, "data"), exist_ok=True)
    path = os.path.join(STATE_DIR, "config.toml")
    if os.path.exists(path):
        return path

    def env(name: str, default: str = "") -> str:
        return os.environ.get(name, default).strip()

    content = CONFIG_TEMPLATE.format(
        owner_id=env("OWNER_ID", "0"),
        chat_id=env("CHAT_ID", "0"),
        timezone=env("TIMEZONE", "Africa/Tunis"),
        linkedin_account=env("LINKEDIN_ACCOUNT", "urn:li:person:UNCONFIGURED"),
        publisher=env("PUBLISHER_MODE", "simulated"),
        linkedin_api_version=env("LINKEDIN_API_VERSION", ""),
    )
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    os.chmod(path, 0o600)
    log("config.toml écrit (droits 600)")
    return path


def install_dependencies() -> None:
    requirements = os.path.join(CODE_DIR, "requirements.txt")
    if not os.path.exists(requirements):
        return
    if run([PYTHON, "-m", "pip", "install", "-U", "-r", requirements]) != 0:
        run([PYTHON, "-m", "pip", "install", "-U", "--break-system-packages", "-r", requirements])
    # La CLI `treg` doit être dans le PATH du bot (publication réelle).
    local_bin = os.path.join(ROOT, ".local", "bin")
    if os.path.isdir(local_bin) and local_bin not in os.environ.get("PATH", "").split(os.pathsep):
        os.environ["PATH"] = local_bin + os.pathsep + os.environ.get("PATH", "")


def main() -> int:
    os.makedirs(ROOT, exist_ok=True)
    if not fetch_code():
        log("ÉCHEC : code du dépôt indisponible")
        return 2
    config_path = write_config()
    install_dependencies()
    sys.path.insert(0, os.path.join(CODE_DIR, "src"))
    from linkedin_assistant.app import main as app_main

    return app_main(["--config", config_path])


if __name__ == "__main__":
    raise SystemExit(main())
