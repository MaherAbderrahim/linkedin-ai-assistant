from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from .extracting import IMAGE_CONTENT_TYPES, sniff_image

# Tampon d'images RAM SEULE : aucun binaire n'est écrit sur disque ni en base.
#
# Règles du projet :
# - pas d'archive binaire d'images (RAM seule de bout en bout, sans BLOB,
#   disque temporaire ni sauvegarde) ; seules les métadonnées, l'empreinte et
#   les droits autorisés sont persistables ;
# - perte du tampon ou redémarrage => NOUVEL aperçu et NOUVELLES approbations
#   image/finale, jamais de retrait silencieux ;
# - l'image est approuvée sur son fichier exact (empreinte SHA-256), jamais
#   sur un simple texte.
#
# Le tampon vit dans le processus du bot : il est donc vide après un
# redémarrage. C'est un comportement attendu, pas une panne.

MAX_IMAGE_BYTES = 8_000_000  # 8 Mio : limite de téléversement LinkedIn
MAX_IMAGES_PER_DRAFT = 4


class MediaError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ImageAsset:
    """Une image prête à être téléversée, gardée en mémoire uniquement."""

    token: str
    sha256: str
    content_type: str
    filename: str
    alt_text: str
    source: str  # "telegram" | "url"
    size: int
    data: bytes = field(repr=False, compare=False)

    def manifest_entry(self) -> dict:
        """Métadonnées persistables (jamais les octets)."""
        return {
            "token": self.token,
            "sha256": self.sha256,
            "content_type": self.content_type,
            "filename": self.filename,
            "alt_text": self.alt_text,
            "source": self.source,
            "size": self.size,
        }


class ImageBuffer:
    """Stockage d'images en RAM, borné, sans persistance."""

    def __init__(self, max_images: int = MAX_IMAGES_PER_DRAFT, max_bytes: int = MAX_IMAGE_BYTES):
        self._assets: dict[str, ImageAsset] = {}
        self._max_images = max_images
        self._max_bytes = max_bytes

    def add(
        self,
        data: bytes,
        *,
        content_type: str,
        filename: str,
        source: str,
        alt_text: str = "",
        token: str | None = None,
    ) -> ImageAsset:
        if not isinstance(data, (bytes, bytearray)) or not data:
            raise MediaError("IMAGE_EMPTY", "image vide")
        data = bytes(data)
        if len(data) > self._max_bytes:
            raise MediaError(
                "IMAGE_TOO_LARGE",
                f"image de {len(data)} octets : maximum {self._max_bytes} octets",
            )
        sniffed = sniff_image(data)
        if sniffed is None:
            raise MediaError("IMAGE_UNSUPPORTED", "format d'image non reconnu (PNG, JPEG ou GIF attendus)")
        if content_type and content_type.split(";")[0].strip().lower() != sniffed:
            # Le type déclaré et les octets divergent : on suit les octets.
            content_type = sniffed
        if sniffed not in IMAGE_CONTENT_TYPES:
            raise MediaError("IMAGE_UNSUPPORTED", f"format non accepté par LinkedIn : {sniffed}")
        if len(self._assets) >= self._max_images and token not in self._assets:
            raise MediaError(
                "IMAGE_LIMIT",
                f"{self._max_images} images maximum par brouillon",
            )
        asset = ImageAsset(
            token=token or f"img_{hashlib.sha256(data).hexdigest()[:16]}",
            sha256=hashlib.sha256(data).hexdigest(),
            content_type=sniffed,
            filename=filename or "image",
            alt_text=alt_text or "",
            source=source,
            size=len(data),
            data=data,
        )
        self._assets[asset.token] = asset
        return asset

    def get(self, token: str | None) -> ImageAsset | None:
        if not token:
            return None
        return self._assets.get(token)

    def remove(self, token: str) -> bool:
        return self._assets.pop(token, None) is not None

    def clear(self) -> None:
        self._assets.clear()

    def assets(self) -> list[ImageAsset]:
        return list(self._assets.values())

    def __len__(self) -> int:
        return len(self._assets)
