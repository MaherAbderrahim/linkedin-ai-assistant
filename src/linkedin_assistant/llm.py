from __future__ import annotations

import abc
import sqlite3
import time
from dataclasses import dataclass

from . import store
from .db import transaction
from .hashing import sha256_text

# Contrat unique LLMProvider (ADR-08) : changement de fournisseur/modèle par
# paramètre, AUCUN appel réel en Phase 1 (adaptateurs simulés uniquement), aucun
# fallback payant, aucune sélection définitive avant les tests comparatifs.
# Le tableau llm_benchmarks enregistre latence/usage/sortie ; l'évaluation du
# français, des instructions et du style reste humaine (human_score).


class LLMError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class LLMResult:
    provider: str
    model: str
    text: str
    latency_ms: int
    usage: dict


class LLMProvider(abc.ABC):
    """Contrat d'adaptateur LLM.

    - `generate(task, prompt)` renvoie un `LLMResult` avec usage mesuré.
    - La sortie est traitée comme NON FIABLE : jamais une autorisation, un
      secret ni un envoi automatique.
    - Aucun adaptateur n'est autorisé à retomber silencieusement sur un
      fournisseur payant ; quota épuisé ⇒ arrêt explicite.
    """

    name: str = ""
    model: str = ""

    @abc.abstractmethod
    def generate(self, task: str, prompt: str) -> LLMResult: ...


class SimulatedProvider(LLMProvider):
    """Adaptateur simulé : aucune requête réseau, réponse déterministe marquée."""

    def __init__(self, name: str, model: str):
        self.name = name
        self.model = model

    def generate(self, task: str, prompt: str) -> LLMResult:
        start = time.perf_counter_ns()
        text = f"[SIMULATION {self.name}/{self.model}] {prompt[:160]}"
        latency_ms = (time.perf_counter_ns() - start) // 1_000_000
        return LLMResult(
            provider=self.name,
            model=self.model,
            text=text,
            latency_ms=latency_ms,
            usage={"simulated": True},
        )


PROVIDER_NAMES = ("groq", "openrouter")


def provider(name: str, model: str) -> LLMProvider:
    """Fabrique : seul le simulé existe en Phase 1 ; aucun appel réel ici."""
    if name not in PROVIDER_NAMES:
        raise LLMError("LLM_PROVIDER_UNKNOWN", f"fournisseur inconnu : {name}")
    return SimulatedProvider(name, model)


def run_benchmark(conn: sqlite3.Connection, providers: list[LLMProvider], tasks: list[tuple[str, str]]) -> list[str]:
    """Harness de comparaison : mêmes tâches pour chaque fournisseur.

    Enregistre une ligne par (fournisseur, tâche) dans llm_benchmarks :
    latence mesurée, usage déclaré, sortie intégrale pour évaluation humaine
    ultérieure. Aucun appel réseau : seul le contrat est éprouvé en Phase 1.
    """
    ids: list[str] = []
    now = store.utcnow()
    for candidate in providers:
        for task, prompt in tasks:
            started = time.perf_counter_ns()
            result = candidate.generate(task, prompt)
            elapsed_ms = (time.perf_counter_ns() - started) // 1_000_000
            bench_id = store.new_id()
            with transaction(conn):
                conn.execute(
                    "INSERT INTO llm_benchmarks (id, provider, model, task, prompt_hash, latency_ms, usage_json, output_text, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        bench_id,
                        result.provider,
                        result.model,
                        task,
                        sha256_text(prompt),
                        elapsed_ms,
                        store._json(result.usage),
                        result.text,
                        now,
                    ),
                )
            ids.append(bench_id)
    return ids


def score(conn: sqlite3.Connection, bench_id: str, human_score: int, notes: str = "") -> None:
    """Évaluation humaine (1 à 5) d'une sortie de benchmark."""
    if not isinstance(human_score, int) or isinstance(human_score, bool) or not (1 <= human_score <= 5):
        raise LLMError("INVALID_SCORE", "score humain attendu : entier de 1 à 5")
    row = conn.execute("SELECT id FROM llm_benchmarks WHERE id = ?", (bench_id,)).fetchone()
    if row is None:
        raise LLMError("BENCH_NOT_FOUND", bench_id)
    with transaction(conn):
        conn.execute(
            "UPDATE llm_benchmarks SET human_score = ?, human_notes = ? WHERE id = ?",
            (human_score, notes, bench_id),
        )


def results(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Résumé par fournisseur/modèle : volume, latence moyenne, score humain moyen."""
    return conn.execute(
        "SELECT provider, model, COUNT(*) AS runs, AVG(latency_ms) AS avg_latency_ms, "
        "AVG(human_score) AS avg_human_score, SUM(human_score IS NULL) AS unscored "
        "FROM llm_benchmarks GROUP BY provider, model ORDER BY provider, model"
    ).fetchall()
