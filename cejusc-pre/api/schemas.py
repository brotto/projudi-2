"""
Schemas de request/response da API — CEJUSC pré-processual.

Pydantic models para validação de entrada e serialização de saída.
Separados dos modelos de domínio para manter a API desacoplada.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


# ══════════════════════════════════════════════════════════════════════════
# Enums
# ══════════════════════════════════════════════════════════════════════════

class ModalidadeSchema(str, Enum):
    CONCILIACAO = "CONCILIACAO"
    MEDIACAO = "MEDIACAO"


class OpcaoCustasSchema(str, Enum):
    TAXA_PAGA = "TAXA_PAGA"
    PEDIDO_GRATUIDADE = "PEDIDO_GRATUIDADE"


class TipoPessoaSchema(str, Enum):
    FISICA = "FISICA"
    JURIDICA = "JURIDICA"


class ResultadoSessaoSchema(str, Enum):
    ACORDO = "ACORDO"
    SEM_ACORDO = "SEM_ACORDO"
    CONTINUACAO = "CONTINUACAO"
    AUSENCIA_RECLAMANTE = "AUSENCIA_RECLAMANTE"
    AUSENCIA_RECLAMADO = "AUSENCIA_RECLAMADO"
    AUSENCIA_AMBOS = "AUSENCIA_AMBOS"


# ══════════════════════════════════════════════════════════════════════════
# Reclamação
# ══════════════════════════════════════════════════════════════════════════

class EnderecoIn(BaseModel):
    logradouro: str
    numero: str
    complemento: str = ""
    bairro: str
    cidade: str
    uf: str
    cep: str


class ParteIn(BaseModel):
    nome: str
    tipo_pessoa: TipoPessoaSchema
    cpf: str | None = None
    cnpj: str | None = None
    email: str
    telefone: str
    endereco: EnderecoIn


class PedidoIn(BaseModel):
    descricao: str
    valor: Decimal


class ReclamacaoIn(BaseModel):
    """Request body para criar reclamação — art. 9º Res. 403/2023."""
    cejusc_destino: str
    reclamante: ParteIn
    reclamado: ParteIn
    fatos: str = Field(min_length=10)
    pedidos: list[PedidoIn] = Field(min_length=1)
    valor_causa: Decimal = Field(gt=0)
    modalidade: ModalidadeSchema
    opcao_custas: OpcaoCustasSchema


class ReclamacaoOut(BaseModel):
    """Response de reclamação."""
    id: str
    cejusc_destino: str
    reclamante: dict
    reclamado: dict
    fatos: str
    pedidos: list[dict]
    valor_causa: Decimal
    modalidade: str
    opcao_custas: str
    estado_atual: str
    protocolado_em: str | None = None


# ══════════════════════════════════════════════════════════════════════════
# Transição FSM
# ══════════════════════════════════════════════════════════════════════════

class TransicaoIn(BaseModel):
    """Request body para executar transição de estado."""
    estado_destino: str
    ator_id: str
    ator_tipo: str
    payload: dict = Field(default_factory=dict)


class TransicaoOut(BaseModel):
    """Response de transição executada."""
    id: str
    estado_anterior: str
    estado_novo: str
    ator_id: str
    ator_tipo: str
    timestamp: str
    hash: str


class EstadoOut(BaseModel):
    """Response do estado atual + transições válidas."""
    reclamacao_id: str
    estado_atual: str
    transicoes_validas: list[str]
    is_terminal: bool


# ══════════════════════════════════════════════════════════════════════════
# Sessão
# ══════════════════════════════════════════════════════════════════════════

class SessaoIn(BaseModel):
    """Request body para agendar sessão."""
    reclamacao_id: str
    conciliador_id: str
    conciliador_nome: str
    data_agendada: datetime


class ResultadoSessaoIn(BaseModel):
    """Request body para registrar resultado da sessão."""
    resultado: ResultadoSessaoSchema
    ata_conteudo: str = Field(min_length=10)
    reclamante_presente: bool
    reclamado_presente: bool
    observacoes: str = ""


class SessaoOut(BaseModel):
    id: str
    reclamacao_id: str
    numero_sessao: int
    conciliador_nome: str
    data_agendada: str
    resultado: str | None = None


# ══════════════════════════════════════════════════════════════════════════
# Acordo
# ══════════════════════════════════════════════════════════════════════════

class CondicaoIn(BaseModel):
    descricao: str
    parte_responsavel: str
    valor: Decimal | None = None
    forma_pagamento: str = ""


class AcordoIn(BaseModel):
    """Request body para registrar acordo."""
    reclamacao_id: str
    sessao_id: str
    condicoes: list[CondicaoIn] = Field(min_length=1)
    envolve_menores_incapazes: bool = False


class ParecerMPIn(BaseModel):
    """Request body para parecer do MP."""
    promotor_id: str
    promotor_nome: str
    favoravel: bool
    fundamentacao: str = Field(min_length=10)


class AcordoOut(BaseModel):
    id: str
    reclamacao_id: str
    sessao_id: str
    condicoes: list[dict]
    envolve_menores_incapazes: bool
    status: str
    valor_total: str
    pode_homologar: bool


# ══════════════════════════════════════════════════════════════════════════
# Automações
# ══════════════════════════════════════════════════════════════════════════

class CartaConviteOut(BaseModel):
    """Carta-convite gerada automaticamente."""
    reclamacao_id: str
    destinatario: str
    conteudo: str
    gerada_em: str


class CertidaoNegativaOut(BaseModel):
    """Certidão negativa gerada automaticamente."""
    reclamacao_id: str
    conteudo: str
    gerada_em: str


class PrazosOut(BaseModel):
    """Prazos computados para a reclamação."""
    reclamacao_id: str
    prazo_regularizacao: str | None = None
    prazo_max_sessao: str | None = None
    prazo_max_continuacao: str | None = None
    alertas: list[str] = Field(default_factory=list)
