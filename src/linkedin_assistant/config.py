from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .envfile import EnvFileError, load_env, missing_names


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Config:
    owner_id: int
    chat_id: int
    db_path: Path
    timezone: str = "Africa/Tunis"
    approval_ttl_seconds: int = 3600
    poll_timeout_seconds: int = 25
    linkedin_account: str = "urn:li:person:UNCONFIGURED"
    telegram_token: str | None = None
    env_file: Path | None = None
    missing_env: tuple[str, ...] = ()
    dashboard_port: int = 8000
    #: "simulated" (aucun appel externe) ou "treg" (publication réelle).
    publisher: str = "simulated"
    #: Version LinkedIn-Version (YYYYMM) choisie explicitement, requise par
    #: l'adaptateur treg : aucun choix silencieux de version.
    linkedin_api_version: str = ""
    #: Dossier local en LECTURE SEULE (textes → brouillons, images → candidats).
    #: None = /folder désactivé ; l'existence est vérifiée à l'usage, pas ici.
    local_folder: Path | None = None

    @property
    def simulation(self) -> bool:
        return self.telegram_token is None


def load(path: str | Path) -> Config:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"fichier de configuration absent: {path}")
    with path.open("rb") as fh:
        data = tomllib.load(fh)

    owner_id = data.get("owner_id")
    chat_id = data.get("chat_id")
    if not isinstance(owner_id, int) or isinstance(owner_id, bool) or owner_id <= 0:
        raise ConfigError("owner_id doit être un identifiant numérique Telegram positif")
    if not isinstance(chat_id, int) or isinstance(chat_id, bool) or chat_id <= 0:
        raise ConfigError("chat_id doit être un identifiant numérique de chat privé positif")

    dashboard_port = data.get("dashboard_port", 8000)
    if not isinstance(dashboard_port, int) or isinstance(dashboard_port, bool) or not (1 <= dashboard_port <= 65535):
        raise ConfigError("dashboard_port doit être un entier entre 1 et 65535")

    publisher = str(data.get("publisher", "simulated")).strip().lower()
    if publisher not in ("simulated", "treg"):
        raise ConfigError("publisher doit être 'simulated' ou 'treg'")
    linkedin_api_version = str(data.get("linkedin_api_version", "") or "").strip()
    if publisher == "treg" and not re.fullmatch(r"\d{6}", linkedin_api_version):
        raise ConfigError(
            "linkedin_api_version (YYYYMM) est obligatoire et doit être choisi explicitement "
            "quand publisher = 'treg'"
        )

    db_path = Path(data.get("db_path", "data/assistant.db"))
    if not db_path.is_absolute():
        db_path = path.parent / db_path

    local_folder: Path | None = None
    raw_folder = data.get("local_folder")
    if raw_folder is not None:
        if not isinstance(raw_folder, str) or not raw_folder.strip():
            raise ConfigError("local_folder doit être un chemin de dossier non vide, ou absent")
        local_folder = Path(raw_folder.strip())
        if not local_folder.is_absolute():
            local_folder = path.parent / local_folder

    # Fichier d'environnement local (facultatif, chargé avant la lecture du jeton).
    env_name = data.get("env_file", ".env")
    env_path = Path(env_name)
    if not env_path.is_absolute():
        env_path = path.parent / env_path
    try:
        load_env(env_path)
    except EnvFileError as exc:
        raise ConfigError(f"fichier d'environnement invalide ({env_path.name}) : {exc}") from exc

    token = os.environ.get("TELEGRAM_BOT_TOKEN") or None
    if token is not None and not token.strip():
        token = None

    return Config(
        owner_id=owner_id,
        chat_id=chat_id,
        db_path=db_path,
        timezone=data.get("timezone", "Africa/Tunis"),
        approval_ttl_seconds=int(data.get("approval_ttl_seconds", 3600)),
        poll_timeout_seconds=int(data.get("poll_timeout_seconds", 25)),
        linkedin_account=data.get("linkedin_account", "urn:li:person:UNCONFIGURED"),
        telegram_token=token,
        env_file=env_path,
        missing_env=tuple(missing_names()),
        dashboard_port=dashboard_port,
        publisher=publisher,
        linkedin_api_version=linkedin_api_version,
        local_folder=local_folder,
    )