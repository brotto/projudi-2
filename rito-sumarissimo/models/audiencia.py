"""
Modelos de audiencia — Juizados Especiais Civeis.

art. 21-29 · Lei 9.099/95:
- Audiencia de conciliacao obrigatoria (art. 21)
- Conduzida por conciliador sob orientacao do juiz (art. 22)
- Audiencia de instrucao e julgamento presidida pelo juiz (art. 27-29)
- Oitiva de partes e testemunhas (max 3 por parte — art. 34)
"""

from __future__ import annotations

from datetime import datetime, UTC
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TipoAudiencia(str, Enum):
    """Tipo de audiencia no rito sumarissimo."""
    CONCILIACAO = "CONCILIACAO"   # art. 21-22
    INSTRUCAO = "INSTRUCAO"      # art. 27-29


class ResultadoAudiencia(str, Enum):
    """Resultado possivel de uma audiencia."""
    ACORDO = "ACORDO"
    SEM_ACORDO = "SEM_ACORDO"
    INSTRUCAO_CONCLUIDA = "INSTRUCAO_CONCLUIDA"
    AUSENCIA_AUTOR = "AUSENCIA_AUTOR"
    AUSENCIA_REU = "AUSENCIA_REU"
    REVELIA = "REVELIA"           # art. 20 — reu ausente, efeitos da revelia
    DESISTENCIA = "DESISTENCIA"   # art. 51 I


class AudienciaJEC(BaseModel):
    """
    Audiencia no rito sumarissimo — Juizados Especiais Civeis.

    art. 21 — a conciliacao e obrigatoria e precede qualquer instrucao.
    art. 27-29 — audiencia de instrucao e julgamento presidida pelo juiz.
    """
    id: UUID = Field(default_factory=uuid4)
    processo_id: UUID
    tipo: TipoAudiencia

    # Participantes
    # Conciliacao: conduzida por conciliador (art. 22)
    # Instrucao: presidida por juiz togado ou leigo (art. 27)
    condutor_id: UUID
    condutor_nome: str = Field(min_length=2)

    # Datas
    data_designada: datetime
    data_realizada: datetime | None = None

    # Resultado
    resultado: ResultadoAudiencia | None = None

    # Ata — registro do que ocorreu (art. 36)
    ata: AtaAudienciaJEC | None = None

    @property
    def is_conciliacao(self) -> bool:
        """Verifica se e audiencia de conciliacao."""
        return self.tipo == TipoAudiencia.CONCILIACAO

    @property
    def is_instrucao(self) -> bool:
        """Verifica se e audiencia de instrucao."""
        return self.tipo == TipoAudiencia.INSTRUCAO

    @property
    def is_ausencia(self) -> bool:
        """Verifica se houve ausencia de qualquer parte."""
        if self.resultado is None:
            return False
        return self.resultado in {
            ResultadoAudiencia.AUSENCIA_AUTOR,
            ResultadoAudiencia.AUSENCIA_REU,
            ResultadoAudiencia.REVELIA,
        }


class AtaAudienciaJEC(BaseModel):
    """
    Ata de audiencia — Juizados Especiais Civeis.

    art. 36 · Lei 9.099/95 — registro sucinto dos atos essenciais.
    Dispensados o relatorio e a fundamentacao extensa.
    """
    id: UUID = Field(default_factory=uuid4)
    audiencia_id: UUID
    conteudo: str = Field(min_length=10)

    # Presenca das partes
    autor_presente: bool
    reu_presente: bool

    # Resultado registrado na ata
    resultado: ResultadoAudiencia
    observacoes: str = ""

    lavrada_em: datetime = Field(default_factory=lambda: datetime.now(UTC))
    lavrada_por_id: UUID  # conciliador ou juiz
    lavrada_por_nome: str = Field(min_length=2)


# Atualizar referencia forward para AudienciaJEC
AudienciaJEC.model_rebuild()
