from __future__ import annotations

import argparse
import logging
import sys
import time

from . import db, inbox, media, purge, reminders, store
from .config import ConfigError, load
from .conversation import Conversation
from .publisher import build_publisher
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
    parser.add_argument("--dashboard", action="store_true", help="tableau de bord local 127.0.0.1 (aucune publication)")
    parser.add_argument("--port", type=int, default=None, help="port du tableau de bord (défaut : config dashboard_port)")
    args = parser.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    try:
        config = load(args.config)
    except ConfigError as exc:
        print(f"Configuration invalide : {exc}", file=sys.stderr)
        return 2

    if config.missing_env:
        # Signal par NOM uniquement : aucune valeur n'est jamais affichée ni journalisée.
        print("Variables d'environnement absentes (noms seuls) : " + ", ".join(config.missing_env))

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    log.addFilter(_RedactingFilter(config.telegram_token))

    conn = db.connect(config.db_path)
    purge.purge(conn)

    if args.local:
        from .local import run_local

        run_local(conn, config)
        return 0

    if args.dashboard:
        from .dashboard import run

        run(config, port=args.port)
        return 0

    if config.simulation:
        print(
            "Mode simulation : TELEGRAM_BOT_TOKEN absent, aucune action réseau. "
            "Renseignez config.toml (voir config.example.toml) et le jeton par variable d'environnement pour démarrer."
        )
        return 0

    client = TelegramClient(
        UrllibTransport(config.telegram_token, timeout=config.poll_timeout_seconds + 10),
        token=config.telegram_token,
        timeout=config.poll_timeout_seconds + 30,
    )
    buffer = media.ImageBuffer()
    publisher = build_publisher(config, buffer=buffer)
    conversation = Conversation(conn, config, client, publisher, buffer=buffer)

    log.info(
        "démarrage long polling, chat=%s, publication LinkedIn %s",
        config.chat_id,
        "réelle (treg)" if getattr(publisher, "is_real", False) else "simulée",
    )
    while True:
        try:
            inbox.poll_once(conn, client, config.poll_timeout_seconds)
            inbox.process_pending(conn, conversation.handle)
            reminders.tick(conn, client, config.chat_id, store.utcnow())
        except TelegramError as exc:
            log.warning("Telegram indisponible : %s", exc)
            time.sleep(5)
        except store.StoreError as exc:
            log.error("erreur de stockage (%s) : %s", exc.code, exc)
        except Exception as exc:  # noqa: BLE001
            # Un événement fautif ne doit JAMAIS arrêter l'assistant : l'événement
            # est marqué FAILED par le traitement d'inbox (aucun retry
            # automatique), le cycle suivant reprend. Le bot reste disponible.
            log.exception("erreur inattendue dans la boucle principale : %s", exc)
            time.sleep(5)
        except KeyboardInterrupt:
            log.info("arrêt demandé")
            return 0
        if args.once:
            return 0
        time.sleep(1)


if __name__ == "__main__":
    raise SystemExit(main())