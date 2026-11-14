"""Scaffolding Phase 5 simulé : SearchProvider, budget borné, garde-fous d'extraction.

Aucun test n'accède au réseau : les gardes URL/résolution sont testées en pur ;
la connexion réelle n'est activée qu'en Phase 5 après qualification (G5).
"""

import pytest

from linkedin_assistant import extracting, searching


# --- Contrat SearchProvider (simulé uniquement) ---


def test_simulated_provider_deterministic():
    hits1 = searching.SimulatedSearchProvider().search("IA Tunisie", 3)
    hits2 = searching.SimulatedSearchProvider().search("IA Tunisie", 3)
    assert [h.url for h in hits1] == [h.url for h in hits2]
    assert len(hits1) == 3
    assert all("[SIMULATION" in h.title for h in hits1)
    assert all(h.url.startswith("https://") for h in hits1)


def test_provider_factory_refuses_unqualified():
    with pytest.raises(searching.SearchError) as exc:
        searching.provider("tavily")
    assert exc.value.code == "PROVIDER_NOT_QUALIFIED"
    assert isinstance(searching.provider("none"), searching.SimulatedSearchProvider)


def test_provider_rejects_bad_input():
    p = searching.SimulatedSearchProvider()
    with pytest.raises(searching.SearchError):
        p.search("   ", 3)
    with pytest.raises(searching.SearchError):
        p.search("ok", 0)


# --- Budget borné, échec conservateur ---


def test_budget_limits_queries_and_pages():
    budget = searching.SearchBudget(max_pages=2)
    for _ in range(3):
        budget.reserve_query()
    with pytest.raises(searching.SearchError) as exc:
        budget.reserve_query()
    assert exc.value.code == "BUDGET_QUERIES"
    budget.reserve_page("https://example.com/a")
    budget.reserve_page("https://example.com/b")
    with pytest.raises(searching.SearchError) as exc:
        budget.reserve_page("https://example.com/c")
    assert exc.value.code == "BUDGET_PAGES"


def test_budget_rejects_duplicate_url():
    budget = searching.SearchBudget(max_pages=5)
    budget.reserve_page("https://example.com/a")
    with pytest.raises(searching.SearchError) as exc:
        budget.reserve_page("https://example.com/a")
    assert exc.value.code == "BUDGET_DUP"


# --- Garde-fous d'extraction (pur, sans réseau) ---


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/x",
        "https://localhost/x",
        "https://10.0.0.5/x",
        "https://192.168.1.1/x",
        "https://172.16.0.9/x",
        "https://169.254.169.254/latest/meta-data/",
        "http://[::1]/x",
        "https://[fc00::1]/x",
        "file:///etc/passwd",
        "ftp://example.com/x",
        "https://user:secret@example.com/x",
        "",
        "https://" + "a" * 2100 + ".com",
        "https://host.invalid..com",
    ],
)
def test_is_public_http_url_refuses_private_and_schemes(url):
    assert extracting.is_public_http_url(url) is False


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/page",
        "http://example.org/a?b=c",
        "https://sous-domaine.example.tn/x#frag",
    ],
)
def test_is_public_http_url_accepts_public(url):
    assert extracting.is_public_http_url(url) is True


def test_fetch_refuses_before_any_connection():
    # URLs privées : refus immédiat, aucune connexion tentée.
    for url in ("http://127.0.0.1/x", "https://169.254.169.254/meta", "file:///etc/passwd"):
        with pytest.raises(extracting.ExtractError) as exc:
            extracting.fetch(url)
        assert exc.value.code == "BLOCKED_URL"


def test_fetch_refuses_unresolvable_without_leaking():
    # DNS public échouant (TLD .invalid) : erreur bornée, pas de fuite de contenu.
    with pytest.raises(extracting.ExtractError) as exc:
        extracting.fetch("https://test.invalid/page", timeout=2)
    assert exc.value.code in ("DNS_FAIL", "FETCH_FAIL")
