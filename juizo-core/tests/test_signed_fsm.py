"""
Testes de integracao: FSM Engine + Assinatura Convergente.

Valida que:
- Transicoes validas com sinais suficientes → sucesso
- Transicoes validas com sinais insuficientes → AssinaturaInsuficiente
- Transicoes invalidas → TransicaoInvalida (antes mesmo de checar assinatura)
- Ator nao autorizado → AtorNaoAutorizado
- Estado terminal → EstadoTerminal
- Cadeia de eventos + assinaturas integra
- Sinal de contexto gerado automaticamente
- Gravidade do ato determina threshold
"""

from __future__ import annotations

from datetime import datetime, UTC, timedelta

import pytest

from juizo.exceptions import (
    AssinaturaInsuficiente,
    AtorNaoAutorizado,
    EstadoTerminal,
    TransicaoInvalida,
)
from juizo.fsm.engine import FSMEngine
from juizo.fsm.signed_engine import (
    SignedFSMEngine,
    SignedTransitionRequest,
)
from juizo.signing.convergence import ActGravity, ConvergenceSignature
from juizo.signing.gateway import SigningGateway
from juizo.signing.signals import (
    BiometrySignal,
    DeviceSignal,
    TemporalSignal,
)


# ── Fixtures ──────────────────────────────────────────────────────────


class InMemorySignatureStore:
    def __init__(self) -> None:
        self.signatures: list[ConvergenceSignature] = []

    def append(self, signature: ConvergenceSignature) -> None:
        self.signatures.append(signature)

    def get_last_hash(self, process_id: str) -> str:
        for sig in reversed(self.signatures):
            if sig.process_id == process_id:
                return sig.hash
        return ""


class InMemoryAuditEmitter:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def emit(self, event_type: str, data: dict) -> None:
        self.events.append((event_type, data))


# FSM de teste simples — simula um mini-rito
TRANSICOES = {
    "CADASTRADO": ["SESSAO_AGENDADA"],
    "SESSAO_AGENDADA": ["SESSAO_CONDUZIDA", "SESSAO_FRUSTRADA"],
    "SESSAO_CONDUZIDA": ["ACORDO_REDIGIDO", "SEM_ACORDO"],
    "ACORDO_REDIGIDO": ["HOMOLOGADO"],
    "HOMOLOGADO": [],
    "SEM_ACORDO": [],
    "SESSAO_FRUSTRADA": [],
}

TERMINAIS = {"HOMOLOGADO", "SEM_ACORDO", "SESSAO_FRUSTRADA"}

PERMISSOES = {
    "HOMOLOGADO": ["JUIZ_COORDENADOR"],
    "ACORDO_REDIGIDO": ["CONCILIADOR"],
    "SESSAO_CONDUZIDA": ["CONCILIADOR"],
    "SESSAO_AGENDADA": ["SECRETARIA", "CONCILIADOR"],
}


def make_engine(store=None, audit=None):
    fsm = FSMEngine(
        transicoes=TRANSICOES,
        estados_terminais=TERMINAIS,
        permissoes=PERMISSOES,
    )
    gateway = SigningGateway(
        store=store,
        audit=audit,
    )
    return SignedFSMEngine(fsm=fsm, gateway=gateway)


def make_strong_request(
    estado_atual: str,
    estado_destino: str,
    ator_id: str = "actor-001",
    ator_tipo: str = "CONCILIADOR",
    act_gravity: ActGravity = ActGravity.RECORD,
) -> SignedTransitionRequest:
    """Requisicao com sinais fortes — deve passar para a maioria dos atos."""
    now = datetime.now(UTC)
    return SignedTransitionRequest(
        estado_atual=estado_atual,
        estado_destino=estado_destino,
        processo_id="proc-001",
        ator_id=ator_id,
        ator_tipo=ator_tipo,
        act_gravity=act_gravity,
        biometry=BiometrySignal(
            method="face_id",
            match_score=0.97,
            device_tee="secure_enclave",
        ),
        device=DeviceSignal(
            device_id="device-hash-001",
            device_signature="ed25519-sig",
            key_origin="secure_enclave",
            known_since=now - timedelta(days=180),
            platform="ios",
            ip_address="192.168.1.100",
        ),
        temporal=TemporalSignal(
            client_timestamp=now,
            server_timestamp=now + timedelta(seconds=1),
        ),
    )


# ── Testes ────────────────────────────────────────────────────────────


