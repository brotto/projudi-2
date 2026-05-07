"""
LLM client — single facade with two backends:

    chat()  → OpenRouter (frontier API per ADR-008)
    embed() → Ollama nomic-embed-text (per ADR-005 fallback, embeddings only)

Why split: the project's TJPR-authorized stance is to use a frontier API for
reasoning/generation (latency + quality), while keeping embeddings on the
self-hosted infra to avoid re-indexing the Vault and to bound the data
that leaves the project for vector lookup (only the query, not chunks).

Environment:
    OPENROUTER_API_KEY   — required for chat()
    JUIZO_LLM_PROVIDER   — "openrouter" (default) or "ollama" (full fallback)
"""

from __future__ import annotations

import os
from typing import Any, Iterable

import httpx

from .config import CONFIG


# ─── HTTP timeouts ───────────────────────────────────────────────────────────
EMBED_TIMEOUT = 30.0       # nomic-embed-text is fast even on CPU
CHAT_TIMEOUT = 180.0       # frontier API typically <30s; allow headroom


class LLMClient:
    """Unified facade. Chat → OpenRouter, embed → Ollama."""

    def __init__(self) -> None:
        # OpenRouter setup
        self._or_url = CONFIG.openrouter_url.rstrip("/")
        self._or_key = os.getenv("OPENROUTER_API_KEY", "")
        # Ollama setup
        self._ollama_url = CONFIG.ollama_url.rstrip("/")

    # ── Chat ────────────────────────────────────────────────────────────────

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> str:
        """Run a chat completion via OpenRouter. Returns the full assistant text."""
        if not self._or_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. Export it or load from .dev.vars "
                "(see ADR-008 in the Vault for setup instructions)."
            )
        body: dict[str, Any] = {
            "model": model or CONFIG.model_analyzer,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        headers = {
            "Authorization": f"Bearer {self._or_key}",
            "Content-Type": "application/json",
            # OpenRouter ranking attribution — recommended, optional
            "HTTP-Referer": "https://github.com/brotto/projudi-2",
            "X-Title": "Sistema Juizo - CEJUSC Pre",
        }
        async with httpx.AsyncClient(timeout=CHAT_TIMEOUT) as cli:
            r = await cli.post(
                f"{self._or_url}/chat/completions", json=body, headers=headers
            )
            # Surfacing the actual error body — OpenRouter returns helpful JSON
            # explanations on 400/402/429/etc. that httpx.raise_for_status swallows.
            if r.status_code >= 400:
                try:
                    err_body = r.json()
                except Exception:
                    err_body = {"raw": r.text[:500]}
                raise RuntimeError(
                    f"OpenRouter HTTP {r.status_code}: {err_body}"
                )
            data = r.json()
        if "error" in data:
            raise RuntimeError(f"OpenRouter error: {data['error']}")
        return data["choices"][0]["message"]["content"]

    # ── Embeddings ──────────────────────────────────────────────────────────

    async def embed(self, text: str, model: str | None = None) -> list[float]:
        """Single-text embedding via Ollama. Caps input at 6K chars (see ADR-005)."""
        body = {"model": model or CONFIG.model_embed, "prompt": text[:6000]}
        async with httpx.AsyncClient(timeout=EMBED_TIMEOUT) as cli:
            r = await cli.post(f"{self._ollama_url}/api/embeddings", json=body)
            r.raise_for_status()
            data = r.json()
        return data.get("embedding", [])

    async def embed_batch(
        self,
        texts: Iterable[str],
        model: str | None = None,
        on_error: str = "skip",  # "skip" | "raise" | "zero"
    ) -> list[list[float]]:
        """Batch embeddings (sequential — Ollama doesn't expose true batching).

        Per-chunk error handling: an isolated 500 on Ollama shouldn't abort
        the whole indexing run. ``on_error`` controls behavior:
          - "skip": return [] for failed chunks (caller filters them)
          - "raise": propagate the exception
          - "zero": return a zero-vector placeholder
        """
        out: list[list[float]] = []
        for i, t in enumerate(texts):
            try:
                out.append(await self.embed(t, model=model))
            except httpx.HTTPError as e:
                if on_error == "raise":
                    raise
                import sys
                preview = t[:80].replace("\n", " ")
                print(
                    f"[embed_batch] chunk {i} failed ({e}); preview: {preview!r}",
                    file=sys.stderr,
                )
                if on_error == "zero":
                    out.append([0.0] * 768)
                else:  # skip
                    out.append([])
        return out


# ─── Public factory ──────────────────────────────────────────────────────────


def make_client() -> LLMClient:
    """Return the unified LLM client.

    Currently only the OpenRouter+Ollama hybrid is implemented. Full Ollama
    fallback (chat too) is preserved as a future path; see ADR-005 archived.
    """
    if CONFIG.llm_provider not in {"openrouter", "ollama"}:
        raise NotImplementedError(
            f"Unknown JUIZO_LLM_PROVIDER='{CONFIG.llm_provider}'. "
            "Use 'openrouter' (default) or 'ollama' (fallback)."
        )
    return LLMClient()
