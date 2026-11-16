"""Recherche → proposition de post : clarification, budget, sources non fiables.

Aucun test n'accède au réseau : les pages sont simulées, le modèle est simulé.
"""

import pytest

from linkedin_assistant import extracting, llm, research, searching


class FakeSearch(searching.SearchProvider):
    name = "fake"

    def __init__(self, hits=None, error=None):
        self.hits = hits or []
        self.error = error
        self.queries = []

    def search(self, query, max_results):
        self.queries.append(query)
        if self.error:
            raise self.error
        return self.hits[:max_results]


class FakeLLM(llm.LLMProvider):
    name = "fake"

    def __init__(self, text="Un post proposé.", error=None):
        self.model = "fake-model"
        self.text = text
        self.error = error
        self.prompts = []

    def generate(self, task, prompt):
        self.prompts.append((task, prompt))
        if self.error:
            raise self.error
        return llm.LLMResult(
            provider=self.name,
            model=self.model,
            text=self.text,
            latency_ms=1,
            usage={"simulated": True},
        )


@pytest.fixture()
def fake_page(monkeypatch):
    monkeypatch.setattr(
        extracting,
        "fetch",
        lambda url, timeout=10.0, max_bytes=extracting.MAX_BYTES: (
            "<html><head><title>Page de test</title></head><body>"
            "<script>bad()</script><p>Contenu utile de la page.</p></body></html>"
        ),
    )


# --- clarification ---------------------------------------------------------


def test_short_name_needs_clarification():
    assert research.needs_clarification("IA") is True
    assert research.needs_clarification("LinkedIn") is True
    assert research.needs_clarification("  ") is True


def test_explicit_subject_does_not_need_clarification():
    assert research.needs_clarification("l'API Posts de LinkedIn") is False


def test_clarification_question_names_the_topic():
    question = research.clarification_question("IA")
    assert "IA" in question
    assert "Précisez" in question


# --- recherche -------------------------------------------------------------


def test_research_produces_draft_with_sources(fake_page):
    hits = [searching.SearchHit(title="Titre", url="https://exemple.fr/a", snippet="extrait")]
    outcome = research.research(
        "l'API Posts de LinkedIn",
        search_provider=FakeSearch(hits),
        llm_provider=FakeLLM(),
        budget=searching.SearchBudget(),
    )
    assert outcome.status == "draft"
    assert outcome.text == "Un post proposé."
    assert [s.url for s in outcome.sources] == ["https://exemple.fr/a"]
    assert outcome.as_dict()["sources"][0]["title"] == "Titre"


def test_prompt_contains_sources_marked_untrusted(fake_page):
    hits = [searching.SearchHit(title="Titre", url="https://exemple.fr/a", snippet="extrait")]
    fake_llm = FakeLLM()
    research.research(
        "sujet test",
        search_provider=FakeSearch(hits),
        llm_provider=fake_llm,
        budget=searching.SearchBudget(),
    )
    _task, prompt = fake_llm.prompts[0]
    assert "https://exemple.fr/a" in prompt
    assert "non fiables" in prompt
    assert "n'invente aucun fait" in prompt


def test_budget_stops_second_query(fake_page):
    hits = [searching.SearchHit(title="T", url="https://exemple.fr/a", snippet="e")]
    budget = searching.SearchBudget(max_queries=1)
    research.research(
        "sujet test", search_provider=FakeSearch(hits), llm_provider=FakeLLM(), budget=budget
    )
    assert budget.queries == 1


def test_no_readable_source_returns_question_not_draft(monkeypatch):
    monkeypatch.setattr(
        extracting, "fetch", lambda url, timeout=10.0, max_bytes=extracting.MAX_BYTES: "<html></html>"
    )
    hits = [searching.SearchHit(title="T", url="https://exemple.fr/a", snippet="e")]
    outcome = research.research(
        "sujet test", search_provider=FakeSearch(hits), llm_provider=FakeLLM(), budget=searching.SearchBudget()
    )
    assert outcome.status == "sources_only"
    assert outcome.text == ""


def test_llm_quota_error_is_surfaced(fake_page):
    hits = [searching.SearchHit(title="T", url="https://exemple.fr/a", snippet="e")]
    with pytest.raises(research.ResearchError) as exc:
        research.research(
            "sujet test",
            search_provider=FakeSearch(hits),
            llm_provider=FakeLLM(error=llm.LLMError("LLM_QUOTA", "quota épuisé")),
            budget=searching.SearchBudget(),
        )
    assert exc.value.code == "LLM_QUOTA"


def test_search_quota_error_is_surfaced():
    with pytest.raises(searching.SearchError) as exc:
        research.research(
            "sujet test",
            search_provider=FakeSearch(error=searching.SearchError("SEARCH_QUOTA", "quota épuisé")),
            llm_provider=FakeLLM(),
            budget=searching.SearchBudget(),
        )
    assert exc.value.code == "SEARCH_QUOTA"


# --- lecture d'un lien direct ----------------------------------------------


def test_read_url_extracts_text_and_title(monkeypatch):
    monkeypatch.setattr(
        extracting,
        "fetch",
        lambda url, timeout=15.0, max_bytes=extracting.MAX_BYTES: (
            "<html><head><title>Mon article</title></head><body><p>Bonjour</p></body></html>"
        ),
    )
    source = research.read_url("https://exemple.fr/article")
    assert source.title == "Mon article"
    assert "Bonjour" in source.excerpt


def test_read_url_refuses_private_url():
    with pytest.raises(research.ResearchError) as exc:
        research.read_url("http://127.0.0.1/page")
    assert exc.value.code == "URL_BLOCKED"


# --- extraction de texte ---------------------------------------------------


def test_to_text_removes_scripts_and_tags():
    text = extracting.to_text("<html><script>alert(1)</script><p>Bonjour &amp; salut</p></html>")
    assert "alert" not in text
    assert "Bonjour & salut" in text
