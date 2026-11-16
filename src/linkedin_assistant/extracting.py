from __future__ import annotations

import html as html_module
import ipaddress
import re
import socket
import urllib.error
import urllib.parse
import urllib.request

# Extraction locale des pages de recherche (Phase 5) : téléchargement contrôlé
# et extraction bornée. Les garde-fous sont testables sans réseau ; le
# téléchargement réel n'est activé qu'en Phase 5, après qualification (G5).
# Refus systématiques : réseaux privés/liens, métadonnées, redirections
# non contrôlées, tailles démesurées, schémas non HTTP(S).

# Les serveurs d'éditeurs (Cloudflare et consorts) rejettent l'User-Agent par
# défaut de urllib (« Python-urllib/3.x »). Un UA explicite est nécessaire
# pour toute lecture de page réelle : ce n'est ni un contournement d'accès ni
# une demande d'authentification, seulement un client HTTP identifiable.
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LinkedInAssistant-local/0.1"


class ExtractError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


MAX_BYTES = 2_000_000  # 2 Mio par page, cohérent avec la borne d'import
MAX_URL_LENGTH = 2_000
MAX_IMAGE_BYTES = 8_000_000  # 8 Mio : limite de téléversement LinkedIn (catalogue)
_HOSTNAME_RE = re.compile(r"[A-Za-z0-9.-]+")
_SCRIPT_STYLE_RE = re.compile(r"(?is)<(script|style|noscript|template)[^>]*>.*?</\1>")
_TAG_RE = re.compile(r"(?s)<[^>]+>")
_WS_RE = re.compile(r"[ \t\r\f\v]+")
_BLANKS_RE = re.compile(r"\n{3,}")


def to_text(markup: str) -> str:
    """Réduit du HTML à un texte lisible (scripts et styles retirés).

    Volontairement simple et borné : c'est une entrée de contexte pour le
    rédacteur, pas un parseur HTML complet.
    """
    if not markup:
        return ""
    without_code = _SCRIPT_STYLE_RE.sub(" ", markup)
    text = _TAG_RE.sub(" ", without_code)
    text = html_module.unescape(text)
    lines = [_WS_RE.sub(" ", line).strip() for line in text.split("\n")]
    text = "\n".join(line for line in lines if line)
    return _BLANKS_RE.sub("\n\n", text).strip()


def _is_private_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Vrai pour toute adresse qui n'est pas publiquement routable.

    Piège connu : le préfixe IPv6 NAT64 (`64:ff9b::/96`) est marqué
    `is_reserved` par Python alors qu'il est une adresse GLOBALE légitime
    (traduction IPv6→IPv4, présente sur tous les réseaux IPv6-only). Le
    refuser produirait un faux positif sur des sites parfaitement publics.
    On s'appuie donc sur `is_global`, avec refus explicite des cas sensibles.
    """
    if (
        ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
        or ip.is_private
    ):
        return True
    return not ip.is_global


def is_public_http_url(url: str) -> bool:
    """True uniquement pour une URL http(s) publique, sans userinfo ni hôte privé."""
    if not url or len(url) > MAX_URL_LENGTH:
        return False
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    if parsed.username or parsed.password:
        return False
    host = parsed.hostname
    if not host:
        return False
    if host.lower() in ("localhost",) or host.endswith(".localhost") or host.endswith(".local"):
        return False
    if not _HOSTNAME_RE.fullmatch(host) or ".." in host or host.startswith(".") or host.endswith("."):
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return True  # nom d'hôte : la résolution est revérifiée avant connexion
    return not _is_private_ip(ip)


def resolve_public_hosts(url: str) -> list[str]:
    """Résout l'hôte et refuse toute IP privée/liens (anti rebinding DNS)."""
    host = urllib.parse.urlsplit(url).hostname
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError as exc:
        raise ExtractError("DNS_FAIL", f"résolution impossible : {host}") from exc
    ips: list[str] = []
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if _is_private_ip(ip):
            raise ExtractError("BLOCKED_HOST", "hôte résolu vers une IP non publique")
        if str(ip) not in ips:
            ips.append(str(ip))
    if not ips:
        raise ExtractError("DNS_FAIL", "aucune adresse résolue")
    return ips


