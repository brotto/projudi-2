"""
Signing Gateway — orquestrador do fluxo de assinatura.

Coleta sinais, calcula convergencia, valida contra threshold do ato,
e produz a ConvergenceSignature final.

E o ponto unico de entrada para toda assinatura no sistema.
Analogia: como o ProjudiUploader + AutoSigningOrchestrator do Assinador
Projudi original, mas operando sobre sinais de convergencia em vez de
CMS/PKCS#7 isolado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any, Protocol
from uuid import uuid4

from juizo.signing.convergence import (
    ActGravity,
    ConvergenceScore,
    ConvergenceSignature,
    DEFAULT_THRESHOLDS,
    DEFAULT_WEIGHTS,
    Signal,
    SignalWeight,
)
from juizo.signing.signals import (
    BiometrySignal,
    ContextSignal,
    DeviceSignal,
    ICPBrasilSignal,
    TemporalSignal,
)


class SignatureStore(Protocol):
    """Interface para persistencia de assinaturas (append-only)."""

    def append(self, signature: ConvergenceSignature) -> None:
        """Persiste assinatura no log imutavel."""
        ...

    def get_last_hash(self, process_id: str) -> str:
        """Retorna hash da ultima assinatura do processo (encadeamento)."""
        ...


class AuditEmitter(Protocol):
    """Interface para emissao de eventos de auditoria."""

    def emit(self, event_type: str, data: dict[str, Any]) -> None:
        """Emite evento de auditoria."""
        ...


@dataclass
class SigningRequest:
    """
    Requisicao de assinatura — tudo que o gateway precisa para assinar.

    Reune: o que esta sendo assinado, quem esta assinando,
    os sinais coletados, e o nivel de certeza exigido.
    """

    # O que
    event_hash: str  # hash SHA-256 do evento/conteudo
    process_id: str
    fsm_state: str
    fsm_transition: str
    act_gravity: ActGravity

    # Quem
    actor_id: str
    actor_type: str

    # Sinais coletados
    biometry: BiometrySignal | None = None
    device: DeviceSignal | None = None
    context: ContextSignal | None = None
    temporal: TemporalSignal | None = None
    icp_brasil: ICPBrasilSignal | None = None

    # Payload adicional
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SigningResult:
    """Resultado da operacao de assinatura."""

    success: bool
    signature: ConvergenceSignature | None = None
    convergence_score: ConvergenceScore | None = None
    rejection_reason: str = ""
    required_missing: list[str] = field(default_factory=list)
    threshold_required: float = 0.0
    threshold_achieved: float = 0.0


class SigningGateway:
    """
    Gateway de assinatura — ponto unico de entrada.

    Fluxo:
    1. Recebe SigningRequest com sinais coletados
    2. Converte sinais especificos em Signal generico
    3. Calcula ConvergenceScore
    4. Valida contra threshold do ActGravity
    5. Se aprovado, gera ConvergenceSignature
    6. Persiste no log imutavel
    7. Emite evento de auditoria
    8. Retorna SigningResult

    Se ICP-Brasil presente, a assinatura CAdES e armazenada junto
    como sinal adicional (interoperabilidade).
    """

    def __init__(
        self,
        store: SignatureStore | None = None,
        audit: AuditEmitter | None = None,
        weights: list[SignalWeight] | None = None,
        thresholds: dict[ActGravity, float] | None = None,
    ) -> None:
        self.store = store
        self.audit = audit
        self.weights = weights or DEFAULT_WEIGHTS
        self.thresholds = thresholds or DEFAULT_THRESHOLDS

    def sign(self, request: SigningRequest) -> SigningResult:
        """
        Executa o fluxo completo de assinatura.

        Retorna SigningResult com sucesso ou rejeicao detalhada.
        Nunca lanca excecao por score insuficiente — retorna resultado.
        """
        # 1. Coletar sinais
        signals = self._collect_signals(request)

        # 2. Buscar hash anterior (encadeamento)
        hash_anterior = ""
        if self.store:
            hash_anterior = self.store.get_last_hash(request.process_id)

        # 3. Construir assinatura
        signature = ConvergenceSignature(
            id=uuid4(),
            actor_id=request.actor_id,
            actor_type=request.actor_type,
            event_hash=request.event_hash,
            process_id=request.process_id,
            fsm_state=request.fsm_state,
            fsm_transition=request.fsm_transition,
            signals=signals,
            timestamp=datetime.now(UTC),
            hash_anterior=hash_anterior,
        )

        # Adicionar dados ICP-Brasil se presente
        if request.icp_brasil:
            signature.icp_brasil_signature = request.icp_brasil.cades_signature
            signature.icp_brasil_certificate_cn = request.icp_brasil.certificate_cn
            signature.icp_brasil_certificate_serial = request.icp_brasil.certificate_serial
            signature.icp_brasil_issuer = request.icp_brasil.issuer_cn

        # 4. Calcular convergencia
        score = signature.compute_convergence(self.weights)

        # 5. Validar contra threshold
        threshold = self.thresholds.get(request.act_gravity, 0.80)

        if not score.meets_threshold(threshold):
            # Rejeitar — score insuficiente ou sinal obrigatorio ausente
            result = SigningResult(
                success=False,
                signature=None,
                convergence_score=score,
                threshold_required=threshold,
                threshold_achieved=score.value,
                required_missing=[s.value for s in score.required_missing],
                rejection_reason=self._build_rejection_reason(score, threshold),
            )

            # Auditar tentativa rejeitada
            if self.audit:
                self.audit.emit("signing_rejected", {
                    "actor_id": request.actor_id,
                    "process_id": request.process_id,
                    "act_gravity": request.act_gravity.value,
                    "score": score.value,
                    "threshold": threshold,
                    "reason": result.rejection_reason,
                })

            return result

        # 6. Recalcular hash final (apos todos os campos preenchidos)
        signature.hash = signature._compute_hash()

        # 7. Persistir
        if self.store:
            self.store.append(signature)

        # 8. Auditar sucesso
        if self.audit:
            self.audit.emit("signing_approved", signature.to_audit_dict())

        return SigningResult(
            success=True,
            signature=signature,
            convergence_score=score,
            threshold_required=threshold,
            threshold_achieved=score.value,
        )

    def _collect_signals(self, request: SigningRequest) -> list[Signal]:
        """Converte sinais especificos em sinais genericos."""
        signals: list[Signal] = []

        if request.biometry:
            signals.append(request.biometry.to_signal())

        if request.device:
            signals.append(request.device.to_signal())

        if request.context:
            signals.append(request.context.to_signal())

        if request.temporal:
            signals.append(request.temporal.to_signal())

        if request.icp_brasil:
            signals.append(request.icp_brasil.to_signal())

        return signals

    def _build_rejection_reason(
        self,
        score: ConvergenceScore,
        threshold: float,
    ) -> str:
        """Constroi mensagem descritiva de rejeicao."""
        reasons = []

        if score.required_missing:
            missing_names = ", ".join(s.value for s in score.required_missing)
            reasons.append(f"Sinais obrigatorios ausentes: {missing_names}")

        if score.value < threshold:
            reasons.append(
                f"Score de convergencia ({score.value:.2f}) abaixo do "
                f"minimo exigido ({threshold:.2f})"
            )

        return ". ".join(reasons) if reasons else "Motivo desconhecido"
