"""Point d'entrée du conteneur : génère la config du volume si absente, puis lance le bot.

Règles :
- OWNER_ID / CHAT_ID viennent de l'environnement (jamais écrits dans le dépôt) ;
- TELEGRAM_BOT_TOKEN vient de l'environnement (l'application le lit déjà) ;
- publisher = "simulated" par défaut : la qualification ne touche jamais LinkedIn ;
- la base SQLite vit sur le volume /data (persistant), jamais dans l'image.
"""

from __future__ import annotations

import os
import pathlib
import sys

DATA = pathlib.Path("/data")
CONFIG_PATH = DATA / "config.toml"

TEMPLATE = """owner_id = {owner}
chat_id = {chat}
db_path = "/data/assistant.db"
timezone = "Africa/Tunis"
approval_ttl_seconds = 3600
poll_timeout_seconds = 25
publisher = "simulated"
env_file = "/data/.env"
"""


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    owner = os.environ.get("OWNER_ID", "").strip()
    chat = os.environ.get("CHAT_ID", "").strip() or owner
    if not owner.isdigit() or not chat.isdigit():
        sys.exit(
            "Variables OWNER_ID et CHAT_ID attendues : identifiants numériques "
            "Telegram positifs (pas des usernames)."
        )
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(TEMPLATE.format(owner=owner, chat=chat), encoding="utf-8")
    os.execvp("linkedin-assistant", ["linkedin-assistant", "--config", str(CONFIG_PATH)])


if __name__ == "__main__":
    main()
