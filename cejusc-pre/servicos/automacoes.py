"""
Automações do CEJUSC pré-processual — Res. 403/2023.

Geração automática de documentos e cálculo de prazos:
- Carta-convite ao reclamado (art. 10º III/IV)
- Certidão negativa de conciliação (art. 12 §3º)
- Ata de sessão (com e sem acordo)
- Cálculo de prazos legais (art. 9º §2º, art. 14)
"""

from __future__ import annotations

from datetime import datetime, timedelta, UTC
from typing import Any

from fsm.estados import (
    PRAZO_MAX_CONTINUADA,
    PRAZO_MAX_SEM_SESSAO,
    PRAZO_REGULARIZACAO,
)


# ── Carta-Convite ────────────────────────────────────────────────────────


def gerar_carta_convite(reclamacao: dict[str, Any]) -> dict[str, Any]:
    """
    Gera carta-convite ao reclamado — art. 10º III/IV.

    A carta é gerada automaticamente ao transicionar para
    NOTIFICACOES_ENVIADAS, contendo os dados necessários para
    que o reclamado compareça à sessão de conciliação/mediação.
    """
    reclamado = reclamacao.get("reclamado", {})
    reclamante = reclamacao.get("reclamante", {})
    modalidade = reclamacao.get("modalidade", "CONCILIACAO")

    modalidade_texto = (
        "conciliação" if modalidade == "CONCILIACAO" else "mediação"
    )

    conteudo = f"""CARTA-CONVITE — CEJUSC PRÉ-PROCESSUAL

Ao(À) Sr(a). {reclamado.get('nome', '[nome do reclamado]')},

Comunicamos que foi apresentada reclamação pré-processual perante
o {reclamacao.get('cejusc_destino', 'CEJUSC')}, formulada por
{reclamante.get('nome', '[nome do reclamante]')}.

Modalidade: {modalidade_texto.upper()}

Convidamos V. Sa. a comparecer à sessão de {modalidade_texto}
que será designada, a fim de buscar solução consensual para
a questão apresentada.

O comparecimento é voluntário, não induzindo prevenção,
não interrompendo prescrição, não constituindo em mora,
não tornando coisa litigiosa e não vinculando as partes
a propostas eventualmente apresentadas (art. 4º, Res. 403/2023).

Breve relato dos fatos:
{reclamacao.get('fatos', '[fatos]')}

Pedidos:
{_formatar_pedidos(reclamacao.get('pedidos', []))}

Caso deseje informações adicionais, entre em contato com o CEJUSC.

Atenciosamente,
Secretaria do CEJUSC"""

    return {
        "reclamacao_id": reclamacao.get("id", ""),
        "destinatario": reclamado.get("nome", ""),
        "conteudo": conteudo,
        "gerada_em": datetime.now(UTC).isoformat(),
    }


def _formatar_pedidos(pedidos: list[dict]) -> str:
    """Formata a lista de pedidos para a carta-convite."""
    if not pedidos:
        return "  - [sem pedidos especificados]"
    linhas = []
    for i, p in enumerate(pedidos, 1):
        desc = p.get("descricao", "")
        valor = p.get("valor", "")
        linhas.append(f"  {i}. {desc}" + (f" — R$ {valor}" if valor else ""))
    return "\n".join(linhas)


# ── Certidão Negativa ────────────────────────────────────────────────────


def gerar_certidao_negativa(reclamacao: dict[str, Any]) -> dict[str, Any]:
    """
    Gera certidão negativa de conciliação — art. 12 §3º.

    Emitida quando a sessão é infrutífera (sem acordo).
    Certifica que:
    - Não induz prevenção (art. 4º)
    - Não interrompe prescrição (art. 4º)
    - Não constitui em mora (art. 4º)
    """
    reclamante = reclamacao.get("reclamante", {})
    reclamado = reclamacao.get("reclamado", {})

    conteudo = f"""CERTIDÃO NEGATIVA DE CONCILIAÇÃO/MEDIAÇÃO
CEJUSC Pré-Processual — Res. 403/2023 NUPEMEC TJPR

CERTIFICO que a reclamação pré-processual registrada sob
ID {reclamacao.get('id', '[ID]')}, apresentada por
{reclamante.get('nome', '[reclamante]')} em face de
{reclamado.get('nome', '[reclamado]')}, tramitou perante o
{reclamacao.get('cejusc_destino', 'CEJUSC')}, tendo sido
INFRUTÍFERA a tentativa de solução consensual.

CERTIFICO, ainda, nos termos do art. 4º da Res. 403/2023, que:
  I   - O procedimento NÃO induziu prevenção;
  II  - O procedimento NÃO interrompeu prescrição;
  III - O procedimento NÃO constituiu em mora;
  IV  - O procedimento NÃO tornou coisa litigiosa;
  V   - As propostas eventualmente apresentadas durante as sessões
        NÃO vinculam as partes, somente o acordo devidamente assinado.

As partes ficam livres para buscar a tutela jurisdicional
pelos meios próprios.

Data: {datetime.now(UTC).strftime('%d/%m/%Y às %H:%M UTC')}

Secretaria do CEJUSC"""

    return {
        "reclamacao_id": reclamacao.get("id", ""),
        "conteudo": conteudo,
        "gerada_em": datetime.now(UTC).isoformat(),
    }


