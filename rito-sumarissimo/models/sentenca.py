"""
Modelo de sentenca — Juizados Especiais Civeis.

art. 38-40 · Lei 9.099/95:
- Sentenca dispensada de relatorio (art. 38)
- Mencionara os elementos de convicao do juiz (art. 38)
- Irrecorrivel a sentenca de primeiro grau somente se homologatoria de acordo (art. 41)
- Recurso inominado para Turma Recursal em 10 dias (art. 42)
- Turma Recursal composta por 3 juizes togados (art. 41 §1o)
"""

from __future__ import annotations

from datetime import datetime, UTC
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class TipoSentenca(str, Enum):
    """Tipo de decisao proferida na sentenca — art. 38-40."""
    PROCEDENTE = "PROCEDENTE"
    IMPROCEDENTE = "IMPROCEDENTE"
    PARCIALMENTE_PROCEDENTE = "PARCIALMENTE_PROCEDENTE"
    EXTINCAO = "EXTINCAO"  # art. 51 — extincao sem resolucao de merito


class SentencaJEC(BaseModel):
    """
    Sentenca — Juizados Especiais Civeis.

    art. 38 · Lei 9.099/95:
    - Dispensada de relatorio
    - Mencionara os elementos de convicao do juiz
    - Indicara os motivos que formaram seu convencimento

    art. 39 — ineficaz a sentenca condenatoria que exceder a alçada
    dos Juizados (40 SM), valendo como titulo executivo ate o limite.
    """
    id: UUID = Field(default_factory=uuid4)
    processo_id: UUID

    # Tipo de decisao
    tipo: TipoSentenca

    # art. 38 — fundamentacao (elementos de convicao)
    fundamentacao: str = Field(min_length=10)

    # art. 38 — dispositivo (parte decisoria)
    dispositivo: str = Field(min_length=10)

    # Juiz prolator
    juiz_id: UUID
    juiz_nome: str = Field(min_length=2)

    # Valor da condenacao (quando aplicavel)
    valor_condenacao: Decimal | None = None

    # art. 41 — recorrivel (irrecorrivel se homologatoria de acordo)
    recorrivel: bool = True

    # Metadados
    proferida_em: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("valor_condenacao")
    @classmethod
    def _validar_valor_condenacao(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v < 0:
            raise ValueError("Valor da condenacao nao pode ser negativo")
        return v

    @property
    def is_merito(self) -> bool:
        """Verifica se a sentenca resolveu o merito."""
        return self.tipo != TipoSentenca.EXTINCAO

    @property
    def is_condenatoria(self) -> bool:
        """Verifica se a sentenca e condenatoria (com valor)."""
        return self.tipo in {
            TipoSentenca.PROCEDENTE,
            TipoSentenca.PARCIALMENTE_PROCEDENTE,
        } and self.valor_condenacao is not None and self.valor_condenacao > 0


class ResultadoRecurso(str, Enum):
    """Resultado do julgamento do recurso pela Turma Recursal."""
    PROVIDO = "PROVIDO"                        # reforma total
    PARCIALMENTE_PROVIDO = "PARCIALMENTE_PROVIDO"  # reforma parcial
    IMPROVIDO = "IMPROVIDO"                    # mantida a sentenca
    NAO_CONHECIDO = "NAO_CONHECIDO"            # recurso inadmissivel


class RecursoInominado(BaseModel):
    """
    Recurso inominado — art. 41-46 · Lei 9.099/95.

    art. 41 — da sentenca cabe recurso para a Turma Recursal
    art. 42 — prazo de 10 dias, por escrito, com razoes
    art. 46 — julgado em turma de 3 juizes togados
    """
    id: UUID = Field(default_factory=uuid4)
    processo_id: UUID
    sentenca_id: UUID

    # Recorrente
    recorrente_id: UUID
    recorrente_nome: str = Field(min_length=2)

    # Razoes do recurso
    razoes: str = Field(min_length=10)

    # Contrarrazoes (quando apresentadas)
    contrarrazoes: str | None = None

    # Resultado (preenchido apos julgamento)
    resultado: ResultadoRecurso | None = None

    # Turma Recursal
    relator_id: UUID | None = None
    relator_nome: str = ""

    # Datas
    interposto_em: datetime = Field(default_factory=lambda: datetime.now(UTC))
    julgado_em: datetime | None = None

    @property
    def is_julgado(self) -> bool:
        """Verifica se o recurso ja foi julgado."""
        return self.resultado is not None
