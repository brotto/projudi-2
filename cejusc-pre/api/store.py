"""
Repositório in-memory com Event Sourcing — MVP.

Em produção: PostgreSQL para o event log + Redis para cache de estado.
No MVP: dicionários em memória com a mesma interface.

O estado atual de cada reclamação é SEMPRE derivado do log de eventos.
Nenhum evento é deletado — apenas append.
"""

from __future__ import annotations

from datetime import datetime, UTC
from uuid import UUID, uuid4
from typing import Any

from juizo.fsm.engine import EventoTransicao

from fsm.engine import engine as fsm_engine
from fsm.estados import EstadoCejusc


class EventStore:
    """
    Repositório central de eventos — append-only log.

    Segue o padrão Event Sourcing (ADR-001):
    - Eventos são a fonte de verdade
    - Estado atual é derivado/cacheado
    - Nenhum evento é editado ou deletado
    """

    def __init__(self) -> None:
        # Event log: reclamacao_id -> [eventos]
        self._eventos: dict[UUID, list[EventoTransicao]] = {}
        # Estado atual cacheado: reclamacao_id -> estado
        self._estados: dict[UUID, str] = {}
        # Dados da reclamação: reclamacao_id -> dados
        self._reclamacoes: dict[UUID, dict[str, Any]] = {}
        # Sessões: sessao_id -> dados
        self._sessoes: dict[UUID, dict[str, Any]] = {}
        # Acordos: acordo_id -> dados
        self._acordos: dict[UUID, dict[str, Any]] = {}

    # ── Reclamações ──

    def criar_reclamacao(self, reclamacao_id: UUID, dados: dict[str, Any]) -> EventoTransicao:
        """Cria reclamação e registra evento SOLICITACAO_RECEBIDA."""
        self._reclamacoes[reclamacao_id] = dados
        self._estados[reclamacao_id] = EstadoCejusc.SOLICITACAO_RECEBIDA
        self._eventos[reclamacao_id] = []

        evento = EventoTransicao(
            id=str(uuid4()),
            processo_id=str(reclamacao_id),
            estado_anterior="",
            estado_novo=EstadoCejusc.SOLICITACAO_RECEBIDA,
            ator_id=dados.get("ator_id", "sistema"),
            ator_tipo=dados.get("ator_tipo", "PARTE"),
            timestamp=datetime.now(UTC),
            payload={"tipo": "protocolo_reclamacao"},
            hash_anterior="",
        )
        self._eventos[reclamacao_id].append(evento)
        return evento

    def transicionar(
        self,
        reclamacao_id: UUID,
        estado_destino: str,
        ator_id: str,
        ator_tipo: str,
        payload: dict[str, Any] | None = None,
    ) -> EventoTransicao:
        """Executa transição FSM e registra evento no log."""
        estado_atual = self._estados[reclamacao_id]
        eventos = self._eventos[reclamacao_id]
        hash_anterior = eventos[-1].hash if eventos else ""

        evento = fsm_engine.transicionar(
            estado_atual=estado_atual,
            estado_destino=estado_destino,
            ator_id=ator_id,
            ator_tipo=ator_tipo,
            processo_id=str(reclamacao_id),
            payload=payload or {},
            hash_anterior=hash_anterior,
        )

        self._eventos[reclamacao_id].append(evento)
        self._estados[reclamacao_id] = estado_destino
        return evento

    def get_reclamacao(self, reclamacao_id: UUID) -> dict[str, Any] | None:
        dados = self._reclamacoes.get(reclamacao_id)
        if dados is None:
            return None
        return {
            **dados,
            "id": str(reclamacao_id),
            "estado_atual": self._estados[reclamacao_id],
        }

    def listar_reclamacoes(self) -> list[dict[str, Any]]:
        return [
            {
                **dados,
                "id": str(rid),
                "estado_atual": self._estados[rid],
            }
            for rid, dados in self._reclamacoes.items()
        ]

    def get_historico(self, reclamacao_id: UUID) -> list[dict[str, Any]]:
        eventos = self._eventos.get(reclamacao_id, [])
        return [
            {
                "id": e.id,
                "estado_anterior": e.estado_anterior,
                "estado_novo": e.estado_novo,
                "ator_id": e.ator_id,
                "ator_tipo": e.ator_tipo,
                "timestamp": e.timestamp.isoformat(),
                "payload": e.payload,
                "hash": e.hash,
            }
            for e in eventos
        ]

    def get_estado(self, reclamacao_id: UUID) -> str | None:
        return self._estados.get(reclamacao_id)

    def get_transicoes_validas(self, reclamacao_id: UUID) -> list[str]:
        estado = self._estados.get(reclamacao_id)
        if estado is None:
            return []
        return fsm_engine.transicoes_validas(estado)

    # ── Sessões ──

    def criar_sessao(self, sessao_id: UUID, dados: dict[str, Any]) -> None:
        self._sessoes[sessao_id] = dados

    def get_sessao(self, sessao_id: UUID) -> dict[str, Any] | None:
        dados = self._sessoes.get(sessao_id)
        if dados is None:
            return None
        return {**dados, "id": str(sessao_id)}

    def listar_sessoes(self, reclamacao_id: UUID | None = None) -> list[dict[str, Any]]:
        sessoes = [
            {**dados, "id": str(sid)}
            for sid, dados in self._sessoes.items()
        ]
        if reclamacao_id:
            sessoes = [s for s in sessoes if s.get("reclamacao_id") == str(reclamacao_id)]
        return sessoes

    def atualizar_sessao(self, sessao_id: UUID, dados: dict[str, Any]) -> None:
        if sessao_id in self._sessoes:
            self._sessoes[sessao_id].update(dados)

    # ── Acordos ──

    def criar_acordo(self, acordo_id: UUID, dados: dict[str, Any]) -> None:
        self._acordos[acordo_id] = dados

    def get_acordo(self, acordo_id: UUID) -> dict[str, Any] | None:
        dados = self._acordos.get(acordo_id)
        if dados is None:
            return None
        return {**dados, "id": str(acordo_id)}

    def atualizar_acordo(self, acordo_id: UUID, dados: dict[str, Any]) -> None:
        if acordo_id in self._acordos:
            self._acordos[acordo_id].update(dados)


# Instância singleton — usada pela API
store = EventStore()
