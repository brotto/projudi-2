"""
Testes do modulo de assinatura por convergencia.

Valida:
- Calculo de score de convergencia
- Thresholds por gravidade de ato
- Rejeicao por sinal obrigatorio ausente
- Encadeamento de hashes
- Verificacao de integridade
- Fluxo completo do SigningGateway
"""

from __future__ import annotations

from datetime import datetime, UTC, timedelta
from typing import Any
from uuid import uuid4

import pytest

from juizo.signing.convergence import (
    ActGravity,
    ConvergenceScore,
    ConvergenceSignature,
    DEFAULT_THRESHOLDS,
    DEFAULT_WEIGHTS,
    Signal,
    SignalType,
    SignalWeight,
)
from juizo.signing.signals import (
    BiometrySignal,
    ContextSignal,
    DeviceSignal,
    ICPBrasilSignal,
    TemporalSignal,
)
from juizo.signing.gateway import (
    SigningGateway,
    SigningRequest,
    SigningResult,
)
from juizo.signing.verifier import SignatureVerifier


# ── Fixtures ──────────────────────────────────────────────────────────


class InMemorySignatureStore:
    """Store em memoria para testes."""

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
    """Emissor de auditoria em memoria para testes."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def emit(self, event_type: str, data: dict[str, Any]) -> None:
        self.events.append((event_type, data))


def make_full_request(
    act_gravity: ActGravity = ActGravity.PETITION,
    biometry_score: float = 0.97,
    device_origin: str = "secure_enclave",
) -> SigningRequest:
    """Cria uma requisicao de assinatura com todos os sinais."""
    now = datetime.now(UTC)
    return SigningRequest(
        event_hash="abc123hash",
        process_id="proc-001",
        fsm_state="SESSAO_CONDUZIDA",
        fsm_transition="ACORDO_REDIGIDO",
        act_gravity=act_gravity,
        actor_id="actor-001",
        actor_type="CONCILIADOR",
        biometry=BiometrySignal(
            method="face_id",
            match_score=biometry_score,
            device_tee="secure_enclave",
        ),
        device=DeviceSignal(
            device_id="device-hash-001",
            device_signature="ed25519-sig-here",
            key_origin=device_origin,
            known_since=now - timedelta(days=180),
            platform="ios",
            ip_address="192.168.1.100",
        ),
        context=ContextSignal(
            fsm_state="SESSAO_CONDUZIDA",
            fsm_transition="ACORDO_REDIGIDO",
            actor_authorized=True,
            transition_valid=True,
        ),
        temporal=TemporalSignal(
            client_timestamp=now,
            server_timestamp=now + timedelta(seconds=1),
        ),
    )


# ── Testes de Signal ──────────────────────────────────────────────────


class TestSignals:

    def test_biometry_signal_creates_valid_signal(self) -> None:
        bio = BiometrySignal(
            method="face_id",
            match_score=0.95,
            device_tee="secure_enclave",
        )
        signal = bio.to_signal()
        assert signal.signal_type == SignalType.BIOMETRY
        assert signal.score == 0.95
        assert signal.metadata["method"] == "face_id"
        assert signal.metadata["captured_on_device"] is True
        assert signal.proof  # hash nao vazio

    def test_device_signal_secure_enclave_high_score(self) -> None:
        device = DeviceSignal(
            device_id="dev-001",
            device_signature="sig",
            key_origin="secure_enclave",
            known_since=datetime.now(UTC) - timedelta(days=365),
            platform="ios",
        )
        signal = device.to_signal()
        assert signal.signal_type == SignalType.DEVICE
        assert signal.score >= 0.95  # secure enclave = alto score

    def test_device_signal_software_low_score(self) -> None:
        device = DeviceSignal(
            device_id="dev-002",
            device_signature="sig",
            key_origin="software",
            platform="linux",
        )
        signal = device.to_signal()
        assert signal.score == 0.50  # software = score baixo

    def test_context_signal_valid_transition(self) -> None:
        ctx = ContextSignal(
            fsm_state="SESSAO_CONDUZIDA",
            fsm_transition="ACORDO_REDIGIDO",
            actor_authorized=True,
            transition_valid=True,
        )
        signal = ctx.to_signal()
        assert signal.score == 1.0

    def test_context_signal_invalid_transition(self) -> None:
        ctx = ContextSignal(
            fsm_state="SESSAO_CONDUZIDA",
            fsm_transition="CADASTRADO",  # transicao invalida
            actor_authorized=True,
            transition_valid=False,
        )
        signal = ctx.to_signal()
        assert signal.score == 0.0

    def test_context_signal_override_reduced_score(self) -> None:
        ctx = ContextSignal(
            fsm_state="X",
            fsm_transition="Y",
            actor_authorized=True,
            transition_valid=True,
            override=True,
        )
        signal = ctx.to_signal()
        assert signal.score == 0.60

    def test_temporal_signal_low_drift(self) -> None:
        now = datetime.now(UTC)
        temp = TemporalSignal(
            client_timestamp=now,
            server_timestamp=now + timedelta(seconds=2),
        )
        signal = temp.to_signal()
        assert signal.score == 1.0  # drift < 5s

    def test_temporal_signal_high_drift(self) -> None:
        now = datetime.now(UTC)
        temp = TemporalSignal(
            client_timestamp=now,
            server_timestamp=now + timedelta(minutes=10),
        )
        signal = temp.to_signal()
        assert signal.score < 0.30  # drift > 5min

    def test_icp_brasil_valid_a3(self) -> None:
        icp = ICPBrasilSignal(
            certificate_cn="FULANO DE TAL",
            certificate_serial="ABC123",
            issuer_cn="AC CERTISIGN",
            certificate_type="A3",
            chain_valid=True,
            not_revoked=True,
        )
        signal = icp.to_signal()
        assert signal.score >= 0.90

    def test_icp_brasil_revoked_low_score(self) -> None:
        icp = ICPBrasilSignal(
            certificate_cn="FULANO",
            certificate_serial="ABC123",
            issuer_cn="AC CERTISIGN",
            certificate_type="A3",
            chain_valid=True,
            not_revoked=False,  # REVOGADO
        )
        signal = icp.to_signal()
        assert signal.score <= 0.10


# ── Testes de Convergencia ────────────────────────────────────────────


class TestConvergence:

    def test_full_signals_high_score(self) -> None:
        """Todos os sinais primarios presentes → score alto."""
        sig = ConvergenceSignature(
            actor_id="actor-001",
            event_hash="hash-001",
            signals=[
                Signal(SignalType.BIOMETRY, score=0.95),
                Signal(SignalType.DEVICE, score=0.90),
                Signal(SignalType.CONTEXT, score=1.0),
                Signal(SignalType.TEMPORAL, score=1.0),
                Signal(SignalType.BEHAVIOR, score=0.85),
            ],
        )
        score = sig.compute_convergence()
        assert score.value >= 0.90
        assert score.is_sufficient
        assert len(score.required_missing) == 0

    def test_missing_required_signal_zeros_score(self) -> None:
        """Sinal obrigatorio ausente → score = 0."""
        sig = ConvergenceSignature(
            actor_id="actor-001",
            event_hash="hash-001",
            signals=[
                Signal(SignalType.BIOMETRY, score=0.95),
                # DEVICE ausente (required=True nos defaults)
                Signal(SignalType.CONTEXT, score=1.0),
                Signal(SignalType.TEMPORAL, score=1.0),
            ],
        )
        score = sig.compute_convergence()
        assert score.value == 0.0
        assert not score.is_sufficient
        assert SignalType.DEVICE in score.required_missing

    def test_icp_brasil_bonus(self) -> None:
        """ICP-Brasil como sinal bonus aumenta o score."""
        # Sem ICP
        sig_base = ConvergenceSignature(
            actor_id="actor-001",
            event_hash="hash-001",
            signals=[
                Signal(SignalType.BIOMETRY, score=0.95),
                Signal(SignalType.DEVICE, score=0.90),
                Signal(SignalType.CONTEXT, score=1.0),
                Signal(SignalType.TEMPORAL, score=1.0),
            ],
        )
        score_base = sig_base.compute_convergence()

        # Com ICP
        sig_icp = ConvergenceSignature(
            actor_id="actor-001",
            event_hash="hash-001",
            signals=[
                Signal(SignalType.BIOMETRY, score=0.95),
                Signal(SignalType.DEVICE, score=0.90),
                Signal(SignalType.CONTEXT, score=1.0),
                Signal(SignalType.TEMPORAL, score=1.0),
                Signal(SignalType.ICP_BRASIL, score=0.95),
            ],
        )
        score_icp = sig_icp.compute_convergence()

        assert score_icp.value > score_base.value

    def test_score_capped_at_1(self) -> None:
        """Score nunca ultrapassa 1.0."""
        sig = ConvergenceSignature(
            actor_id="actor-001",
            event_hash="hash-001",
            signals=[
                Signal(SignalType.BIOMETRY, score=1.0),
                Signal(SignalType.DEVICE, score=1.0),
                Signal(SignalType.CONTEXT, score=1.0),
                Signal(SignalType.TEMPORAL, score=1.0),
                Signal(SignalType.BEHAVIOR, score=1.0),
                Signal(SignalType.ICP_BRASIL, score=1.0),
                Signal(SignalType.GOV_BR, score=1.0),
            ],
        )
        score = sig.compute_convergence()
        assert score.value <= 1.0

    def test_threshold_by_gravity(self) -> None:
        """Atos mais graves exigem thresholds mais altos."""
        assert DEFAULT_THRESHOLDS[ActGravity.VIEW] < DEFAULT_THRESHOLDS[ActGravity.SENTENCE]
        assert DEFAULT_THRESHOLDS[ActGravity.FILE] < DEFAULT_THRESHOLDS[ActGravity.DECISION]

    def test_convergence_score_meets_threshold(self) -> None:
        score = ConvergenceScore(value=0.85, required_missing=[])
        assert score.meets_threshold(0.80)
        assert not score.meets_threshold(0.90)

    def test_convergence_score_with_required_missing(self) -> None:
        score = ConvergenceScore(
            value=0.85,
            required_missing=[SignalType.DEVICE],
        )
        # Mesmo com score alto, sinal obrigatorio ausente → nao atende
        assert not score.meets_threshold(0.80)


# ── Testes do SigningGateway ──────────────────────────────────────────


class TestSigningGateway:

    def test_successful_signing(self) -> None:
        """Assinatura com todos os sinais e score suficiente → sucesso."""
        store = InMemorySignatureStore()
        audit = InMemoryAuditEmitter()
        gateway = SigningGateway(store=store, audit=audit)

        request = make_full_request(act_gravity=ActGravity.PETITION)
        result = gateway.sign(request)

        assert result.success
        assert result.signature is not None
        assert result.convergence_score is not None
        assert result.threshold_achieved >= 0.80
        assert len(store.signatures) == 1
        assert len(audit.events) == 1
        assert audit.events[0][0] == "signing_approved"

    def test_rejected_for_low_score(self) -> None:
        """Score abaixo do threshold → rejeicao."""
        gateway = SigningGateway()

        # Requisicao para sentenca (threshold 0.95) com sinais fracos
        request = SigningRequest(
            event_hash="hash-001",
            process_id="proc-001",
            fsm_state="CONCLUSO_JUIZ",
            fsm_transition="HOMOLOGADO",
            act_gravity=ActGravity.SENTENCE,
            actor_id="juiz-001",
            actor_type="JUIZ_COORDENADOR",
            device=DeviceSignal(
                device_id="dev",
                device_signature="sig",
                key_origin="software",  # score baixo
                platform="linux",
            ),
            context=ContextSignal(
                fsm_state="CONCLUSO_JUIZ",
                fsm_transition="HOMOLOGADO",
                actor_authorized=True,
                transition_valid=True,
            ),
            temporal=TemporalSignal(
                client_timestamp=datetime.now(UTC),
            ),
        )

        result = gateway.sign(request)
        assert not result.success
        assert result.rejection_reason

    def test_rejected_for_missing_required_signal(self) -> None:
        """Sinal obrigatorio ausente → rejeicao."""
        audit = InMemoryAuditEmitter()
        gateway = SigningGateway(audit=audit)

        # Sem device (obrigatorio) e sem temporal (obrigatorio)
        request = SigningRequest(
            event_hash="hash-001",
            process_id="proc-001",
            fsm_state="X",
            fsm_transition="Y",
            act_gravity=ActGravity.VIEW,
            actor_id="actor-001",
            actor_type="PARTE",
            biometry=BiometrySignal(
                method="face_id",
                match_score=0.99,
            ),
        )

        result = gateway.sign(request)
        assert not result.success
        assert "device" in result.required_missing or "temporal" in result.required_missing
        assert len(audit.events) == 1
        assert audit.events[0][0] == "signing_rejected"

    def test_hash_chaining(self) -> None:
        """Assinaturas consecutivas sao encadeadas por hash."""
        store = InMemorySignatureStore()
        gateway = SigningGateway(store=store)

        # Primeira assinatura
        req1 = make_full_request()
        result1 = gateway.sign(req1)
        assert result1.success

        # Segunda assinatura
        req2 = make_full_request()
        result2 = gateway.sign(req2)
        assert result2.success

        # Verificar encadeamento
        sig1 = store.signatures[0]
        sig2 = store.signatures[1]
        assert sig2.hash_anterior == sig1.hash
        assert sig1.hash_anterior == ""  # primeira nao tem anterior

    def test_audit_dict_completeness(self) -> None:
        """audit_dict contem todos os campos exigidos pelo CPC Art. 195."""
        store = InMemorySignatureStore()
        gateway = SigningGateway(store=store)

        request = make_full_request()
        result = gateway.sign(request)

        audit = result.signature.to_audit_dict()

        # CPC Art. 195 — campos obrigatorios
        assert "actor_id" in audit        # autenticidade
        assert "event_hash" in audit      # integridade
        assert "timestamp" in audit       # temporalidade
        assert "hash" in audit            # nao-repudio
        assert "hash_anterior" in audit   # conservacao (encadeamento)
        assert "signals" in audit         # prova composta
        assert "convergence" in audit     # score de certeza


# ── Testes do Verifier ────────────────────────────────────────────────


class TestVerifier:

    def test_valid_signature_passes_verification(self) -> None:
        """Assinatura integra passa na verificacao."""
        sig = ConvergenceSignature(
            actor_id="actor-001",
            actor_type="CONCILIADOR",
            event_hash="hash-001",
            signals=[
                Signal(SignalType.DEVICE, score=0.95),
                Signal(SignalType.CONTEXT, score=1.0),
                Signal(SignalType.TEMPORAL, score=1.0),
            ],
        )
        sig.compute_convergence()

        verifier = SignatureVerifier()
        result = verifier.verify(sig)
        assert result.valid

    def test_tampered_signature_fails_verification(self) -> None:
        """Assinatura adulterada falha na verificacao."""
        sig = ConvergenceSignature(
            actor_id="actor-001",
            actor_type="CONCILIADOR",
            event_hash="hash-001",
            signals=[
                Signal(SignalType.DEVICE, score=0.95),
                Signal(SignalType.CONTEXT, score=1.0),
                Signal(SignalType.TEMPORAL, score=1.0),
            ],
        )
        sig.compute_convergence()

        # Adulterar
        sig.actor_id = "IMPOSTOR"

        verifier = SignatureVerifier()
        result = verifier.verify(sig)
        assert not result.valid

    def test_chain_verification(self) -> None:
        """Cadeia de assinaturas com encadeamento correto passa."""
        sig1 = ConvergenceSignature(
            actor_id="actor-001",
            actor_type="CONCILIADOR",
            event_hash="hash-001",
            hash_anterior="",
            signals=[Signal(SignalType.DEVICE, score=0.95),
                     Signal(SignalType.CONTEXT, score=1.0),
                     Signal(SignalType.TEMPORAL, score=1.0)],
        )
        sig1.compute_convergence()

        sig2 = ConvergenceSignature(
            actor_id="actor-002",
            actor_type="JUIZ_COORDENADOR",
            event_hash="hash-002",
            hash_anterior=sig1.hash,
            signals=[Signal(SignalType.DEVICE, score=0.90),
                     Signal(SignalType.CONTEXT, score=1.0),
                     Signal(SignalType.TEMPORAL, score=1.0)],
        )
        sig2.compute_convergence()

        verifier = SignatureVerifier()
        result = verifier.verify_chain([sig1, sig2])
        assert result.valid

    def test_broken_chain_fails(self) -> None:
        """Cadeia com encadeamento quebrado falha."""
        sig1 = ConvergenceSignature(
            actor_id="actor-001",
            actor_type="CONCILIADOR",
            event_hash="hash-001",
            signals=[Signal(SignalType.DEVICE, score=0.95),
                     Signal(SignalType.CONTEXT, score=1.0),
                     Signal(SignalType.TEMPORAL, score=1.0)],
        )
        sig1.compute_convergence()

        sig2 = ConvergenceSignature(
            actor_id="actor-002",
            actor_type="JUIZ_COORDENADOR",
            event_hash="hash-002",
            hash_anterior="HASH_ADULTERADO",  # encadeamento quebrado
            signals=[Signal(SignalType.DEVICE, score=0.90),
                     Signal(SignalType.CONTEXT, score=1.0),
                     Signal(SignalType.TEMPORAL, score=1.0)],
        )
        sig2.compute_convergence()

        verifier = SignatureVerifier()
        result = verifier.verify_chain([sig1, sig2])
        assert not result.valid


# ── Testes de integracao (Gateway + Verifier) ─────────────────────────


class TestIntegration:

    def test_sign_then_verify(self) -> None:
        """Assinar e depois verificar — fluxo completo."""
        store = InMemorySignatureStore()
        gateway = SigningGateway(store=store)
        verifier = SignatureVerifier()

        # Assinar
        request = make_full_request()
        result = gateway.sign(request)
        assert result.success

        # Verificar
        verification = verifier.verify(result.signature)
        assert verification.valid

    def test_sign_chain_then_verify(self) -> None:
        """Assinar multiplos atos e verificar a cadeia completa."""
        store = InMemorySignatureStore()
        gateway = SigningGateway(store=store)
        verifier = SignatureVerifier()

        # 3 assinaturas consecutivas
        for i in range(3):
            request = make_full_request()
            request.event_hash = f"hash-{i}"
            result = gateway.sign(request)
            assert result.success

        # Verificar cadeia
        chain_result = verifier.verify_chain(store.signatures)
        assert chain_result.valid

    def test_view_requires_less_than_sentence(self) -> None:
        """Consulta (VIEW) aceita com sinais que sentenca rejeitaria."""
        store = InMemorySignatureStore()
        gateway = SigningGateway(store=store)

        # Requisicao com sinais basicos — software key (score 0.50)
        # e drift temporal moderado, sem biometria
        now = datetime.now(UTC)
        basic_request = SigningRequest(
            event_hash="hash-view",
            process_id="proc-001",
            fsm_state="CADASTRADO",
            fsm_transition="SESSAO_AGENDADA",
            act_gravity=ActGravity.VIEW,  # threshold 0.60
            actor_id="actor-001",
            actor_type="PARTE",
            device=DeviceSignal(
                device_id="dev",
                device_signature="sig",
                key_origin="software",  # score baixo (~0.50)
                platform="linux",
            ),
            context=ContextSignal(
                fsm_state="CADASTRADO",
                fsm_transition="SESSAO_AGENDADA",
                actor_authorized=True,
                transition_valid=True,
            ),
            temporal=TemporalSignal(
                client_timestamp=now,
                server_timestamp=now + timedelta(seconds=60),  # drift 60s → score 0.60
                ntp_synced=False,  # reduz score
            ),
        )

        # VIEW aceita (score ~0.72, threshold 0.60)
        view_result = gateway.sign(basic_request)
        assert view_result.success

        # SENTENCE rejeita com os mesmos sinais (threshold 0.95)
        basic_request.act_gravity = ActGravity.SENTENCE
        sentence_result = gateway.sign(basic_request)
        assert not sentence_result.success
