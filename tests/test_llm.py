"""Chantier 4 : contrat LLMProvider, adaptateurs simulés et harness de comparaison."""

import pytest

from linkedin_assistant import llm, store
from linkedin_assistant.hashing import sha256_text


def test_factory_returns_simulated_only():
    p = llm.provider("groq", "llama-3-70b")
    assert isinstance(p, llm.SimulatedProvider)
    assert (p.name, p.model) == ("groq", "llama-3-70b")
    p2 = llm.provider("openrouter", "qwen-free")
    assert p2.name == "openrouter"
    with pytest.raises(llm.LLMError) as exc:
        llm.provider("anthropic", "x")
    assert exc.value.code == "LLM_PROVIDER_UNKNOWN"


def test_generate_deterministic_and_marked():
    r1 = llm.provider("openrouter", "m1").generate("draft", "Sujet : IA en Tunisie")
    r2 = llm.provider("openrouter", "m1").generate("draft", "Sujet : IA en Tunisie")
    assert r1.text == r2.text
    assert "[SIMULATION openrouter/m1]" in r1.text
    assert "Sujet : IA en Tunisie" in r1.text
    assert r1.usage == {"simulated": True}
    assert r1.latency_ms >= 0


def test_benchmark_records_one_row_per_pair(conn):
    providers = [llm.provider("groq", "a"), llm.provider("openrouter", "b")]
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
    ids = llm.run_benchmark(conn, [llm.provider("groq", "a")], [("draft", "p1"), ("correct", "p2")])
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
    llm.run_benchmark(conn, [llm.provider("groq", "a"), llm.provider("openrouter", "b")], [("t", "p")])
    assert store.get_setting(conn, "llm_provider") is None
    assert store.get_setting(conn, "llm_model") is None
