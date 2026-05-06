"""
Rotas de reclamações — CEJUSC pré-processual.

CRUD completo + transições FSM + histórico de eventos.
Cada reclamação é um dataset jurisdicional com append-only log.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from juizo.exceptions import (
    AtorNaoAutorizado,
    EstadoTerminal,
    TransicaoInvalida,
)

from api.deps import get_store
from api.schemas import (
    CartaConviteOut,
    CertidaoNegativaOut,
    EstadoOut,
    PrazosOut,
    ReclamacaoIn,
    ReclamacaoOut,
    TransicaoIn,
    TransicaoOut,
)
from api.store import EventStore

router = APIRouter(prefix="/reclamacoes", tags=["Reclamações"])


# ── CRUD ──────────────────────────────────────────────────────────────────


@router.post(
    "/",
    response_model=ReclamacaoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Protocolar reclamação — art. 9º Res. 403/2023",
)
def criar_reclamacao(
    body: ReclamacaoIn,
    store: EventStore = Depends(get_store),
) -> ReclamacaoOut:
    """
    Cria uma nova reclamação pré-processual.

    art. 9º — Requisitos: CEJUSC destino, qualificação completa das partes,
    breve relato dos fatos, pedidos com especificações, valor da causa,
    opção de modalidade (conciliação/mediação), comprovante de custas.
    """
    reclamacao_id = uuid4()
    dados = {
        "cejusc_destino": body.cejusc_destino,
        "reclamante": body.reclamante.model_dump(),
        "reclamado": body.reclamado.model_dump(),
        "fatos": body.fatos,
        "pedidos": [p.model_dump() for p in body.pedidos],
        "valor_causa": str(body.valor_causa),
        "modalidade": body.modalidade.value,
        "opcao_custas": body.opcao_custas.value,
    }

    evento = store.criar_reclamacao(reclamacao_id, dados)
    rec = store.get_reclamacao(reclamacao_id)

    return ReclamacaoOut(
        id=str(reclamacao_id),
        cejusc_destino=rec["cejusc_destino"],
        reclamante=rec["reclamante"],
        reclamado=rec["reclamado"],
        fatos=rec["fatos"],
        pedidos=rec["pedidos"],
        valor_causa=rec["valor_causa"],
        modalidade=rec["modalidade"],
        opcao_custas=rec["opcao_custas"],
        estado_atual=rec["estado_atual"],
        protocolado_em=evento.timestamp.isoformat(),
    )


@router.get(
    "/",
    response_model=list[ReclamacaoOut],
    summary="Listar reclamações",
)
def listar_reclamacoes(
    store: EventStore = Depends(get_store),
) -> list[ReclamacaoOut]:
    """Retorna todas as reclamações cadastradas."""
    return [
        ReclamacaoOut(
            id=r["id"],
            cejusc_destino=r["cejusc_destino"],
            reclamante=r["reclamante"],
            reclamado=r["reclamado"],
            fatos=r["fatos"],
            pedidos=r["pedidos"],
            valor_causa=r["valor_causa"],
            modalidade=r["modalidade"],
            opcao_custas=r["opcao_custas"],
            estado_atual=r["estado_atual"],
        )
        for r in store.listar_reclamacoes()
    ]


@router.get(
    "/{reclamacao_id}",
    response_model=ReclamacaoOut,
    summary="Consultar reclamação",
)
def get_reclamacao(
    reclamacao_id: UUID,
    store: EventStore = Depends(get_store),
) -> ReclamacaoOut:
    """Retorna os dados de uma reclamação pelo ID."""
    rec = store.get_reclamacao(reclamacao_id)
    if rec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reclamação {reclamacao_id} não encontrada",
        )
    return ReclamacaoOut(
        id=rec["id"],
        cejusc_destino=rec["cejusc_destino"],
        reclamante=rec["reclamante"],
        reclamado=rec["reclamado"],
        fatos=rec["fatos"],
        pedidos=rec["pedidos"],
        valor_causa=rec["valor_causa"],
        modalidade=rec["modalidade"],
        opcao_custas=rec["opcao_custas"],
        estado_atual=rec["estado_atual"],
    )


# ── Transições FSM ───────────────────────────────────────────────────────


@router.post(
    "/{reclamacao_id}/transicao",
    response_model=TransicaoOut,
    summary="Executar transição de estado — FSM",
)
def executar_transicao(
    reclamacao_id: UUID,
    body: TransicaoIn,
    store: EventStore = Depends(get_store),
) -> TransicaoOut:
    """
    Executa uma transição de estado na FSM da reclamação.

    A FSM valida:
    1. Se o estado atual permite a transição destino
    2. Se o ator tem permissão para executar essa transição
    3. Se o estado atual não é terminal (frozen)

    Cada transição é registrada como evento imutável com hash encadeado.
    """
    rec = store.get_reclamacao(reclamacao_id)
    if rec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reclamação {reclamacao_id} não encontrada",
        )

    try:
        evento = store.transicionar(
            reclamacao_id=reclamacao_id,
            estado_destino=body.estado_destino,
            ator_id=body.ator_id,
            ator_tipo=body.ator_tipo,
            payload=body.payload,
        )
    except TransicaoInvalida as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "TRANSICAO_INVALIDA",
                "estado_atual": e.estado_atual,
                "transicao_tentada": e.transicao_tentada,
                "transicoes_validas": e.transicoes_validas,
            },
        )
    except AtorNaoAutorizado as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "ATOR_NAO_AUTORIZADO",
                "ator_tipo": e.ator_tipo,
                "ato": e.ato,
                "estado": e.estado,
            },
        )
    except EstadoTerminal as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "ESTADO_TERMINAL",
                "estado": e.estado,
                "mensagem": str(e),
            },
        )

    return TransicaoOut(
        id=evento.id,
        estado_anterior=evento.estado_anterior,
        estado_novo=evento.estado_novo,
        ator_id=evento.ator_id,
        ator_tipo=evento.ator_tipo,
        timestamp=evento.timestamp.isoformat(),
        hash=evento.hash,
    )


@router.get(
    "/{reclamacao_id}/estado",
    response_model=EstadoOut,
    summary="Consultar estado atual + transições válidas",
)
def get_estado(
    reclamacao_id: UUID,
    store: EventStore = Depends(get_store),
) -> EstadoOut:
    """
    Retorna o estado atual da reclamação e as transições válidas.
    Útil para o frontend renderizar botões de ação disponíveis.
    """
    estado = store.get_estado(reclamacao_id)
    if estado is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reclamação {reclamacao_id} não encontrada",
        )

    from fsm.engine import engine as fsm_engine

    return EstadoOut(
        reclamacao_id=str(reclamacao_id),
        estado_atual=estado,
        transicoes_validas=store.get_transicoes_validas(reclamacao_id),
        is_terminal=fsm_engine.is_terminal(estado),
    )


@router.get(
    "/{reclamacao_id}/historico",
    response_model=list[dict],
    summary="Consultar histórico de eventos (append-only log)",
)
def get_historico(
    reclamacao_id: UUID,
    store: EventStore = Depends(get_store),
) -> list[dict]:
    """
    Retorna o log completo de eventos da reclamação.
    Cada evento é imutável e encadeado por hash SHA-256 (append-only).
    """
    rec = store.get_reclamacao(reclamacao_id)
    if rec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reclamação {reclamacao_id} não encontrada",
        )

    return store.get_historico(reclamacao_id)
