"""Contrat LLMProvider : adaptateurs réels (Groq/OpenRouter) + simulés.

Les tests restent SANS RÉSEAU : l'environnement est contrôlé par monkeypatch
et les appels HTTP ne sont jamais effectués (aucun appel réel dans la suite).
"""

import pytest

from linkedin_assistant import llm, store
from linkedin_assistant.hashing import sha256_text


@pytest.fixture(autouse=True)
def _no_ambient_keys(monkeypatch):
    """Les clés ambiantes de la machine ne doivent pas changer le contrat."""
    for name in ("GROQ_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(name, raising=False)


def test_factory_returns_simulated_without_key():
    p = llm.provider("groq", "llama-3-70b")
    assert isinstance(p, llm.SimulatedProvider)
    assert (p.name, p.model) == ("groq", "llama-3-70b")
    p2 = llm.provider("openrouter", "qwen:free")
    assert isinstance(p2, llm.SimulatedProvider)
    assert p2.name == "openrouter"
    with pytest.raises(llm.LLMError) as exc:
        llm.provider("anthropic", "x")
    assert exc.value.code == "LLM_PROVIDER_UNKNOWN"


def test_factory_returns_real_provider_with_key(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    p = llm.provider("groq", "openai/gpt-oss-120b")
    assert isinstance(p, llm.GroqProvider)
    assert p.is_real is True
    assert p.model == "openai/gpt-oss-120b"


def test_openrouter_refuses_paid_model(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    with pytest.raises(llm.LLMError) as exc:
        llm.provider("openrouter", "meta-llama/llama-3.3-70b-instruct")
    assert exc.value.code == "LLM_MODEL_NOT_FREE"


def test_openrouter_accepts_free_variant(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    p = llm.provider("openrouter", "google/gemma-4-31b-it:free")
    assert isinstance(p, llm.OpenRouterProvider)


def test_missing_model_refused(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    with pytest.raises(llm.LLMError) as exc:
        llm.GroqProvider("")
    assert exc.value.code == "LLM_MODEL_MISSING"


def test_generate_deterministic_and_marked():
    r1 = llm.provider("openrouter", "m1").generate("draft", "Sujet : IA en Tunisie")
    r2 = llm.provider("openrouter", "m1").generate("draft", "Sujet : IA en Tunisie")
    assert r1.text == r2.text
    assert "[SIMULATION openrouter/m1]" in r1.text
    assert "Sujet : IA en Tunisie" in r1.text
    assert r1.usage == {"simulated": True}
    assert r1.latency_ms >= 0


def test_http_provider_extracts_text_and_usage(monkeypatch):
    """Réponse HTTP simulée : aucun réseau, contrat d'extraction vérifié."""

    class FakeResponse:
        def read(self):
            return b'{"choices": [{"message": {"content": "Un post propos\\u00e9."}}], "usage": {"total_tokens": 15}}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    calls = []

    def fake_urlopen(request, timeout=None):
        calls.append(request)
        return FakeResponse()

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)
    provider = llm.GroqProvider("openai/gpt-oss-120b", api_key="gsk_test")
    result = provider.generate("linkedin_post", "Sujet")
    assert result.text == "Un post proposé."
    assert result.usage == {"total_tokens": 15}
    assert result.latency_ms >= 0
    assert len(calls) == 1


def test_quota_exhausted_is_explicit_stop(monkeypatch):
    def fake_urlopen(request, timeout=None):
        raise llm.urllib.error.HTTPError("url", 429, "Too Many Requests", {}, None)

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)
    provider = llm.GroqProvider("openai/gpt-oss-120b", api_key="gsk_test")
    with pytest.raises(llm.LLMError) as exc:
        provider.generate("linkedin_post", "Sujet")
    assert exc.value.code == "LLM_QUOTA"
    assert "payant" in str(exc.value)


def test_benchmark_records_one_row_per_pair(conn):
    providers = [llm.SimulatedProvider("groq", "a"), llm.SimulatedProvider("openrouter", "b")]
    tasks = [("draft", "prompt-un"), ("correct", "prompt-deux")]
    ids = llm.run_benchmark(conn, providers, tasks)
    assert len(ids) == 4
    rows = conn.execute("SELECT * FROM llm_benchmarks ORDER BY id").fetchall()
    assert len(rows) == 4
    hashes = {(row["task"], row["prompt_hash"]) for row in rows}
    assert hashes == {
        ("draft", sha256_text("prompt-un")),
        ("correct", sha256_text("prompt-deux")),
    }
    assert all(row["latency_ms"] >= 0 for row in rows)
    assert all("[SIMULATION" in row["output_text"] for row in rows)
    assert {row["provider"] for row in rows} == {"groq", "openrouter"}
    assert all(store._loads(row["usage_json"]) == {"simulated": True} for row in rows)


def test_human_score_and_summary(conn):
    ids = llm.run_benchmark(conn, [llm.SimulatedProvider("groq", "a")], [("draft", "p1"), ("correct", "p2")])
    llm.score(conn, ids[0], 4, "bon français")
    llm.score(conn, ids[1], 2)
    row = conn.execute("SELECT * FROM llm_benchmarks WHERE id = ?", (ids[0],)).fetchone()
    assert row["human_score"] == 4 and row["human_notes"] == "bon français"
    with pytest.raises(llm.LLMError) as exc:
        llm.score(conn, ids[0], 6)
    assert exc.value.code == "INVALID_SCORE"
    with pytest.raises(llm.LLMError) as exc:
        llm.score(conn, "absent", 3)
    assert exc.value.code == "BENCH_NOT_FOUND"
    summary = llm.results(conn)
    assert len(summary) == 1
    assert summary[0]["provider"] == "groq"
    assert summary[0]["runs"] == 2
    assert summary[0]["avg_human_score"] == 3.0
    assert summary[0]["unscored"] == 0


def test_no_selection_is_made_by_the_harness(conn):
    """Le harness n'enregistre aucun choix : aucun réglage LLM n'est posé."""
    llm.run_benchmark(
        conn,
        [llm.SimulatedProvider("groq", "a"), llm.SimulatedProvider("openrouter", "b")],
        [("t", "p")],
    )
    assert store.get_setting(conn, "llm_provider") is None
    assert store.get_setting(conn, "llm_model") is None
