from __future__ import annotations

import abc
import json
import os
import sqlite3
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from . import store
from .db import transaction
from .hashing import sha256_text

# Contrat unique LLMProvider (ADR-08) : changement de fournisseur/modèle par
# paramètre, aucun fallback payant, aucune sélection définitive avant les
# tests comparatifs.
# Le tableau llm_benchmarks enregistre latence/usage/sortie ; l'évaluation du
# français, des instructions et du style reste humaine (human_score).
#
# Adaptateurs réels : Groq et OpenRouter (API compatible OpenAI, endpoints
# distincts, clés dans `.env`). Règles inchangées : quota épuisé = arrêt
# explicite, aucun basculement automatique vers une variante payante, la
# sortie du modèle n'est jamais une autorisation.

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LinkedInAssistant-local/0.1"
DEFAULT_TIMEOUT = 60.0


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
    #: `True` si l'appel part vers un service distant réel (usage réseau,
    #: quota, données transmises). `False` pour les adaptateurs simulés.
    is_real: bool = False

    @abc.abstractmethod
    def generate(self, task: str, prompt: str) -> LLMResult: ...


class SimulatedProvider(LLMProvider):
    """Adaptateur simulé : aucune requête réseau, réponse déterministe marquée."""

    is_real = False

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


class HTTPChatProvider(LLMProvider):
    """Adaptateur réel : API compatible OpenAI (chat/completions).

    - Un seul appel, pas de réessai automatique : une erreur réseau ou un
      quota épuisé est un arrêt, jamais une relance ni un changement de
      fournisseur.
    - Le quota épuisé (429) est un arrêt explicite : aucun passage à une
      offre payante, aucun « crédit de bienvenue » présenté comme gratuit.
    - La clé n'est jamais journalisée ni inclusion dans l'erreur retournée.
    """

    is_real = True

    def __init__(
        self,
        name: str,
        model: str,
        api_key: str,
        base_url: str,
        *,
        system_prompt: str = "",
        max_tokens: int = 2048,
        temperature: float = 0.7,
        extra_headers: dict | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        if not api_key or not api_key.strip():
            raise LLMError("LLM_KEY_MISSING", f"clé absente pour le fournisseur {name}")
        if not model or not model.strip():
            raise LLMError("LLM_MODEL_MISSING", "modèle non choisi explicitement")
        self.name = name
        self.model = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._system_prompt = system_prompt
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._extra_headers = extra_headers or {}
        self._timeout = timeout

    def generate(self, task: str, prompt: str) -> LLMResult:
        messages = []
        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
            "User-Agent": USER_AGENT,
        }
        headers.update(self._extra_headers)
        request = urllib.request.Request(
            f"{self._base_url}/chat/completions", data=body, headers=headers, method="POST"
        )
        start = time.perf_counter_ns()
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            latency_ms = (time.perf_counter_ns() - start) // 1_000_000
            self._raise_http(exc.code, exc)
            raise AssertionError("unreachable")  # pragma: no cover
        except (OSError, urllib.error.URLError) as exc:
            raise LLMError(
                "LLM_UNAVAILABLE", f"{self.name} injoignable : {type(exc).__name__}"
            ) from exc
        latency_ms = (time.perf_counter_ns() - start) // 1_000_000
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LLMError("LLM_BAD_RESPONSE", f"{self.name} : réponse illisible") from exc
        return LLMResult(
            provider=self.name,
            model=self.model,
            text=self._extract_text(data),
            latency_ms=latency_ms,
            usage=self._extract_usage(data),
        )

    def _raise_http(self, status: int, exc: urllib.error.HTTPError) -> None:
        if status == 429:
            raise LLMError(
                "LLM_QUOTA",
                f"{self.name} : quota épuisé ou limite de débit atteinte — arrêt, aucun passage à une offre payante",
            ) from exc
        if status in (401, 403):
            raise LLMError("LLM_AUTH", f"{self.name} : clé refusée") from exc
        if status == 404:
            raise LLMError("LLM_MODEL_UNKNOWN", f"{self.name} : modèle indisponible ({self.model})") from exc
        if 400 <= status < 500:
            raise LLMError("LLM_BAD_REQUEST", f"{self.name} : requête refusée (HTTP {status})") from exc
        raise LLMError("LLM_UNAVAILABLE", f"{self.name} : erreur serveur (HTTP {status})") from exc

    def _extract_text(self, data: dict) -> str:
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("LLM_BAD_RESPONSE", f"{self.name} : contenu absent") from exc
        if isinstance(content, list):  # certains modèles renvoient des fragments
            content = "".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
        if not isinstance(content, str) or not content.strip():
            raise LLMError("LLM_EMPTY_OUTPUT", f"{self.name} : réponse vide")
        return content.strip()

    @staticmethod
    def _extract_usage(data: dict) -> dict:
        usage = data.get("usage")
        if not isinstance(usage, dict):
            return {}
        return {
            key: usage[key]
            for key in ("prompt_tokens", "completion_tokens", "total_tokens")
            if key in usage
        }


class GroqProvider(HTTPChatProvider):
    """Groq (offre gratuite documentée, clé `GROQ_API_KEY`)."""

    def __init__(self, model: str, api_key: str | None = None, **kwargs):
        super().__init__(
            name="groq",
            model=model,
            api_key=api_key if api_key is not None else os.environ.get("GROQ_API_KEY", ""),
            base_url="https://api.groq.com/openai/v1",
            **kwargs,
        )


class OpenRouterProvider(HTTPChatProvider):
    """OpenRouter — variantes `:free` uniquement par défaut.

    Le budget validé est 0 € : un modèle payant ne peut pas être choisi
    silencieusement. Le garde-fou est ici, pas dans une configuration :
    `allow_paid=False` refuse tout identifiant sans `:free`.
    """

    def __init__(self, model: str, api_key: str | None = None, allow_paid: bool = False, **kwargs):
        resolved = api_key if api_key is not None else os.environ.get("OPENROUTER_API_KEY", "")
        if not allow_paid and ":free" not in model:
            raise LLMError(
                "LLM_MODEL_NOT_FREE",
                f"modèle OpenRouter payant refusé (budget 0 €) : {model} — utiliser une variante ':free'",
            )
        super().__init__(
            name="openrouter",
            model=model,
            api_key=resolved,
            base_url="https://openrouter.ai/api/v1",
            **kwargs,
        )


PROVIDER_NAMES = ("groq", "openrouter")


def provider(name: str, model: str) -> LLMProvider:
    """Fabrique d'adaptateur LLM réel.

    Le fournisseur est choisi par paramètre (`llm_provider`/`llm_model`) :
    aucun modèle n'est figé dans le code et aucun fournisseur payant n'est
    appelé par défaut. Sans clé, l'adaptateur simulé est renvoyé (mode hors
    ligne, aucun appel réseau).
    """
    if name not in PROVIDER_NAMES:
        raise LLMError("LLM_PROVIDER_UNKNOWN", f"fournisseur inconnu : {name}")
    if name == "groq":
        if not os.environ.get("GROQ_API_KEY", "").strip():
            return SimulatedProvider(name, model)
        return GroqProvider(model)
    if not os.environ.get("OPENROUTER_API_KEY", "").strip():
        return SimulatedProvider(name, model)
    return OpenRouterProvider(model)


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
