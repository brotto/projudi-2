"""
Rotas de sessões de conciliação/mediação — CEJUSC pré-processual.

art. 11–14 · Res. 403/2023:
- Sessão conduzida pelo conciliador/mediador designado
- Continuação: máx. 60 dias total (art. 14)
- Ausência de parte → arquivamento imediato (art. 12 §3º)
"""

from __future__ import annotations

from datetime import datetime, UTC
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import get_store
from api.schemas import (
    ResultadoSessaoIn,
    SessaoIn,
    SessaoOut,
)
from api.store import EventStore

router = APIRouter(prefix="/sessoes", tags=["Sessões"])


@router.post(
    "/",
    response_model=SessaoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Agendar sessão de conciliação/mediação — art. 10º",
)
def criar_sessao(
    body: SessaoIn,
    store: EventStore = Depends(get_store),
) -> SessaoOut:
    """
    Agenda uma sessão de conciliação ou mediação.

    art. 10º — Sessão designada com conciliador/mediador e data.
    art. 14 — Prazo máximo de 30 dias para primeira sessão.
    """
    rec = store.get_reclamacao(UUID(body.reclamacao_id))
    if rec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reclamação {body.reclamacao_id} não encontrada",
        )

    # Contar sessões existentes para esta reclamação
    sessoes_existentes = store.listar_sessoes(UUID(body.reclamacao_id))
    numero_sessao = len(sessoes_existentes) + 1

    sessao_id = uuid4()
    dados = {
        "reclamacao_id": body.reclamacao_id,
        "conciliador_id": body.conciliador_id,
        "conciliador_nome": body.conciliador_nome,
        "data_agendada": body.data_agendada.isoformat(),
        "numero_sessao": numero_sessao,
        "resultado": None,
        "criada_em": datetime.now(UTC).isoformat(),
    }

    store.criar_sessao(sessao_id, dados)

    return SessaoOut(
        id=str(sessao_id),
        reclamacao_id=body.reclamacao_id,
        numero_sessao=numero_sessao,
        conciliador_nome=body.conciliador_nome,
        data_agendada=body.data_agendada.isoformat(),
    )


@router.get(
    "/",
    response_model=list[SessaoOut],
    summary="Listar sessões",
)
def listar_sessoes(
    reclamacao_id: UUID | None = None,
    store: EventStore = Depends(get_store),
) -> list[SessaoOut]:
    """Lista todas as sessões, opcionalmente filtradas por reclamação."""
    sessoes = store.listar_sessoes(reclamacao_id)
    return [
        SessaoOut(
            id=s["id"],
            reclamacao_id=s["reclamacao_id"],
            numero_sessao=s.get("numero_sessao", 1),
            conciliador_nome=s["conciliador_nome"],
            data_agendada=s["data_agendada"],
            resultado=s.get("resultado"),
        )
        for s in sessoes
    ]


@router.get(
    "/{sessao_id}",
    response_model=SessaoOut,
    summary="Consultar sessão",
)
def get_sessao(
    sessao_id: UUID,
    store: EventStore = Depends(get_store),
) -> SessaoOut:
    """Retorna os dados de uma sessão pelo ID."""
    s = store.get_sessao(sessao_id)
    if s is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sessão {sessao_id} não encontrada",
        )
    return SessaoOut(
        id=s["id"],
        reclamacao_id=s["reclamacao_id"],
        numero_sessao=s.get("numero_sessao", 1),
        conciliador_nome=s["conciliador_nome"],
        data_agendada=s["data_agendada"],
        resultado=s.get("resultado"),
    )


@router.post(
    "/{sessao_id}/resultado",
    response_model=SessaoOut,
    summary="Registrar resultado da sessão — art. 12–13",
)
def registrar_resultado(
    sessao_id: UUID,
    body: ResultadoSessaoIn,
    store: EventStore = Depends(get_store),
) -> SessaoOut:
    """
    Registra o resultado de uma sessão conduzida.

    art. 12 — Resultados possíveis:
    - ACORDO: acordo obtido, segue para redação (art. 13)
    - SEM_ACORDO: sessão infrutífera → certidão negativa
    - CONTINUACAO: necessita nova sessão (max 60 dias · art. 14)
    - AUSENCIA_*: ausência de parte(s) → arquivamento imediato (art. 12 §3º)
    """
    s = store.get_sessao(sessao_id)
    if s is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sessão {sessao_id} não encontrada",
        )

    dados_atualizacao = {
        "resultado": body.resultado.value,
        "ata_conteudo": body.ata_conteudo,
        "reclamante_presente": body.reclamante_presente,
        "reclamado_presente": body.reclamado_presente,
        "observacoes": body.observacoes,
        "registrado_em": datetime.now(UTC).isoformat(),
    }

    store.atualizar_sessao(sessao_id, dados_atualizacao)
    s_atualizada = store.get_sessao(sessao_id)

    return SessaoOut(
        id=s_atualizada["id"],
        reclamacao_id=s_atualizada["reclamacao_id"],
        numero_sessao=s_atualizada.get("numero_sessao", 1),
        conciliador_nome=s_atualizada["conciliador_nome"],
        data_agendada=s_atualizada["data_agendada"],
        resultado=s_atualizada.get("resultado"),
    )
