from __future__ import annotations

import sys

from .conversation import Conversation
from .publisher import SimulatedPublisher


class ConsoleClient:
    def __init__(self, out=None):
        self.out = out or sys.stdout
        self.buttons: list[tuple[str, str]] = []

    def send_message(self, chat_id, text, reply_markup=None):
        print(text, file=self.out)
        self.buttons = []
        if reply_markup:
            for row in reply_markup["inline_keyboard"]:
                for button in row:
                    self.buttons.append((button["text"], button["callback_data"]))
            for i, (label, _) in enumerate(self.buttons, 1):
                print(f"  [{i}] {label}", file=self.out)
        return {}

    def answer_callback(self, callback_query_id, text=None):
        return {}


def run_local(conn, config, inp=None, out=None) -> None:
    inp = inp or sys.stdin
    out = out or sys.stdout
    client = ConsoleClient(out)
    conversation = Conversation(conn, config, client, SimulatedPublisher())
    print(
        "Mode local interactif — aucune action réseau, publication simulée.\n"
        "Commandes : /new /preview /status /cancel ; texte libre = révision ; "
        "numéro = bouton affiché ; 'quit' pour sortir.",
        file=out,
    )
    while True:
        try:
            line = inp.readline()
        except KeyboardInterrupt:
            break
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        if line.lower() in ("quit", "exit"):
            break
        if line.isdigit() and client.buttons:
            index = int(line)
            if 1 <= index <= len(client.buttons):
                conversation.handle(
                    {
                        "update_id": 0,
                        "callback_query": {
                            "id": "local",
                            "from": {"id": config.owner_id},
                            "message": {"message_id": 0, "chat": {"id": config.chat_id, "type": "private"}},
                            "data": client.buttons[index - 1][1],
                        },
                    }
                )
                continue
        conversation.handle(
            {
                "update_id": 0,
                "message": {
                    "message_id": 0,
                    "from": {"id": config.owner_id},
                    "chat": {"id": config.chat_id, "type": "private"},
                    "text": line,
                },
            }
        )