from __future__ import annotations

import abc
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field

# Scaffolding Phase 5 (recherche web) : contrat SearchProvider et budget borné.
# Bornes proposées et confirmées côté paramètres : 3 requêtes / 5 pages par tour.
#
# Adaptateur réel : Tavily (offre gratuite documentée, clé `TAVILY_API_KEY`).
# Aucune recherche ne porte sur le profil privé de l'utilisateur ; les
# résultats ne prouvent jamais un fait (les pages sont relues localement par
# l'extracteur avant tout usage éditorial) ; aucun fallback payant automatique.

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LinkedInAssistant-local/0.1"
TAVILY_ENDPOINT = "https://api.tavily.com/search"


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
    is_real: bool = False

    @abc.abstractmethod
    def search(self, query: str, max_results: int) -> list[SearchHit]: ...


class SimulatedSearchProvider(SearchProvider):
    """Adaptateur simulé : aucune requête réseau, résultats déterministes."""

    is_real = False

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


class TavilySearchProvider(SearchProvider):
    """Adaptateur réel : API Tavily (recherche + extrait en un appel).

    - Un quota épuisé (429) est un arrêt explicite : aucun passage à une offre
      payante, aucune relance automatique.
    - `max_results` est borné par l'appelant (budget de tour) ; le budget
      reste la référence, pas le service distant.
    """

    is_real = True

    def __init__(self, api_key: str | None = None, *, timeout: float = 30.0, endpoint: str = TAVILY_ENDPOINT):
        resolved = api_key if api_key is not None else os.environ.get("TAVILY_API_KEY", "")
        if not resolved or not resolved.strip():
            raise SearchError("SEARCH_KEY_MISSING", "clé Tavily absente")
        self.name = "tavily"
        self._api_key = resolved
        self._timeout = timeout
        self._endpoint = endpoint

    def search(self, query: str, max_results: int) -> list[SearchHit]:
        if not query.strip():
            raise SearchError("EMPTY_QUERY", "requête vide")
        if max_results < 1:
            raise SearchError("INVALID_LIMIT", "max_results doit être ≥ 1")
        payload = {
            "api_key": self._api_key,
            "query": query.strip(),
            "max_results": min(max_results, 10),
            "search_depth": "basic",
            "include_answer": False,
            "include_raw_content": False,
        }
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self._endpoint,
            data=body,
            headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                raise SearchError(
                    "SEARCH_QUOTA",
                    "quota Tavily épuisé — arrêt, aucun passage à une offre payante",
                ) from exc
            if exc.code in (401, 403):
                raise SearchError("SEARCH_AUTH", "clé Tavily refusée") from exc
            raise SearchError("SEARCH_UNAVAILABLE", f"Tavily : erreur HTTP {exc.code}") from exc
        except (OSError, urllib.error.URLError) as exc:
            raise SearchError("SEARCH_UNAVAILABLE", f"Tavily injoignable : {type(exc).__name__}") from exc
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SearchError("SEARCH_BAD_RESPONSE", "réponse Tavily illisible") from exc
        results = data.get("results")
        if not isinstance(results, list):
            raise SearchError("SEARCH_BAD_RESPONSE", "réponse Tavily sans résultats")
        hits = []
        for item in results[:max_results]:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            if not isinstance(url, str) or not url.strip():
                continue
            hits.append(
                SearchHit(
                    title=str(item.get("title") or "")[:300],
                    url=url,
                    snippet=str(item.get("content") or "")[:1200],
                )
            )
        return hits


def provider(name: str) -> SearchProvider:
    """Fabrique : `tavily` réel si la clé est présente, `none` simulé."""
    if name == "none":
        return SimulatedSearchProvider()
    if name == "tavily":
        if not os.environ.get("TAVILY_API_KEY", "").strip():
            raise SearchError(
                "SEARCH_KEY_MISSING",
                "TAVILY_API_KEY absente : recherche réelle impossible (le mode simulé reste disponible)",
            )
        return TavilySearchProvider()
    raise SearchError("PROVIDER_UNKNOWN", f"fournisseur de recherche inconnu : {name}")
