from __future__ import annotations

import os
from pathlib import Path

# Variables attendues au démarrage. TELEGRAM_BOT_TOKEN absent = mode simulation ;
# les autres sont signalées par leur nom, sans jamais révéler de contenu.
EXPECTED_VARIABLES = (
    "TELEGRAM_BOT_TOKEN",
    "GROQ_API_KEY",
    "OPENROUTER_API_KEY",
    "TAVILY_API_KEY",
)


class EnvFileError(Exception):
    """Fichier .env mal formé : seule la position est signalée, jamais le contenu."""


def _parse(text: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            raise EnvFileError(f"ligne {number} mal formée (format attendu : NOM=valeur ; contenu non affiché)")
        name, _, value = line.partition("=")
        name = name.strip()
        if not name or any(ch.isspace() for ch in name):
            raise EnvFileError(f"ligne {number} : nom de variable invalide (contenu non affiché)")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        pairs[name] = value
    return pairs


def load_env(path: str | Path, override: bool = False) -> dict[str, str]:
    """Charge un fichier `.env` dans `os.environ` (parseur stdlib minimal).

    - Fichier facultatif : absent ⇒ aucune variable, aucune erreur.
    - L'environnement déjà posé prime (`override=False`) ; rien n'est écrasé
      silencieusement.
    - Application tout-ou-rien : un fichier mal formé ne modifie rien.
    - Les valeurs ne sont jamais renvoyées dans un message d'erreur ni
      journalisées ; seule la position (ligne) est signalée en cas d'erreur.
    """
    path = Path(path)
    if not path.exists():
        return {}
    pairs = _parse(path.read_text(encoding="utf-8"))
    for name, value in pairs.items():
        if override or name not in os.environ:
            os.environ[name] = value
    return pairs


def missing_names(expected=EXPECTED_VARIABLES, environ=None) -> list[str]:
    """Noms des variables attendues absentes ou vides. Aucune valeur n'est exposée."""
    env = os.environ if environ is None else environ
    return [name for name in expected if not str(env.get(name, "")).strip()]


def describe_missing(names: list[str]) -> str:
    """Message de démarrage : noms seuls, jamais de contenu."""
    return "Variables d'environnement absentes : " + ", ".join(names) if names else ""
