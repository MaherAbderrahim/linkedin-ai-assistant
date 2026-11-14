from __future__ import annotations

import abc
import sqlite3

from . import store


class CertainPublicationError(Exception):
    """Rejet documenté sans effet externe : une nouvelle autorisation sera requise."""


class AmbiguousPublicationError(Exception):
    """L'envoi a pu aboutir côté LinkedIn : aucune nouvelle tentative automatique."""


class PublisherError(Exception):
    """Le contrat de publication ne peut pas être honoré (configuration/adaptateur)."""


class Publisher(abc.ABC):
    """Contrat unique des adaptateurs de publication (ADR-04, ADR-16).

    - `post(manifest)` envoie exactement le manifeste validé : aucun texte,
      hashtag, lien ou image ajouté ; aucune transformation cachée après accord.
    - Retour attendu : un `dict` de reçu ; champs optionnels nullables (ID/URL
      jamais inventés). Pour LinkedIn la preuve officielle est l'URN (`urn`),
      jamais une lecture non autorisée ni le scraping.
    - Rejet documenté sans effet externe : lever `CertainPublicationError` ;
      une nouvelle autorisation sera exigée pour une nouvelle tentative.
    - Résultat incertain (timeout, réponse perdue, reçu non conforme) : lever
      `AmbiguousPublicationError` ou `TimeoutError` — le socle verrouille le
      compte et n'effectue JAMAIS de nouvelle tentative automatique.
    - Aucun appel n'est déclenché par le LLM, la recherche ou un rappel ; seule
      la consommation atomique d'une autorisation finale valide un envoi.
    - Aucun nom ni secret en dur : un futur adaptateur treg résoudra la
      connexion LinkedIn health=ok dynamiquement (`resolve_treg_connection`).
    """

    @abc.abstractmethod
    def post(self, manifest: dict) -> dict: ...


class SimulatedPublisher(Publisher):
    def __init__(self, outcome: str = "success", receipt: dict | None = None):
        self.outcome = outcome
        self.receipt = {"urn": "urn:li:share:simulated"} if receipt is None else receipt
        self.calls = 0

    def post(self, manifest: dict) -> dict:
        self.calls += 1
        if self.outcome == "success":
            return self.receipt
        if self.outcome == "certain_failure":
            raise CertainPublicationError("refus documenté simulé")
        raise AmbiguousPublicationError("réponse perdue simulée")


def resolve_treg_connection(connections) -> str:
    """Résout dynamiquement la connexion treg LinkedIn saine (ADR-16).

    La rotation périodique de treg révoque les secrets et crée un nouveau nom
    `linkedin-N` à chaque reconnexion : aucun nom ni secret n'est codé en dur.
    Retourne le nom unique de la connexion `provider=linkedin` en `health=ok`.
    Aucune ou plusieurs connexions saines : échec conservateur, aucune cible
    choisie arbitrairement. Fonction pure : aucun appel treg n'est effectué ici.
    """
    healthy: list[str] = []
    for entry in connections or []:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("provider", "")).strip().lower() != "linkedin":
            continue
        health = str(entry.get("health", entry.get("status", ""))).strip().lower()
        if health != "ok":
            continue
        name = entry.get("tool") or entry.get("name") or entry.get("id")
        if name:
            healthy.append(str(name))
    if not healthy:
        raise PublisherError("TREG_CONNECTION_MISSING: aucune connexion linkedin health=ok")
    if len(healthy) > 1:
        raise PublisherError("TREG_CONNECTION_AMBIGUOUS: plusieurs connexions linkedin health=ok")
    return healthy[0]


def publish(conn: sqlite3.Connection, intent_id: str, adapter, now: str | None = None) -> str:
    intent = conn.execute("SELECT * FROM publication_intents WHERE id = ?", (intent_id,)).fetchone()
    if intent is None:
        raise store.StoreError("INTENT_NOT_FOUND", intent_id)
    version = conn.execute(
        "SELECT v.manifest_json FROM draft_versions v JOIN drafts d ON d.id = v.draft_id AND d.current_revision = v.revision WHERE d.id = ?",
        (intent["draft_id"],),
    ).fetchone()
    manifest = store._loads(version["manifest_json"])
    store.mark_sending(conn, intent_id, now)
    try:
        receipt = adapter.post(manifest)
        if not isinstance(receipt, dict):
            raise AmbiguousPublicationError("reçu non conforme au contrat Publisher (dict attendu)")
    except CertainPublicationError as exc:
        store.record_failure(conn, intent_id, str(exc), now)
        return "FAILED"
    except (AmbiguousPublicationError, TimeoutError) as exc:
        store.mark_unknown(conn, intent_id, str(exc), now)
        return "UNKNOWN_OUTCOME"
    store.record_success(conn, intent_id, receipt, now)
    return "PUBLISHED"
