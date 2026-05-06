"""
Modelos de sessão de conciliação/mediação — CEJUSC pré-processual.

art. 11–14 · Res. 403/2023:
- Sessão conduzida por conciliador/mediador designado
- Máximo 30 dias sem sessão (art. 14)
- Sessões continuadas até 60 dias no total (art. 14)
- Ausência de qualquer parte: arquivamento imediato (art. 12 §3º)
"""

from __future__ import annotations

from datetime import datetime, timedelta, UTC
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

from fsm.estados import PRAZO_MAX_CONTINUADA, PRAZO_MAX_SEM_SESSAO


class ResultadoSessao(str, Enum):
    """Resultado possível de uma sessão de conciliação/mediação."""
    ACORDO = "ACORDO"
    SEM_ACORDO = "SEM_ACORDO"
    CONTINUACAO = "CONTINUACAO"
    AUSENCIA_RECLAMANTE = "AUSENCIA_RECLAMANTE"
    AUSENCIA_RECLAMADO = "AUSENCIA_RECLAMADO"
    AUSENCIA_AMBOS = "AUSENCIA_AMBOS"


class SessaoCejusc(BaseModel):
    """
    Sessão de conciliação ou mediação — CEJUSC pré-processual.

    art. 11 · Res. 403/2023
    """
    id: UUID = Field(default_factory=uuid4)
    reclamacao_id: UUID
    numero_sessao: int = Field(ge=1)  # 1 = primeira, 2+ = continuação

    # Participantes
    conciliador_id: UUID
    conciliador_nome: str = Field(min_length=2)

    # Datas
    data_agendada: datetime
    data_realizada: datetime | None = None

    # Resultado
    resultado: ResultadoSessao | None = None

    # Ata — lavrada ao final da sessão (art. 13)
    ata: AtaSessao | None = None

    def verificar_prazo_agendamento(self, data_cadastro: datetime) -> bool:
        """
        Verifica se a sessão está dentro do prazo de 30 dias (art. 14).

        Returns:
            True se dentro do prazo, False se expirado.
        """
        return (self.data_agendada - data_cadastro) <= PRAZO_MAX_SEM_SESSAO

    def verificar_prazo_continuacao(self, data_primeira_sessao: datetime) -> bool:
        """
        Verifica se sessão continuada está dentro do prazo de 60 dias (art. 14).

        Returns:
            True se dentro do prazo, False se expirado.
        """
        if self.numero_sessao <= 1:
            return True
        return (self.data_agendada - data_primeira_sessao) <= PRAZO_MAX_CONTINUADA

    @property
    def is_ausencia(self) -> bool:
        """Verifica se houve ausência de qualquer parte."""
        if self.resultado is None:
            return False
        return self.resultado in {
            ResultadoSessao.AUSENCIA_RECLAMANTE,
            ResultadoSessao.AUSENCIA_RECLAMADO,
            ResultadoSessao.AUSENCIA_AMBOS,
        }


class AtaSessao(BaseModel):
    """
    Ata da sessão de conciliação/mediação.

    art. 13 · Res. 403/2023 — registra o que ocorreu na sessão.
    Lavrada pelo conciliador/mediador ao final da sessão.
    """
    id: UUID = Field(default_factory=uuid4)
    sessao_id: UUID
    conteudo: str = Field(min_length=10)

    # Presença das partes
    reclamante_presente: bool
    reclamado_presente: bool

    # Resultado registrado na ata
    resultado: ResultadoSessao
    observacoes: str = ""

    lavrada_em: datetime = Field(default_factory=lambda: datetime.now(UTC))
    lavrada_por_id: UUID  # conciliador/mediador
    lavrada_por_nome: str = Field(min_length=2)


# Atualizar referência forward para SessaoCejusc
SessaoCejusc.model_rebuild()
