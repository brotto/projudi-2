"""
Modelo da peticao inicial — Juizados Especiais Civeis.

art. 14 · Lei 9.099/95 — requisitos da peticao inicial:
- Qualificacao das partes
- Fatos e fundamentos de forma sucinta
- Objeto e seu valor
- Pedidos com especificacoes

Restricoes do rito sumarissimo:
- art. 3o I — valor da causa ate 40 salarios minimos
- art. 8o §1o — autor deve ser pessoa fisica (ou microempresa/EPP pelo art. 8o §1o)
- art. 9o — advogado facultativo ate 20 SM, obrigatorio acima
"""

from __future__ import annotations

from datetime import datetime, UTC
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

from juizo.exceptions import ErroValidacao
from juizo.fsm.engine import ResultadoValidacao
from juizo.models.partes import Advogado, Parte, TipoPessoa
from juizo.models.pedidos import Pedido

from fsm.estados import LIMITE_SEM_ADVOGADO, VALOR_MAXIMO_CAUSA


class AutorJEC(BaseModel):
    """
    Autor nos Juizados Especiais Civeis.

    art. 8o §1o — somente pessoas fisicas capazes podem ser autoras.
    Microempresas e empresas de pequeno porte tambem podem (art. 8o §1o II),
    mas neste MVP restringimos a pessoas fisicas.
    """
    parte: Parte
    advogado: Advogado | None = None  # art. 9o — facultativo ate 20 SM

    @model_validator(mode="after")
    def _validar_pessoa_fisica(self) -> AutorJEC:
        """art. 8o §1o — autor deve ser pessoa fisica."""
        if self.parte.tipo_pessoa != TipoPessoa.FISICA:
            raise ValueError(
                "Nos Juizados Especiais Civeis, o autor deve ser pessoa fisica "
                "(art. 8o §1o Lei 9.099/95)"
            )
        return self


class ReuJEC(BaseModel):
    """
    Reu nos Juizados Especiais Civeis.

    O reu pode ser pessoa fisica ou juridica — sem restricao.
    """
    parte: Parte
    advogado: Advogado | None = None


class PeticaoInicialJEC(BaseModel):
    """
    Peticao inicial — Juizados Especiais Civeis.

    Objeto estruturado validavel que substitui a peticao em texto livre.
    Cada campo invalido retorna erro especifico.

    art. 14 · Lei 9.099/95
    """
    id: UUID = Field(default_factory=uuid4)

    # art. 14 I — juizado destinatario
    juizado_destino: str = Field(min_length=1)

    # art. 14 II — partes com qualificacao completa
    autor: AutorJEC
    reu: ReuJEC

    # art. 14 III — fatos de forma sucinta
    fatos: str = Field(min_length=10)

    # art. 14 IV — pedidos com especificacoes
    pedidos: list[Pedido] = Field(min_length=1)

    # art. 14 V — valor da causa (max 40 SM — art. 3o I)
    valor_causa: Decimal = Field(gt=0)

    # Metadados
    protocolado_em: datetime = Field(default_factory=lambda: datetime.now(UTC))
    numero_processo: str | None = None  # gerado apos admissibilidade

    @field_validator("valor_causa")
    @classmethod
    def _validar_valor_causa(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Valor da causa deve ser positivo")
        # art. 3o I — ate 40 salarios minimos
        if v > VALOR_MAXIMO_CAUSA:
            raise ValueError(
                f"Valor da causa ({v}) excede o limite de 40 salarios minimos "
                f"(R$ {VALOR_MAXIMO_CAUSA}) para Juizados Especiais Civeis "
                f"(art. 3o I Lei 9.099/95)"
            )
        return v

    @model_validator(mode="after")
    def _validar_valor_causa_vs_pedidos(self) -> PeticaoInicialJEC:
        """Valor da causa deve ser >= soma dos pedidos."""
        soma_pedidos = sum(p.valor for p in self.pedidos)
        if self.valor_causa < soma_pedidos:
            raise ValueError(
                f"Valor da causa ({self.valor_causa}) nao pode ser inferior "
                f"a soma dos pedidos ({soma_pedidos})"
            )
        return self

    @model_validator(mode="after")
    def _validar_advogado_obrigatorio(self) -> PeticaoInicialJEC:
        """art. 9o — advogado obrigatorio acima de 20 SM."""
        if self.valor_causa > LIMITE_SEM_ADVOGADO and self.autor.advogado is None:
            raise ValueError(
                f"Advogado obrigatorio para causas acima de 20 salarios minimos "
                f"(R$ {LIMITE_SEM_ADVOGADO}) — art. 9o Lei 9.099/95"
            )
        return self

    def validar(self) -> ResultadoValidacao:
        """
        Validacao completa da peticao antes do protocolo.

        Retorna ResultadoValidacao com lista de erros especificos por campo.
        Usado pela API para retornar feedback granular ao autor.
        """
        erros: list[ErroValidacao] = []

        # Verifica se ha pelo menos um pedido
        if not self.pedidos:
            erros.append(ErroValidacao(
                campo="pedidos",
                mensagem="Pelo menos um pedido deve ser especificado",
            ))

        # Verifica valor da causa vs soma dos pedidos
        soma = sum(p.valor for p in self.pedidos)
        if self.valor_causa < soma:
            erros.append(ErroValidacao(
                campo="valor_causa",
                mensagem=f"Valor da causa ({self.valor_causa}) inferior "
                         f"a soma dos pedidos ({soma})",
                valor_recebido=self.valor_causa,
            ))

        # art. 3o I — valor maximo
        if self.valor_causa > VALOR_MAXIMO_CAUSA:
            erros.append(ErroValidacao(
                campo="valor_causa",
                mensagem=f"Valor excede limite de 40 SM (R$ {VALOR_MAXIMO_CAUSA})",
                valor_recebido=self.valor_causa,
            ))

        if erros:
            return ResultadoValidacao.falha(erros)
        return ResultadoValidacao.sucesso()
