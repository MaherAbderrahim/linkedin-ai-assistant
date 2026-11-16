from __future__ import annotations

import html
import json
import secrets
import urllib.error
import urllib.request
from typing import Protocol

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LinkedInAssistant-local/0.1"


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

    def request_multipart(self, method: str, fields: dict, files: dict) -> dict:
        """Envoi multipart/form-data (photo binaire). Aucune donnée en base."""
        url = f"https://api.telegram.org/bot{self._token}/{method}"
        boundary = f"----LinkedInAssistant{secrets.token_hex(16)}"
        parts: list[bytes] = []
        for key, value in fields.items():
            if value is None:
                continue
            parts.append(
                (
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'
                ).encode("utf-8")
            )
        for key, (filename, content, content_type) in files.items():
            parts.append(
                (
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{key}"; filename="{filename}"\r\n'
                    f"Content-Type: {content_type}\r\n\r\n"
                ).encode("utf-8")
            )
            parts.append(content)
            parts.append(b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode("utf-8"))
        body = b"".join(parts)
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "User-Agent": USER_AGENT,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            raise TelegramError(redact(str(exc), self._token)) from None
        if not data.get("ok"):
            raise TelegramError(redact(str(data.get("description", "réponse Telegram invalide")), self._token))
        return data["result"]


class TelegramClient:
    def __init__(self, transport: Transport, token: str | None = None, timeout: float = 35.0):
        self._transport = transport
        self._token = token
        self._timeout = timeout

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

    def send_photo(self, chat_id: int, photo: bytes, caption: str | None = None,
                   content_type: str = "image/png") -> dict:
        """Envoie une image (aperçu de la publication). RAM seule côté assistant."""
        fields = {"chat_id": chat_id, "caption": caption}
        files = {"photo": ("image.png", photo, content_type)}
        sender = getattr(self._transport, "request_multipart", None)
        if sender is None:
            raise TelegramError("transport incapable d'envoyer une image")
        return sender("sendPhoto", fields, files)

    def get_file(self, file_id: str) -> dict:
        """Métadonnées d'un fichier Telegram (chemin de téléchargement)."""
        return self._transport.request("getFile", {"file_id": file_id})

    def download(self, file_path: str) -> bytes:
        """Télécharge les octets d'un fichier Telegram (photo envoyée par l'utilisateur).

        Le jeton figure dans l'URL de téléchargement : l'URL n'est jamais
        journalisée ni copiée dans un message.
        """
        if not self._token:
            raise TelegramError("jeton absent : téléchargement impossible")
        if not file_path or "/" not in file_path:
            raise TelegramError("chemin de fichier Telegram invalide")
        url = f"https://api.telegram.org/file/bot{self._token}/{file_path}"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return resp.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            raise TelegramError(redact(str(exc), self._token)) from None

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