from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


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

    db_path = Path(data.get("db_path", "data/assistant.db"))
    if not db_path.is_absolute():
        db_path = path.parent / db_path

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
    )