"""
FSM Engine com assinatura convergente integrada.

Cada transicao de estado produz uma ConvergenceSignature — o ato processual
so e efetivado se a assinatura convergente atingir o score minimo exigido
para a gravidade daquele ato.

Isso une dois principios:
1. FSM valida que a transicao e permitida (regras do rito)
2. Assinatura valida que o ator e quem diz ser (prova de autoria)

O resultado e um EventoTransicao encadeado por hash + uma ConvergenceSignature
encadeada por hash — dupla cadeia de integridade.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any, Callable

from juizo.exceptions import AssinaturaInsuficiente
from juizo.fsm.engine import FSMEngine, EventoTransicao
from juizo.signing.convergence import ActGravity, ConvergenceSignature
from juizo.signing.gateway import (
    AuditEmitter,
    SignatureStore,
    SigningGateway,
    SigningRequest,
    SigningResult,
)
from juizo.signing.signals import (
    BiometrySignal,
    ContextSignal,
    DeviceSignal,
    ICPBrasilSignal,
    TemporalSignal,
)


@dataclass
class SignedTransitionRequest:
    """
    Requisicao de transicao assinada — tudo que o engine precisa
    para validar a transicao E a assinatura num unico passo.
    """

    # FSM
    estado_atual: str
    estado_destino: str
    processo_id: str
    payload: dict[str, Any] = field(default_factory=dict)

    # Ator
    ator_id: str = ""
    ator_tipo: str = ""

    # Gravidade do ato (determina threshold de convergencia)
    act_gravity: ActGravity = ActGravity.PETITION

    # Sinais de convergencia coletados pelo cliente
    biometry: BiometrySignal | None = None
    device: DeviceSignal | None = None
    temporal: TemporalSignal | None = None
    icp_brasil: ICPBrasilSignal | None = None


@dataclass
class SignedTransitionResult:
    """Resultado de uma transicao assinada — evento + assinatura."""

    evento: EventoTransicao
    signing_result: SigningResult

    @property
    def success(self) -> bool:
        return self.signing_result.success


class SignedFSMEngine:
    """
    FSM Engine com assinatura convergente.

    Fluxo:
    1. FSMEngine valida a transicao (regras do rito, permissoes)
    2. Gera EventoTransicao com hash encadeado
    3. Cria sinal de contexto automaticamente (FSM validou a transicao)
    4. SigningGateway calcula convergencia
    5. Se score >= threshold → transicao efetivada com assinatura
    6. Se score < threshold → AssinaturaInsuficiente (transicao NAO efetivada)

    O sinal de contexto e gerado automaticamente — o engine sabe que a FSM
    validou a transicao. Os demais sinais (biometria, dispositivo, temporal)
    vem do cliente.
    """

    def __init__(
        self,
        fsm: FSMEngine,
        gateway: SigningGateway,
    ) -> None:
        self.fsm = fsm
        self.gateway = gateway

    def transicionar(
        self,
        request: SignedTransitionRequest,
        hash_anterior_evento: str = "",
    ) -> SignedTransitionResult:
        """
        Executa transicao de estado com assinatura convergente.

        Raises:
            EstadoTerminal: estado atual e terminal
            TransicaoInvalida: transicao nao permitida pelo rito
            AtorNaoAutorizado: ator sem permissao para este estado
            AssinaturaInsuficiente: score de convergencia abaixo do minimo
        """
        # 1. FSM valida e gera evento (pode lancar excecao)
        evento = self.fsm.transicionar(
            estado_atual=request.estado_atual,
            estado_destino=request.estado_destino,
            ator_id=request.ator_id,
            ator_tipo=request.ator_tipo,
            processo_id=request.processo_id,
            payload=request.payload,
            hash_anterior=hash_anterior_evento,
        )

        # 2. Sinal de contexto gerado automaticamente — a FSM validou
        context_signal = ContextSignal(
            fsm_state=request.estado_atual,
            fsm_transition=request.estado_destino,
            actor_authorized=True,  # FSM nao lancou AtorNaoAutorizado
            transition_valid=True,  # FSM nao lancou TransicaoInvalida
        )

        # 3. Temporal — se cliente nao enviou, criar com timestamp do servidor
        temporal = request.temporal or TemporalSignal(
            client_timestamp=datetime.now(UTC),
        )
        temporal.hash_anterior = hash_anterior_evento

        # 4. Montar requisicao de assinatura
        signing_request = SigningRequest(
            event_hash=evento.hash,
            process_id=request.processo_id,
            fsm_state=request.estado_atual,
            fsm_transition=request.estado_destino,
            act_gravity=request.act_gravity,
            actor_id=request.ator_id,
            actor_type=request.ator_tipo,
            biometry=request.biometry,
            device=request.device,
            context=context_signal,
            temporal=temporal,
            icp_brasil=request.icp_brasil,
        )

        # 5. Assinar
        signing_result = self.gateway.sign(signing_request)

        # 6. Se score insuficiente, lancar excecao (transicao NAO efetivada)
        if not signing_result.success:
            raise AssinaturaInsuficiente(
                score_obtido=signing_result.threshold_achieved,
                score_exigido=signing_result.threshold_required,
                sinais_ausentes=signing_result.required_missing,
                motivo=signing_result.rejection_reason,
            )

        return SignedTransitionResult(
            evento=evento,
            signing_result=signing_result,
        )
