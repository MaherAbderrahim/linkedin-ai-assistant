from __future__ import annotations

import html
import json
import urllib.error
import urllib.request
from typing import Protocol


class TelegramError(Exception):
    pass


class Transport(Protocol):
    def request(self, method: str, payload: dict) -> dict: ...


def redact(text: str, token: str | None) -> str:
    if token and token in text:
        return text.replace(token, "***")
    return text


class UrllibTransport:
    def __init__(self, token: str, timeout: float = 35.0):
        self._token = token
        self._timeout = timeout

    def request(self, method: str, payload: dict) -> dict:
        url = f"https://api.telegram.org/bot{self._token}/{method}"
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            raise TelegramError(redact(str(exc), self._token)) from None
        if not data.get("ok"):
            raise TelegramError(redact(str(data.get("description", "réponse Telegram invalide")), self._token))
        return data["result"]


class TelegramClient:
    def __init__(self, transport: Transport):
        self._transport = transport

    def get_updates(self, offset: int, timeout: int) -> list[dict]:
        return self._transport.request(
            "getUpdates",
            {"offset": offset, "timeout": timeout, "allowed_updates": ["message", "callback_query"]},
        )

    def send_message(self, chat_id: int, text: str, reply_markup: dict | None = None) -> dict:
        payload: dict = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        return self._transport.request("sendMessage", payload)

    def send_photo(self, chat_id: int, photo: bytes, caption: str | None = None) -> dict:
        raise TelegramError("envoi de photo non implémenté en phase 2 (images en phase 7)")

    def answer_callback(self, callback_query_id: str, text: str | None = None) -> dict:
        payload: dict = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        return self._transport.request("answerCallbackQuery", payload)


def is_authorized(update: dict, owner_id: int, chat_id: int) -> bool:
    callback = update.get("callback_query")
    message = update.get("message") or (callback or {}).get("message")
    actor = (update.get("message") or {}).get("from") or (callback or {}).get("from")
    if not message or not actor:
        return False
    chat = message.get("chat", {})
    return (
        actor.get("id") == owner_id
        and chat.get("id") == chat_id
        and chat.get("type") == "private"
    )


def escape_html(text: str) -> str:
    return html.escape(text, quote=False)


def split_message(text: str, limit: int = 4096) -> list[str]:
    if len(text) <= limit:
        return [text]
    budget = limit - 16
    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= budget:
            chunks.append(remaining)
            break
        cut = remaining.rfind("\n", 0, budget + 1)
        cut = cut + 1 if cut > 0 else budget
        chunks.append(remaining[:cut])
        remaining = remaining[cut:]
    total = len(chunks)
    return [f"({i}/{total})\n{chunk}" for i, chunk in enumerate(chunks, 1)]


def keyboard(buttons: list[tuple[str, str]]) -> dict:
    return {"inline_keyboard": [[{"text": label, "callback_data": data}] for label, data in buttons]}