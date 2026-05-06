"""
Dependencias da API — injecao de dependencias FastAPI.

Suporta dois backends de persistencia:
- In-memory (padrao): para testes e desenvolvimento rapido
- SQLAlchemy: ativado com variavel de ambiente JUIZO_USE_SQL=true

A flag USE_SQL permite alternar entre os backends sem alterar nenhum
endpoint da API — ambos implementam a mesma interface.
"""

from __future__ import annotations

import os

from api.store import EventStore, store


# ── Flag de seleção de backend ──
# Quando JUIZO_USE_SQL=true, usa SQLAlchemy ao inves do store in-memory.
# Default: false (manter testes existentes funcionando sem alteracao)
USE_SQL = os.getenv("JUIZO_USE_SQL", "false").lower() == "true"


def get_store() -> EventStore:
    """
    Retorna o repositorio de eventos.

    - USE_SQL=false (padrao): retorna EventStore in-memory (singleton)
    - USE_SQL=true: retorna EventStoreSql com sessao do banco

    Ambos implementam a mesma interface — as rotas nao sabem
    qual backend esta sendo usado.
    """
    if USE_SQL:
        from db.database import SessionLocal
        from db.store_sql import EventStoreSql
        session = SessionLocal()
        return EventStoreSql(session)

    return store
