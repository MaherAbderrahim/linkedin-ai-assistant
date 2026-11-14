from __future__ import annotations

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


class ExtractError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


MAX_BYTES = 2_000_000  # 2 Mio par page, cohérent avec la borne d'import
MAX_URL_LENGTH = 2_000
_HOSTNAME_RE = re.compile(r"[A-Za-z0-9.-]+")


def _is_private_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


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
        headers={"User-Agent": "LinkedInAssistant-local/0.1 (+https://github.com/MaherAbderrahim/linkedin-ai-assistant)"},
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
