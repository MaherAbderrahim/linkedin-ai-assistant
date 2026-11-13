from __future__ import annotations

import argparse
import logging
import sys
import time

from . import db, inbox, purge, store
from .config import ConfigError, load
from .conversation import Conversation
from .publisher import SimulatedPublisher
from .telegram import TelegramClient, TelegramError, UrllibTransport, redact

log = logging.getLogger("linkedin_assistant")


class _RedactingFilter(logging.Filter):
    def __init__(self, token: str | None):
        super().__init__()
        self._token = token

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(str(record.msg), self._token)
        if record.args:
            record.args = tuple(redact(str(a), self._token) for a in record.args)
        return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Assistant LinkedIn personnel — socle phase 2")
    parser.add_argument("--config", default="config.toml", help="fichier de configuration TOML local")
    parser.add_argument("--once", action="store_true", help="un seul cycle de réception puis arrêt")
    parser.add_argument("--local", action="store_true", help="mode interactif local sans réseau (simulation)")
    args = parser.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    try:
        config = load(args.config)
    except ConfigError as exc:
        print(f"Configuration invalide : {exc}", file=sys.stderr)
        return 2

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    log.addFilter(_RedactingFilter(config.telegram_token))

    conn = db.connect(config.db_path)
    purge.purge(conn)

    if args.local:
        from .local import run_local

        run_local(conn, config)
        return 0

    if config.simulation:
        print(
            "Mode simulation : TELEGRAM_BOT_TOKEN absent, aucune action réseau. "
            "Renseignez config.toml (voir config.example.toml) et le jeton par variable d'environnement pour démarrer."
        )
        return 0

    client = TelegramClient(UrllibTransport(config.telegram_token, timeout=config.poll_timeout_seconds + 10))
    conversation = Conversation(conn, config, client, SimulatedPublisher())

    log.info("démarrage long polling, chat=%s, publication LinkedIn simulée", config.chat_id)
    while True:
        try:
            inbox.poll_once(conn, client, config.poll_timeout_seconds)
            inbox.process_pending(conn, conversation.handle)
        except TelegramError as exc:
            log.warning("Telegram indisponible : %s", exc)
            time.sleep(5)
        except store.StoreError as exc:
            log.error("erreur de stockage (%s) : %s", exc.code, exc)
        except KeyboardInterrupt:
            log.info("arrêt demandé")
            return 0
        if args.once:
            return 0
        time.sleep(1)


if __name__ == "__main__":
    raise SystemExit(main())