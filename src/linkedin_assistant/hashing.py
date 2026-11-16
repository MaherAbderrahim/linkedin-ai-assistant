from __future__ import annotations

import hashlib
import json
import unicodedata

NORM_VERSION = "nfc-ws-v1"


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def content_fingerprint(manifest: dict) -> str:
    payload = {
        "account": manifest["account"],
        "text": manifest["text"],
        "visibility": manifest["visibility"],
        # image (héritage, révisions anciennes) ; images = liste multi-images.
        "image_hash": (manifest.get("image") or {}).get("sha256"),
        "image_hashes": [
            entry.get("sha256")
            for entry in (manifest.get("images") or [])
            if isinstance(entry, dict)
        ],
    }
    return sha256_text(canonical_json(payload))


def approval_fingerprint(draft_id: str, revision: int, manifest: dict) -> str:
    payload = {"draft_id": draft_id, "revision": revision, "manifest": manifest}
    return sha256_text(canonical_json(payload))


def normalize_for_comparison(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [" ".join(line.split()) for line in text.split("\n")]
    return "\n".join(lines).strip()


def normalized_hash(text: str) -> str:
    return sha256_text(normalize_for_comparison(text))
