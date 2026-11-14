from __future__ import annotations

import abc
from dataclasses import dataclass, field

# Scaffolding Phase 5 (recherche web) : contrat SearchProvider et budget borné.
# AUCUN appel réel en Phase 1 — seul le simulé existe ; la qualification Tavily
# (offres, pays, ZDR, PAYG non activé) reste à faire avant tout appel réel (G5).
# Bornes proposées et confirmées côté paramètres : 3 requêtes / 5 pages par tour.


class SearchError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class SearchHit:
    title: str
    url: str
    snippet: str


@dataclass
class SearchBudget:
    """Budget par tour, échec conservateur au plafond (jamais de débordement)."""

    max_queries: int = 3
    max_pages: int = 5
    queries: int = 0
    pages: int = 0
    seen_urls: set = field(default_factory=set)

    def reserve_query(self) -> None:
        if self.queries >= self.max_queries:
            raise SearchError("BUDGET_QUERIES", "plafond de requêtes du tour atteint")
        self.queries += 1

    def reserve_page(self, url: str) -> None:
        if self.pages >= self.max_pages:
            raise SearchError("BUDGET_PAGES", "plafond de pages du tour atteint")
        if url in self.seen_urls:
            raise SearchError("BUDGET_DUP", "page déjà réservée dans ce tour")
        self.seen_urls.add(url)
        self.pages += 1


class SearchProvider(abc.ABC):
    """Contrat d'adaptateur de recherche.

    - `search(query, max_results)` renvoie des hits avec URL et extrait.
    - Les résultats ne prouvent jamais un fait ; les pages sont relues
      localement par l'extracteur avant tout usage éditorial.
    - Aucune recherche ne porte sur le profil privé de l'utilisateur.
    - Aucun fallback automatique vers une offre payante.
    """

    name: str = ""

    @abc.abstractmethod
    def search(self, query: str, max_results: int) -> list[SearchHit]: ...


class SimulatedSearchProvider(SearchProvider):
    """Adaptateur simulé : aucune requête réseau, résultats déterministes."""

    def __init__(self, name: str = "simulated"):
        self.name = name

    def search(self, query: str, max_results: int) -> list[SearchHit]:
        if not query.strip():
            raise SearchError("EMPTY_QUERY", "requête vide")
        if max_results < 1:
            raise SearchError("INVALID_LIMIT", "max_results doit être ≥ 1")
        hits = []
        for i in range(1, min(max_results, 3) + 1):
            hits.append(
                SearchHit(
                    title=f"[SIMULATION {self.name}] résultat {i} — {query.strip()[:60]}",
                    url=f"https://example.invalid/{i}",
                    snippet=f"Extrait simulé {i} pour : {query.strip()[:100]}",
                )
            )
        return hits


def provider(name: str) -> SearchProvider:
    """Fabrique : seul le simulé existe jusqu'à qualification réelle (G5)."""
    if name != "none":
        raise SearchError(
            "PROVIDER_NOT_QUALIFIED",
            "recherche réelle non qualifiée (Tavily : offres/pays/ZDR/PAYG à vérifier, G5) ; simulé uniquement",
        )
    return SimulatedSearchProvider()