def fetch(url: str, *, timeout: float = 10.0, max_bytes: int = MAX_BYTES) -> str:
    """Télécharge une page publique avec garde-fous, borné en taille.

    - URL non publique ⇒ refus avant toute connexion.
    - IPs résolues non publiques ⇒ refus (revérification post-DNS).
    - Réponse > max_bytes ⇒ refus (jamais de lecture illimitée).
    - Une erreur d'extraction n'est jamais une source vérifiée.
    """
    if not is_public_http_url(url):
        raise ExtractError("BLOCKED_URL", "URL non publique ou non HTTP(S) refusée")
    resolve_public_hosts(url)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (URL filtrée ci-dessus)
            final = response.geturl()
            if not is_public_http_url(final):
                raise ExtractError("BLOCKED_REDIRECT", "redirection vers une URL non publique")
            content_type = response.headers.get("Content-Type", "")
            if content_type and "html" not in content_type and "text" not in content_type:
                raise ExtractError("UNSUPPORTED_TYPE", f"type non textuel : {content_type}")
            data = response.read(max_bytes + 1)
    except ExtractError:
        raise
    except (OSError, urllib.error.URLError, ValueError) as exc:
        raise ExtractError("FETCH_FAIL", f"téléchargement impossible : {type(exc).__name__}") from exc
    if len(data) > max_bytes:
        raise ExtractError("TOO_LARGE", "page dépassant la taille autorisée")
    charset = "utf-8"
    for part in content_type.split(";"):
        part = part.strip()
        if part.startswith("charset="):
            charset = part[len("charset=") :].strip('"') or "utf-8"
    try:
        return data.decode(charset, errors="replace")
    except LookupError:
        return data.decode("utf-8", errors="replace")


IMAGE_CONTENT_TYPES = ("image/png", "image/jpeg", "image/jpg", "image/gif")
_IMAGE_SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)


def sniff_image(data: bytes) -> str | None:
    """Type d'image déduit des octets (pas de confiance au Content-Type seul)."""
    for signature, content_type in _IMAGE_SIGNATURES:
        if data.startswith(signature):
            return content_type
    return None


def fetch_binary(
    url: str,
    *,
    timeout: float = 20.0,
    max_bytes: int = MAX_IMAGE_BYTES,
    allowed_types: tuple[str, ...] = IMAGE_CONTENT_TYPES,
) -> tuple[bytes, str]:
    """Télécharge un binaire public (image) avec les mêmes garde-fous SSRF.

    - URL non publique ⇒ refus avant toute connexion.
    - IPs résolues non publiques ⇒ refus (revérification post-DNS).
    - Type MIME hors liste ⇒ refus, ET le contenu est vérifié par sa signature
      (un `Content-Type: image/png` sur des octets arbitraires est refusé).
    - Taille > max_bytes ⇒ refus (jamais de lecture illimitée).
    """
    if not is_public_http_url(url):
        raise ExtractError("BLOCKED_URL", "URL non publique ou non HTTP(S) refusée")
    resolve_public_hosts(url)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (URL filtrée ci-dessus)
            final = response.geturl()
            if not is_public_http_url(final):
                raise ExtractError("BLOCKED_REDIRECT", "redirection vers une URL non publique")
            declared = (response.headers.get("Content-Type", "") or "").split(";")[0].strip().lower()
            if declared and declared not in allowed_types:
                raise ExtractError("UNSUPPORTED_TYPE", f"type non supporté : {declared}")
            data = response.read(max_bytes + 1)
    except ExtractError:
        raise
    except (OSError, urllib.error.URLError, ValueError) as exc:
        raise ExtractError("FETCH_FAIL", f"téléchargement impossible : {type(exc).__name__}") from exc
    if len(data) > max_bytes:
        raise ExtractError("TOO_LARGE", "fichier dépassant la taille autorisée")
    sniffed = sniff_image(data)
    if sniffed is None:
        raise ExtractError("UNSUPPORTED_TYPE", "contenu binaire non reconnu comme image")
    if declared and declared != sniffed and sniffed not in allowed_types:
        raise ExtractError("UNSUPPORTED_TYPE", f"signature d'image inattendue : {sniffed}")
    return data, sniffed