class TestSignedFSMEngine:

    def test_valid_transition_with_strong_signals(self) -> None:
        """Transicao valida + sinais fortes → sucesso."""
        store = InMemorySignatureStore()
        audit = InMemoryAuditEmitter()
        engine = make_engine(store=store, audit=audit)

        request = make_strong_request(
            "CADASTRADO", "SESSAO_AGENDADA",
            ator_tipo="SECRETARIA",
            act_gravity=ActGravity.FILE,
        )
        result = engine.transicionar(request)

        assert result.success
        assert result.evento.estado_anterior == "CADASTRADO"
        assert result.evento.estado_novo == "SESSAO_AGENDADA"
        assert result.signing_result.signature is not None
        assert len(store.signatures) == 1
        assert len(audit.events) == 1
        assert audit.events[0][0] == "signing_approved"

    def test_invalid_transition_raises_before_signing(self) -> None:
        """Transicao invalida → TransicaoInvalida (nem chega a verificar assinatura)."""
        engine = make_engine()

        request = make_strong_request(
            "CADASTRADO", "HOMOLOGADO",  # pulo invalido
        )

        with pytest.raises(TransicaoInvalida):
            engine.transicionar(request)

    def test_terminal_state_raises(self) -> None:
        """Estado terminal → EstadoTerminal."""
        engine = make_engine()

        request = make_strong_request(
            "HOMOLOGADO", "CADASTRADO",  # estado terminal
        )

        with pytest.raises(EstadoTerminal):
            engine.transicionar(request)

    def test_unauthorized_actor_raises(self) -> None:
        """Ator nao autorizado → AtorNaoAutorizado."""
        engine = make_engine()

        request = make_strong_request(
            "ACORDO_REDIGIDO", "HOMOLOGADO",
            ator_tipo="PARTE",  # so JUIZ_COORDENADOR pode homologar
        )

        with pytest.raises(AtorNaoAutorizado):
            engine.transicionar(request)

    def test_weak_signals_for_sentence_raises(self) -> None:
        """Sinais fracos para ato grave → AssinaturaInsuficiente."""
        engine = make_engine()

        # Requisicao para homologacao (gravidade SENTENCE) com sinais minimos
        request = SignedTransitionRequest(
            estado_atual="ACORDO_REDIGIDO",
            estado_destino="HOMOLOGADO",
            processo_id="proc-001",
            ator_id="juiz-001",
            ator_tipo="JUIZ_COORDENADOR",
            act_gravity=ActGravity.SENTENCE,  # threshold 0.95
            device=DeviceSignal(
                device_id="dev",
                device_signature="sig",
                key_origin="software",  # score baixo
                platform="linux",
            ),
            temporal=TemporalSignal(
                client_timestamp=datetime.now(UTC),
            ),
            # Sem biometria — para sentenca, score vai ficar baixo
        )

        with pytest.raises(AssinaturaInsuficiente) as exc_info:
            engine.transicionar(request)

        assert exc_info.value.score_exigido == 0.95
        assert exc_info.value.score_obtido < 0.95

    def test_context_signal_auto_generated(self) -> None:
        """Sinal de contexto e gerado automaticamente pela FSM."""
        store = InMemorySignatureStore()
        engine = make_engine(store=store)

        request = make_strong_request(
            "CADASTRADO", "SESSAO_AGENDADA",
            ator_tipo="SECRETARIA",
            act_gravity=ActGravity.FILE,
        )
        result = engine.transicionar(request)

        # Verificar que o sinal de contexto esta na assinatura
        sig = result.signing_result.signature
        signal_types = [s.signal_type.value for s in sig.signals]
        assert "context" in signal_types

        # O sinal de contexto indica transicao valida e ator autorizado
        ctx_signal = next(s for s in sig.signals if s.signal_type.value == "context")
        assert ctx_signal.score == 1.0  # tudo validado pela FSM
        assert ctx_signal.metadata["actor_authorized"] is True
        assert ctx_signal.metadata["transition_valid"] is True

    def test_event_hash_linked_to_signature(self) -> None:
        """Hash do evento e o mesmo usado na assinatura."""
        store = InMemorySignatureStore()
        engine = make_engine(store=store)

        request = make_strong_request(
            "CADASTRADO", "SESSAO_AGENDADA",
            ator_tipo="SECRETARIA",
            act_gravity=ActGravity.FILE,
        )
        result = engine.transicionar(request)

        # Hash do evento deve ser o event_hash da assinatura
        assert result.signing_result.signature.event_hash == result.evento.hash

    def test_signature_chain_across_transitions(self) -> None:
        """Assinaturas sao encadeadas por hash entre transicoes."""
        store = InMemorySignatureStore()
        engine = make_engine(store=store)

        # Transicao 1: CADASTRADO → SESSAO_AGENDADA
        req1 = make_strong_request(
            "CADASTRADO", "SESSAO_AGENDADA",
            ator_tipo="SECRETARIA",
            act_gravity=ActGravity.FILE,
        )
        result1 = engine.transicionar(req1)

        # Transicao 2: SESSAO_AGENDADA → SESSAO_CONDUZIDA
        req2 = make_strong_request(
            "SESSAO_AGENDADA", "SESSAO_CONDUZIDA",
            ator_tipo="CONCILIADOR",
            act_gravity=ActGravity.RECORD,
        )
        result2 = engine.transicionar(req2, hash_anterior_evento=result1.evento.hash)

        # Verificar encadeamento de assinaturas
        sig1 = store.signatures[0]
        sig2 = store.signatures[1]
        assert sig2.hash_anterior == sig1.hash

        # Verificar encadeamento de eventos
        assert result2.evento.hash_anterior == result1.evento.hash

    def test_full_flow_cadastro_to_homologacao(self) -> None:
        """Fluxo completo: cadastro → agendamento → sessao → acordo → homologacao."""
        store = InMemorySignatureStore()
        audit = InMemoryAuditEmitter()
        engine = make_engine(store=store, audit=audit)

        now = datetime.now(UTC)
        hash_anterior = ""

        transitions = [
            ("CADASTRADO", "SESSAO_AGENDADA", "sec-001", "SECRETARIA", ActGravity.FILE),
            ("SESSAO_AGENDADA", "SESSAO_CONDUZIDA", "conc-001", "CONCILIADOR", ActGravity.RECORD),
            ("SESSAO_CONDUZIDA", "ACORDO_REDIGIDO", "conc-001", "CONCILIADOR", ActGravity.RECORD),
            ("ACORDO_REDIGIDO", "HOMOLOGADO", "juiz-001", "JUIZ_COORDENADOR", ActGravity.SENTENCE),
        ]

        for estado_atual, estado_destino, ator_id, ator_tipo, gravity in transitions:
            request = make_strong_request(
                estado_atual, estado_destino,
                ator_id=ator_id,
                ator_tipo=ator_tipo,
                act_gravity=gravity,
            )
            result = engine.transicionar(request, hash_anterior_evento=hash_anterior)
            assert result.success
            hash_anterior = result.evento.hash

        # 4 transicoes → 4 assinaturas → 4 eventos de auditoria
        assert len(store.signatures) == 4
        assert len(audit.events) == 4

        # Cadeia de assinaturas integra
        for i in range(1, len(store.signatures)):
            assert store.signatures[i].hash_anterior == store.signatures[i - 1].hash

        # Todos os eventos de auditoria sao "signing_approved"
        assert all(e[0] == "signing_approved" for e in audit.events)

    def test_gravity_proportional_to_act(self) -> None:
        """Mesmo sinais, atos diferentes — VIEW aceita, SENTENCE rejeita."""
        engine = make_engine()

        # Sinais medianos (sem biometria, device software)
        request = SignedTransitionRequest(
            estado_atual="CADASTRADO",
            estado_destino="SESSAO_AGENDADA",
            processo_id="proc-001",
            ator_id="sec-001",
            ator_tipo="SECRETARIA",
            act_gravity=ActGravity.VIEW,  # threshold 0.60
            device=DeviceSignal(
                device_id="dev",
                device_signature="sig",
                key_origin="software",
                platform="linux",
            ),
            temporal=TemporalSignal(
                client_timestamp=datetime.now(UTC),
            ),
        )

        # VIEW aceita
        result = engine.transicionar(request)
        assert result.success

        # Mesmos sinais para SENTENCE — rejeita
        request_sentence = SignedTransitionRequest(
            estado_atual="ACORDO_REDIGIDO",
            estado_destino="HOMOLOGADO",
            processo_id="proc-002",
            ator_id="juiz-001",
            ator_tipo="JUIZ_COORDENADOR",
            act_gravity=ActGravity.SENTENCE,  # threshold 0.95
            device=DeviceSignal(
                device_id="dev",
                device_signature="sig",
                key_origin="software",
                platform="linux",
            ),
            temporal=TemporalSignal(
                client_timestamp=datetime.now(UTC),
            ),
        )

        with pytest.raises(AssinaturaInsuficiente):
            engine.transicionar(request_sentence)