# ── Ata de Sessão ────────────────────────────────────────────────────────


def gerar_ata_sessao(
    reclamacao: dict[str, Any],
    sessao: dict[str, Any],
    resultado: str,
    ata_conteudo: str = "",
) -> str:
    """Gera ata de sessão de conciliação/mediação — art. 12–13."""
    reclamante = reclamacao.get("reclamante", {})
    reclamado = reclamacao.get("reclamado", {})

    resultado_texto = {
        "ACORDO": "FRUTÍFERA — Acordo obtido",
        "SEM_ACORDO": "INFRUTÍFERA — Sem acordo",
        "CONTINUACAO": "CONTINUAÇÃO — Nova sessão necessária",
        "AUSENCIA_RECLAMANTE": "PREJUDICADA — Ausência do reclamante",
        "AUSENCIA_RECLAMADO": "PREJUDICADA — Ausência do reclamado",
        "AUSENCIA_AMBOS": "PREJUDICADA — Ausência de ambas as partes",
    }.get(resultado, resultado)

    ata = f"""ATA DE SESSÃO DE {sessao.get('modalidade', 'CONCILIAÇÃO/MEDIAÇÃO').upper()}
CEJUSC Pré-Processual — Res. 403/2023

Sessão nº {sessao.get('numero_sessao', 1)}
Reclamação ID: {reclamacao.get('id', '[ID]')}
Data: {sessao.get('data_agendada', '[data]')}
Conciliador/Mediador: {sessao.get('conciliador_nome', '[nome]')}

PARTES:
  Reclamante: {reclamante.get('nome', '[reclamante]')}
  Reclamado: {reclamado.get('nome', '[reclamado]')}

RESULTADO: {resultado_texto}

CONTEÚDO:
{ata_conteudo if ata_conteudo else '[Sem registro adicional]'}

Registrado em: {datetime.now(UTC).strftime('%d/%m/%Y às %H:%M UTC')}
"""
    return ata


# ── Cálculo de Prazos ────────────────────────────────────────────────────


def calcular_prazos(
    reclamacao: dict[str, Any],
    data_protocolo: datetime | None = None,
    data_primeira_sessao: datetime | None = None,
) -> dict[str, Any]:
    """
    Calcula prazos legais da reclamação — art. 9º §2º, art. 14.

    Prazos:
    - Regularização: 5 dias corridos (art. 9º §2º)
    - Máx. sem sessão: 30 dias corridos (art. 14)
    - Máx. com continuação: 60 dias corridos (art. 14)

    Retorna datas-limite e alertas se prazos estão vencendo.
    """
    agora = datetime.now(UTC)
    alertas: list[str] = []

    # art. 9º §2º — prazo para regularização
    prazo_regularizacao = None
    if data_protocolo:
        prazo_regularizacao = data_protocolo + PRAZO_REGULARIZACAO
        if agora > prazo_regularizacao:
            alertas.append(
                "⚠ Prazo de regularização EXPIRADO "
                f"(art. 9º §2º — {PRAZO_REGULARIZACAO.days} dias)"
            )
        elif (prazo_regularizacao - agora).days <= 2:
            alertas.append(
                "⚠ Prazo de regularização vence em "
                f"{(prazo_regularizacao - agora).days} dia(s)"
            )

    # art. 14 — prazo máximo sem sessão (30 dias)
    prazo_max_sessao = None
    if data_protocolo:
        prazo_max_sessao = data_protocolo + PRAZO_MAX_SEM_SESSAO
        if data_primeira_sessao is None and agora > prazo_max_sessao:
            alertas.append(
                "⚠ Prazo máximo sem sessão EXPIRADO "
                f"(art. 14 — {PRAZO_MAX_SEM_SESSAO.days} dias)"
            )

    # art. 14 — prazo máximo com continuação (60 dias)
    prazo_max_continuacao = None
    if data_primeira_sessao:
        prazo_max_continuacao = data_primeira_sessao + PRAZO_MAX_CONTINUADA
        if agora > prazo_max_continuacao:
            alertas.append(
                "⚠ Prazo máximo para sessões continuadas EXPIRADO "
                f"(art. 14 — {PRAZO_MAX_CONTINUADA.days} dias)"
            )

    return {
        "reclamacao_id": reclamacao.get("id", ""),
        "prazo_regularizacao": (
            prazo_regularizacao.isoformat() if prazo_regularizacao else None
        ),
        "prazo_max_sessao": (
            prazo_max_sessao.isoformat() if prazo_max_sessao else None
        ),
        "prazo_max_continuacao": (
            prazo_max_continuacao.isoformat() if prazo_max_continuacao else None
        ),
        "alertas": alertas,
    }
