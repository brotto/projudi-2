"""
RAG layer — Vault → chunks → embeddings → Qdrant; retrieve top-K for queries.

Implements only what the POC needs:
- index_vault(): walks the Vault, chunks markdown, embeds, upserts to Qdrant
- search(query, k): returns top-K matching chunks with metadata
- collection_stats(): vector count, status

A chunk = a section of a Vault page (split by '## ' header) OR the whole page
if shorter than chunk_max_words. Each chunk carries metadata sufficient to
cite the source back at the user (path, section title, type).
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from .client import make_client
from .config import CONFIG


# ─── Chunk model ─────────────────────────────────────────────────────────────


@dataclass
class Chunk:
    id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


# ─── Markdown chunking ───────────────────────────────────────────────────────

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
_H2_RE = re.compile(r"^## ", re.MULTILINE)


def _strip_frontmatter(md: str) -> tuple[str, dict[str, str]]:
    """Return (body, frontmatter_dict). Best-effort parse — frontmatter is YAML-ish."""
    m = _FRONTMATTER_RE.match(md)
    if not m:
        return md, {}
    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip().strip('"').strip("'")
    return md[m.end() :], fm


def _word_count(s: str) -> int:
    return len(s.split())


def chunk_markdown(path: Path, vault_root: Path) -> list[Chunk]:
    """Split a Vault page into chunks and attach metadata."""
    text = path.read_text(encoding="utf-8", errors="replace")
    body, fm = _strip_frontmatter(text)

    rel = path.relative_to(vault_root).as_posix()
    base_meta = {
        "path": rel,
        "filename": path.name,
        "type": fm.get("type", _guess_type(rel)),
        "tags": fm.get("tags", ""),
        "status": fm.get("status", ""),
    }

    # Split body by H2; keep the H1 (page title) prepended to every chunk for context.
    h1_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    h1_title = h1_match.group(1).strip() if h1_match else path.stem

    parts = _H2_RE.split(body)
    # parts[0] is everything before the first ## (intro); rest are sections.
    chunks: list[Chunk] = []
    sections = [("", parts[0])] + [_split_h2_section(p) for p in parts[1:]]

    for section_title, section_body in sections:
        full = (
            f"# {h1_title}\n## {section_title}\n\n{section_body}".strip()
            if section_title
            else f"# {h1_title}\n\n{section_body}".strip()
        )
        wc = _word_count(full)
        if wc < CONFIG.chunk_min_words and chunks:
            # Tiny section — append to previous chunk to keep useful context.
            chunks[-1].text += "\n\n" + full
            continue

        if wc <= CONFIG.chunk_max_words:
            chunks.append(_make_chunk(full, base_meta, h1_title, section_title))
        else:
            for sub in _hard_split(full, CONFIG.chunk_max_words):
                chunks.append(_make_chunk(sub, base_meta, h1_title, section_title))

    return chunks


def _split_h2_section(part: str) -> tuple[str, str]:
    """Given the text following a '## ' marker, return (title, body)."""
    nl = part.find("\n")
    if nl == -1:
        return part.strip(), ""
    return part[:nl].strip(), part[nl + 1 :].strip()


def _hard_split(text: str, max_words: int) -> list[str]:
    """Split at paragraph boundaries when a section exceeds max_words."""
    paragraphs = text.split("\n\n")
    out: list[str] = []
    cur: list[str] = []
    cur_words = 0
    for p in paragraphs:
        pw = _word_count(p)
        if cur_words + pw > max_words and cur:
            out.append("\n\n".join(cur))
            cur = [p]
            cur_words = pw
        else:
            cur.append(p)
            cur_words += pw
    if cur:
        out.append("\n\n".join(cur))
    return out


def _make_chunk(
    text: str, base_meta: dict[str, Any], page_title: str, section_title: str
) -> Chunk:
    h = hashlib.sha1(f"{base_meta['path']}::{section_title}::{text[:80]}".encode()).hexdigest()
    chunk_id = str(uuid.UUID(h[:32]))
    meta = {
        **base_meta,
        "page_title": page_title,
        "section": section_title,
    }
    return Chunk(id=chunk_id, text=text, metadata=meta)


def _guess_type(rel_path: str) -> str:
    """Heuristic when frontmatter doesn't say."""
    if rel_path.startswith("wiki/specs/"): return "spec"
    if rel_path.startswith("wiki/decisions/"): return "decision"
    if rel_path.startswith("wiki/workflows/"): return "workflow"
    if rel_path.startswith("wiki/integrations/"): return "integration"
    if rel_path.startswith("wiki/status/"): return "status"
    if rel_path.startswith("wiki/templates-rascunho/"): return "template-draft"
    if rel_path.startswith("raw/"): return "raw"
    if rel_path.startswith("Clippings/"): return "clipping"
    # Top-level templates (sentenças, decisões, etc.)
    if rel_path.endswith(".md") and "/" not in rel_path: return "template"
    return "other"


