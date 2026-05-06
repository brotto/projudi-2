"""
Modelo principal da reclamação pré-processual CEJUSC.

art. 9º · Res. 403/2023 — requisitos da reclamação:
- Centro CEJUSC destinatário
- Qualificação completa de ambas as partes
- Breve relato dos fatos
- Pedidos com especificações
- Valor da causa
- Opção: conciliação ou mediação
- Comprovante de taxa ou pedido de gratuidade
"""

from __future__ import annotations

from datetime import datetime, UTC
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

from juizo.exceptions import ErroValidacao
from juizo.fsm.engine import ResultadoValidacao
from juizo.models.pedidos import Pedido

from models.partes import ReclamanteCejusc, ReclamadoCejusc


class Modalidade(str, Enum):
    """Modalidade do procedimento — art. 9º V."""
    CONCILIACAO = "CONCILIACAO"
    MEDIACAO = "MEDIACAO"


class OpcaoCustas(str, Enum):
    """Opção de custas do solicitante."""
    TAXA_PAGA = "TAXA_PAGA"
    PEDIDO_GRATUIDADE = "PEDIDO_GRATUIDADE"


class ReclamacaoCejuscPre(BaseModel):
    """
    Reclamação pré-processual CEJUSC — objeto estruturado validável.

    Substitui o formulário/petição em texto livre por um objeto de dados
    com validação em tempo real. Cada campo inválido retorna erro específico.

    art. 9º · Res. 403/2023
    """
    id: UUID = Field(default_factory=uuid4)

    # art. 9º I — centro CEJUSC destinatário
    cejusc_destino: str = Field(min_length=1)

    # art. 9º II — partes com qualificação completa
    reclamante: ReclamanteCejusc
    reclamado: ReclamadoCejusc

    # art. 9º III — breve relato dos fatos
    fatos: str = Field(min_length=10)

    # art. 9º IV — pedidos com especificações
    pedidos: list[Pedido] = Field(min_length=1)

    # art. 9º IV — valor da causa
    valor_causa: Decimal = Field(gt=0)

    # art. 9º V — opção por conciliação ou mediação
    modalidade: Modalidade

    # art. 9º VI — comprovante de taxa ou pedido de gratuidade
    opcao_custas: OpcaoCustas

    # Metadados
    protocolado_em: datetime = Field(default_factory=lambda: datetime.now(UTC))
    numero_procedimento: str | None = None  # gerado na fase CADASTRADO

    @field_validator("valor_causa")
    @classmethod
    def _validar_valor_causa(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Valor da causa deve ser positivo")
        return v

    @model_validator(mode="after")
    def _validar_valor_causa_vs_pedidos(self) -> ReclamacaoCejuscPre:
        """Valor da causa deve ser >= soma dos pedidos."""
        soma_pedidos = sum(p.valor for p in self.pedidos)
        if self.valor_causa < soma_pedidos:
            raise ValueError(
                f"Valor da causa ({self.valor_causa}) não pode ser inferior "
                f"à soma dos pedidos ({soma_pedidos})"
            )
        return self

    def validar(self) -> ResultadoValidacao:
        """
        Validação completa da reclamação antes do protocolo.

        Retorna ResultadoValidacao com lista de erros específicos por campo.
        Usado pela API para retornar feedback granular ao solicitante.
        """
        erros: list[ErroValidacao] = []

        # Verifica se há pelo menos um pedido
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
                         f"à soma dos pedidos ({soma})",
                valor_recebido=self.valor_causa,
            ))

        if erros:
            return ResultadoValidacao.falha(erros)
        return ResultadoValidacao.sucesso()
