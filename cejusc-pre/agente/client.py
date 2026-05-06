"""
LLM client — provider-agnostic facade over Ollama (POC) and OpenAI (future).

Exposes:
- chat(messages, model=None, **kwargs) -> str
- embed(text) -> list[float]

For now, only the Ollama provider is implemented. The interface keeps the door
open for a future OpenAI/Codex-API switch (ADR-008 was rejected for POC but
the abstraction is cheap to maintain).
"""

from __future__ import annotations

from typing import Any, Iterable

import httpx

from .config import CONFIG


# ─── HTTP timeouts ───────────────────────────────────────────────────────────
# Embeddings are fast (~500 tok/s). Chat with 14B Q4 on 8 vCPU is slow:
# realistic worst case is ~5-6 minutes for a 1500-token output.
EMBED_TIMEOUT = 30.0
CHAT_TIMEOUT = 600.0  # 10 min ceiling


class OllamaClient:
    """Thin client for the Ollama HTTP API."""

    def __init__(self, base_url: str | None = None) -> None:
        self._url = (base_url or CONFIG.ollama_url).rstrip("/")

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        **options: Any,
    ) -> str:
        """Run a chat completion. Returns the full assistant message text."""
        body = {
            "model": model or CONFIG.model_analyzer,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.2, **options},
        }
        async with httpx.AsyncClient(timeout=CHAT_TIMEOUT) as cli:
            r = await cli.post(f"{self._url}/api/chat", json=body)
            r.raise_for_status()
            data = r.json()
        return data.get("message", {}).get("content", "")

    async def embed(self, text: str, model: str | None = None) -> list[float]:
        """Return the embedding vector for a single text.

        nomic-embed-text has an 8K-token context. We defensively cap the input
        to ~6K characters (~1.5K tokens — safe margin for non-ascii PT-BR text)
        before calling the API. Truncation is rare in practice (Vault chunks
        are split to <=400 words), but very long sections in MANUAL PRÉ.md
        and similar can hit it.
        """
        body = {"model": model or CONFIG.model_embed, "prompt": text[:6000]}
        async with httpx.AsyncClient(timeout=EMBED_TIMEOUT) as cli:
            r = await cli.post(f"{self._url}/api/embeddings", json=body)
            r.raise_for_status()
            data = r.json()
        return data.get("embedding", [])

    async def embed_batch(
        self,
        texts: Iterable[str],
        model: str | None = None,
        on_error: str = "skip",  # "skip" | "raise" | "zero"
    ) -> list[list[float]]:
        """Embed a batch sequentially (Ollama doesn't expose true batching).

        Per-chunk error handling: an isolated 500 on Ollama shouldn't abort the
        whole indexing run. ``on_error`` controls behavior:
          - "skip": return [] for failed chunks (caller filters them)
          - "raise": propagate the exception (legacy behavior)
          - "zero": return a zero-vector placeholder
        """
        out: list[list[float]] = []
        for i, t in enumerate(texts):
            try:
                out.append(await self.embed(t, model=model))
            except httpx.HTTPError as e:
                if on_error == "raise":
                    raise
                # Best-effort logging via stderr (no logger import to keep deps light)
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


def make_client() -> OllamaClient:
    """Return the LLM client for the current provider.

    POC = Ollama only. The future OpenAI path will be added here.
    """
    if CONFIG.llm_provider != "ollama":
        raise NotImplementedError(
            f"LLM provider '{CONFIG.llm_provider}' not implemented yet "
            "(ADR-005 only ollama; ADR-008 was rejected)"
        )
    return OllamaClient()