# ─── Qdrant operations ───────────────────────────────────────────────────────


async def _qdrant_upsert(chunks: list[Chunk], vectors: list[list[float]]) -> None:
    points = [
        {"id": c.id, "vector": v, "payload": {**c.metadata, "text": c.text}}
        for c, v in zip(chunks, vectors)
    ]
    url = f"{CONFIG.qdrant_url.rstrip('/')}/collections/{CONFIG.qdrant_collection}/points?wait=true"
    async with httpx.AsyncClient(timeout=60.0) as cli:
        r = await cli.put(url, json={"points": points})
        r.raise_for_status()


async def _qdrant_search(vector: list[float], k: int) -> list[dict[str, Any]]:
    url = f"{CONFIG.qdrant_url.rstrip('/')}/collections/{CONFIG.qdrant_collection}/points/search"
    async with httpx.AsyncClient(timeout=15.0) as cli:
        r = await cli.post(
            url,
            json={"vector": vector, "limit": k, "with_payload": True},
        )
        r.raise_for_status()
    return r.json().get("result", [])


async def collection_stats() -> dict[str, Any]:
    url = f"{CONFIG.qdrant_url.rstrip('/')}/collections/{CONFIG.qdrant_collection}"
    async with httpx.AsyncClient(timeout=10.0) as cli:
        r = await cli.get(url)
        r.raise_for_status()
    return r.json().get("result", {})


# ─── Public API ──────────────────────────────────────────────────────────────


async def index_vault(
    vault_path: str | None = None,
    skip_globs: tuple[str, ...] = (".obsidian/*", ".git/*"),
) -> dict[str, Any]:
    """Walk the Vault, chunk every .md, embed, upsert. Returns counts."""
    vault = Path(vault_path or CONFIG.vault_path).resolve()
    if not vault.is_dir():
        raise FileNotFoundError(f"Vault not found: {vault}")

    md_files = [p for p in vault.rglob("*.md") if not _matches_any(p, vault, skip_globs)]
    client = make_client()

    total_chunks = 0
    skipped_chunks = 0
    for md in md_files:
        chunks = chunk_markdown(md, vault)
        if not chunks:
            continue
        vectors = await client.embed_batch((c.text for c in chunks), on_error="skip")
        # Drop chunks where embedding failed (empty vector)
        ok = [(c, v) for c, v in zip(chunks, vectors) if v]
        skipped_chunks += len(chunks) - len(ok)
        if ok:
            await _qdrant_upsert([c for c, _ in ok], [v for _, v in ok])
            total_chunks += len(ok)

    stats = await collection_stats()
    return {
        "files_indexed": len(md_files),
        "chunks_indexed": total_chunks,
        "chunks_skipped": skipped_chunks,
        "collection_status": stats.get("status"),
        "vectors_total": stats.get("points_count", stats.get("vectors_count")),
    }


async def search(query: str, k: int | None = None) -> list[dict[str, Any]]:
    """Embed the query, return top-K matching chunks (with payload + score)."""
    client = make_client()
    vec = await client.embed(query)
    return await _qdrant_search(vec, k or CONFIG.rag_top_k)


def _matches_any(path: Path, root: Path, globs: tuple[str, ...]) -> bool:
    rel = path.relative_to(root).as_posix()
    return any(Path(rel).match(g) for g in globs)
