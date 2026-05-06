"""
Rotas de acordos — CEJUSC pré-processual.

art. 13–16 · Res. 403/2023:
- Acordo redigido pelas partes com auxílio do conciliador/mediador
- Menores/incapazes: MP obrigatório antes da homologação (art. 15 §ú)
- Homologação pelo juiz coordenador (art. 15)
- Título executivo judicial após homologação (art. 16)
"""

from __future__ import annotations

from datetime import datetime, UTC
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import get_store
from api.schemas import (
    AcordoIn,
    AcordoOut,
    ParecerMPIn,
)
from api.store import EventStore

router = APIRouter(prefix="/acordos", tags=["Acordos"])


@router.post(
    "/",
    response_model=AcordoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar acordo — art. 13 §3º",
)
def criar_acordo(
    body: AcordoIn,
    store: EventStore = Depends(get_store),
) -> AcordoOut:
    """
    Registra um acordo obtido em sessão de conciliação/mediação.

    art. 13 §3º — Acordo redigido com condições específicas.
    Se envolve menores/incapazes, o MP deve se manifestar (art. 15 §ú).
    """
    rec = store.get_reclamacao(UUID(body.reclamacao_id))
    if rec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reclamação {body.reclamacao_id} não encontrada",
        )

    sessao = store.get_sessao(UUID(body.sessao_id))
    if sessao is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sessão {body.sessao_id} não encontrada",
        )

    acordo_id = uuid4()

    # Calcular valor total das condições
    valor_total = sum(
        (c.valor for c in body.condicoes if c.valor is not None),
        Decimal("0"),
    )

    # Determinar status inicial — art. 15 §ú
    status_acordo = "REDIGIDO"
    pode_homologar = True
    if body.envolve_menores_incapazes:
        pode_homologar = False  # Precisa parecer MP primeiro

    dados = {
        "reclamacao_id": body.reclamacao_id,
        "sessao_id": body.sessao_id,
        "condicoes": [c.model_dump(mode="json") for c in body.condicoes],
        "envolve_menores_incapazes": body.envolve_menores_incapazes,
        "status": status_acordo,
        "valor_total": str(valor_total),
        "pode_homologar": pode_homologar,
        "parecer_mp": None,
        "redigido_em": datetime.now(UTC).isoformat(),
    }

    store.criar_acordo(acordo_id, dados)

    return AcordoOut(
        id=str(acordo_id),
        reclamacao_id=body.reclamacao_id,
        sessao_id=body.sessao_id,
        condicoes=[c.model_dump(mode="json") for c in body.condicoes],
        envolve_menores_incapazes=body.envolve_menores_incapazes,
        status=status_acordo,
        valor_total=str(valor_total),
        pode_homologar=pode_homologar,
    )


@router.get(
    "/{acordo_id}",
    response_model=AcordoOut,
    summary="Consultar acordo",
)
def get_acordo(
    acordo_id: UUID,
    store: EventStore = Depends(get_store),
) -> AcordoOut:
    """Retorna os dados de um acordo pelo ID."""
    a = store.get_acordo(acordo_id)
    if a is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Acordo {acordo_id} não encontrado",
        )
    return AcordoOut(
        id=a["id"],
        reclamacao_id=a["reclamacao_id"],
        sessao_id=a["sessao_id"],
        condicoes=a["condicoes"],
        envolve_menores_incapazes=a["envolve_menores_incapazes"],
        status=a["status"],
        valor_total=a["valor_total"],
        pode_homologar=a["pode_homologar"],
    )


@router.post(
    "/{acordo_id}/parecer-mp",
    response_model=AcordoOut,
    summary="Registrar parecer do MP — art. 15 §ú",
)
def registrar_parecer_mp(
    acordo_id: UUID,
    body: ParecerMPIn,
    store: EventStore = Depends(get_store),
) -> AcordoOut:
    """
    Registra o parecer do Ministério Público.

    art. 15 §ú — Obrigatório quando houver menores ou incapazes envolvidos.
    Parecer favorável libera o acordo para homologação pelo juiz.
    """
    a = store.get_acordo(acordo_id)
    if a is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Acordo {acordo_id} não encontrado",
        )

    if not a["envolve_menores_incapazes"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Acordo não envolve menores/incapazes — parecer do MP não é necessário",
        )

    if a["status"] != "REDIGIDO" and a["status"] != "AGUARDANDO_MP":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Acordo em status '{a['status']}' não aceita parecer do MP",
        )

    parecer = {
        "promotor_id": body.promotor_id,
        "promotor_nome": body.promotor_nome,
        "favoravel": body.favoravel,
        "fundamentacao": body.fundamentacao,
        "emitido_em": datetime.now(UTC).isoformat(),
    }

    dados_atualizacao = {
        "parecer_mp": parecer,
        "status": "PARECER_MP_EMITIDO",
        "pode_homologar": body.favoravel,  # Só homologa se parecer favorável
    }

    store.atualizar_acordo(acordo_id, dados_atualizacao)
    a_atualizado = store.get_acordo(acordo_id)

    return AcordoOut(
        id=a_atualizado["id"],
        reclamacao_id=a_atualizado["reclamacao_id"],
        sessao_id=a_atualizado["sessao_id"],
        condicoes=a_atualizado["condicoes"],
        envolve_menores_incapazes=a_atualizado["envolve_menores_incapazes"],
        status=a_atualizado["status"],
        valor_total=a_atualizado["valor_total"],
        pode_homologar=a_atualizado["pode_homologar"],
    )


@router.post(
    "/{acordo_id}/homologar",
    response_model=AcordoOut,
    summary="Homologar acordo — art. 15",
)
def homologar_acordo(
    acordo_id: UUID,
    juiz_id: str,
    juiz_nome: str,
    store: EventStore = Depends(get_store),
) -> AcordoOut:
    """
    Homologa o acordo pelo juiz coordenador.

    art. 15 — O acordo homologado constitui título executivo judicial (art. 16).
    Se o acordo envolve menores/incapazes, requer parecer favorável do MP.
    """
    a = store.get_acordo(acordo_id)
    if a is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Acordo {acordo_id} não encontrado",
        )

    if not a["pode_homologar"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Acordo não pode ser homologado — requer parecer favorável do MP",
        )

    dados_atualizacao = {
        "status": "HOMOLOGADO",
        "homologado_por_id": juiz_id,
        "homologado_por_nome": juiz_nome,
        "homologado_em": datetime.now(UTC).isoformat(),
    }

    store.atualizar_acordo(acordo_id, dados_atualizacao)
    a_atualizado = store.get_acordo(acordo_id)

    return AcordoOut(
        id=a_atualizado["id"],
        reclamacao_id=a_atualizado["reclamacao_id"],
        sessao_id=a_atualizado["sessao_id"],
        condicoes=a_atualizado["condicoes"],
        envolve_menores_incapazes=a_atualizado["envolve_menores_incapazes"],
        status=a_atualizado["status"],
        valor_total=a_atualizado["valor_total"],
        pode_homologar=a_atualizado["pode_homologar"],
    )
