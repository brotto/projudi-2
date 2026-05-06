"""
CLI entry point for ad-hoc tasks during POC.

Usage (from cejusc-pre/):
    python -m agente index               # index the entire Vault
    python -m agente search "<query>"    # ad-hoc retrieval test
    python -m agente stats               # collection counts
"""

from __future__ import annotations

import asyncio
import json
import sys

from .rag import collection_stats, index_vault, search


async def _run(cmd: str, args: list[str]) -> int:
    if cmd == "index":
        result = await index_vault()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    if cmd == "search":
        if not args:
            print("usage: python -m agente search '<query>'", file=sys.stderr)
            return 2
        hits = await search(" ".join(args))
        for h in hits:
            payload = h.get("payload", {})
            print(f"[{h.get('score'):.3f}] {payload.get('path')} · §{payload.get('section') or '(intro)'}")
            text = payload.get("text", "")
            preview = text[:200].replace("\n", " ")
            print(f"  {preview}...\n")
        return 0
    if cmd == "stats":
        print(json.dumps(await collection_stats(), indent=2, ensure_ascii=False, default=str))
        return 0
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    cmd, *args = sys.argv[1:]
    sys.exit(asyncio.run(_run(cmd, args)))


if __name__ == "__main__":
    main()
