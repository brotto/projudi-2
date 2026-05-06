"""
Motor FSM genérico para qualquer rito processual do sistema Juízo.

Este módulo é agnóstico ao rito — recebe um dicionário de transições
e valida toda e qualquer tentativa de mudança de estado.

Uso:
    engine = FSMEngine(transicoes=TRANSICOES_CEJUSC, estado_inicial=EstadoCejusc.SOLICITACAO_RECEBIDA)
    engine.transicionar(estado_atual, nova_transicao, ator)
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, UTC
from typing import Any, Callable
import hashlib
import json

from juizo.exceptions import TransicaoInvalida, EstadoTerminal, AtorNaoAutorizado


@dataclass
class EventoTransicao:
    """
    Representa uma transição de estado — o commit do processo.
    Imutável após criação. Encadeado por hash (append-only log).
    """
    id: str
    processo_id: str
    estado_anterior: str
    estado_novo: str
    ator_id: str
    ator_tipo: str
    timestamp: datetime
    payload: dict[str, Any]
    hash_anterior: str   # hash do evento anterior — encadeamento imutável
    hash: str = ""       # calculado na criação

    def __post_init__(self) -> None:
        self.hash = self._calcular_hash()

    def _calcular_hash(self) -> str:
        conteudo = json.dumps({
            "id": self.id,
            "processo_id": self.processo_id,
            "estado_anterior": self.estado_anterior,
            "estado_novo": self.estado_novo,
            "ator_id": self.ator_id,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
            "hash_anterior": self.hash_anterior,
        }, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(conteudo.encode()).hexdigest()


@dataclass
class ResultadoValidacao:
    """Resultado de validação de um ato processual antes do protocolo."""
    ok: bool
    erros: list[Any]  # list[ErroValidacao]

    @classmethod
    def sucesso(cls) -> "ResultadoValidacao":
        return cls(ok=True, erros=[])

    @classmethod
    def falha(cls, erros: list[Any]) -> "ResultadoValidacao":
        return cls(ok=False, erros=erros)


class FSMEngine:
    """
    Motor de máquina de estados finitos para ritos processuais.

    - Valida transições contra o dicionário de transições do rito
    - Verifica autorização do ator para o estado atual
    - Executa atos automáticos registrados para cada transição
    - Gera EventoTransicao imutável com hash encadeado
    - Lança exceções descritivas para qualquer violação
    """

    def __init__(
        self,
        transicoes: dict[str, list[str]],
        estados_terminais: set[str],
        permissoes: dict[str, list[str]] | None = None,
        atos_automaticos: dict[tuple[str, str], list[Callable]] | None = None,
    ) -> None:
        self.transicoes = transicoes
        self.estados_terminais = estados_terminais
        self.permissoes = permissoes or {}
        self.atos_automaticos = atos_automaticos or {}

    def transicionar(
        self,
        estado_atual: str,
        estado_destino: str,
        ator_id: str,
        ator_tipo: str,
        processo_id: str,
        payload: dict[str, Any] | None = None,
        hash_anterior: str = "",
    ) -> EventoTransicao:
        """
        Executa uma transição de estado.

        Raises:
            EstadoTerminal: se o estado atual é terminal (frozen)
            TransicaoInvalida: se a transição não é permitida pelo FSM
            AtorNaoAutorizado: se o ator não tem permissão para esta transição
        """
        # 1. Verifica estado terminal
        if estado_atual in self.estados_terminais:
            raise EstadoTerminal(estado_atual)

        # 2. Verifica se transição é válida
        transicoes_validas = self.transicoes.get(estado_atual, [])
        if estado_destino not in transicoes_validas:
            raise TransicaoInvalida(
                estado_atual=estado_atual,
                transicao_tentada=estado_destino,
                transicoes_validas=transicoes_validas,
            )

        # 3. Verifica autorização do ator
        if self.permissoes:
            atores_permitidos = self.permissoes.get(estado_destino, [])
            if atores_permitidos and ator_tipo not in atores_permitidos:
                raise AtorNaoAutorizado(ator_tipo, estado_destino, estado_atual)

        # 4. Executa atos automáticos
        chave_ato = (estado_atual, estado_destino)
        for ato in self.atos_automaticos.get(chave_ato, []):
            ato(processo_id=processo_id, payload=payload or {})

        # 5. Gera evento imutável
        import uuid
        evento = EventoTransicao(
            id=str(uuid.uuid4()),
            processo_id=processo_id,
            estado_anterior=estado_atual,
            estado_novo=estado_destino,
            ator_id=ator_id,
            ator_tipo=ator_tipo,
            timestamp=datetime.now(UTC),
            payload=payload or {},
            hash_anterior=hash_anterior,
        )

        return evento

    def transicoes_validas(self, estado_atual: str) -> list[str]:
        """Retorna as transições válidas a partir do estado atual."""
        if estado_atual in self.estados_terminais:
            return []
        return self.transicoes.get(estado_atual, [])

    def is_terminal(self, estado: str) -> bool:
        return estado in self.estados_terminais
