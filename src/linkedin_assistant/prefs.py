from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from . import store

# Paramètres progressifs partagés (Telegram + tableau de bord), un seul chemin
# d'écriture : `store.set_setting` sur la table `settings` (même SQLite).
# Distinct de la table `preferences` (règles normatives confirmées séparément).
# Aucune valeur figée arbitrairement : les défauts sont des propositions visibles,
# modifiables ; les règles permanentes restent hors de ce registre.


@dataclass(frozen=True)
class Entry:
    key: str
    label: str
    kind: str  # "text" | "int" | "choice" | "bool" | "list" | "days"
    choices: tuple[str, ...] = ()
    bounds: tuple[int, int] | None = None


SPEC: tuple[Entry, ...] = (
    Entry("editorial_topics", "Thèmes préférés (séparés par des virgules)", "list"),
    Entry("editorial_tone", "Ton éditorial", "choice", choices=("neutre", "convivial", "expert", "direct")),
    Entry("editorial_audience", "Public cible", "text"),
    Entry("editorial_length", "Longueur cible (caractères)", "int", bounds=(0, 3000)),
    Entry("editorial_language", "Langue des posts", "choice", choices=("fr", "en", "ar")),
    Entry("search_provider", "Fournisseur de recherche", "choice", choices=("tavily", "none")),
    Entry("search_max_queries", "Requêtes de recherche max par tour", "int", bounds=(1, 3)),
    Entry("search_max_pages", "Pages de recherche max par tour", "int", bounds=(1, 5)),
    Entry("images_enabled", "Images activées", "bool"),
    Entry("image_provider", "Source d'images", "choice", choices=("commons", "user", "none")),
    Entry("post_visibility", "Visibilité des publications", "choice", choices=("public", "connections")),
    Entry("llm_provider", "Fournisseur LLM (choisi après comparaison)", "choice", choices=("groq", "openrouter", "none")),
    Entry("llm_model", "Modèle LLM (identifiant exact, choisi après comparaison)", "text"),
    Entry("reminders_enabled", "Rappels activés", "bool"),
    Entry("reminder_hour", "Heure du rappel quotidien (Africa/Tunis)", "int", bounds=(0, 23)),
    Entry("reminder_days", "Jours de rappel (0=lundi … 6=dimanche)", "days"),
    Entry("inactivity_hours", "Seuil d'inactivité (heures)", "int", bounds=(1, 720)),
)

_BY_KEY = {entry.key: entry for entry in SPEC}


class PreferencesError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def spec() -> tuple[Entry, ...]:
    """Registre immuable des paramètres progressifs."""
    return SPEC


def get(conn: sqlite3.Connection, key: str) -> str | None:
    """Valeur brute (chaîne) du paramètre, ou None si jamais défini."""
    entry = _BY_KEY.get(key)
    if entry is None:
        raise PreferencesError("UNKNOWN_KEY", f"paramètre inconnu : {key}")
    return store.get_setting(conn, key)


def values(conn: sqlite3.Connection) -> dict[str, str | None]:
    return {entry.key: store.get_setting(conn, entry.key) for entry in SPEC}


def set_value(conn: sqlite3.Connection, key: str, value: str) -> str:
    """Valide puis enregistre ; retourne la valeur normalisée. Échec conservateur."""
    entry = _BY_KEY.get(key)
    if entry is None:
        raise PreferencesError("UNKNOWN_KEY", f"paramètre inconnu : {key}")
    if value is None:
        raise PreferencesError("INVALID_VALUE", "valeur absente")
    normalized = _validate(entry, str(value))
    store.set_setting(conn, key, normalized)
    return normalized


def _validate(entry: Entry, value: str) -> str:
    v = value.strip()
    if entry.kind == "text":
        if not v or len(v) > 200:
            raise PreferencesError("INVALID_VALUE", "texte attendu (1 à 200 caractères)")
        return v
    if entry.kind == "int":
        try:
            n = int(v)
        except ValueError:
            raise PreferencesError("INVALID_VALUE", "entier attendu") from None
        if entry.bounds and not (entry.bounds[0] <= n <= entry.bounds[1]):
            raise PreferencesError("INVALID_VALUE", f"entier attendu entre {entry.bounds[0]} et {entry.bounds[1]}")
        return str(n)
    if entry.kind == "choice":
        v = v.casefold()
        if v not in entry.choices:
            raise PreferencesError("INVALID_VALUE", "choix parmi : " + ", ".join(entry.choices))
        return v
    if entry.kind == "bool":
        low = v.casefold()
        if low in ("1", "true", "on", "oui"):
            return "1"
        if low in ("0", "false", "off", "non"):
            return "0"
        raise PreferencesError("INVALID_VALUE", "valeur attendue : on|off (ou 0/1)")
    if entry.kind == "list":
        items = [item.strip() for item in v.split(",") if item.strip()]
        if not items or len(items) > 20 or any(len(item) > 60 for item in items):
            raise PreferencesError("INVALID_VALUE", "liste attendue : 1 à 20 éléments de 60 caractères max, séparés par des virgules")
        return ", ".join(items)
    if entry.kind == "days":
        tokens = [token.strip() for token in v.split(",") if token.strip()]
        if not tokens:
            raise PreferencesError("INVALID_VALUE", "au moins un jour attendu (0 à 6)")
        try:
            days = sorted({int(token) for token in tokens})
        except ValueError:
            raise PreferencesError("INVALID_VALUE", "jours attendus : entiers 0 à 6") from None
        if any(d < 0 or d > 6 for d in days):
            raise PreferencesError("INVALID_VALUE", "jours attendus : entiers 0 à 6")
        return ",".join(str(d) for d in days)
    raise PreferencesError("INVALID_VALUE", f"type non géré : {entry.kind}")


def show(conn: sqlite3.Connection, key: str) -> str:
    entry = _BY_KEY.get(key)
    if entry is None:
        raise PreferencesError("UNKNOWN_KEY", f"paramètre inconnu : {key}")
    raw = store.get_setting(conn, key)
    shown = raw if raw is not None else "non défini"
    return f"{entry.key} — {entry.label} : {shown}"


def display(conn: sqlite3.Connection) -> str:
    lines = ["Paramètres progressifs (propositions modifiables, même base que le tableau de bord) :"]
    for entry in SPEC:
        raw = store.get_setting(conn, entry.key)
        shown = raw if raw is not None else "non défini"
        lines.append(f"- {entry.key} ({entry.label}) : {shown}")
    lines.append("Usage : /settings <clé> <valeur>. Les règles permanentes restent confirmées séparément.")
    return "\n".join(lines)
