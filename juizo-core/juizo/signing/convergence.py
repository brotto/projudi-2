"""
Modelo de assinatura por convergencia.

A assinatura nao e um ato binario (valida/invalida). E um registro composto
de multiplos sinais independentes, cuja convergencia produz um score de
certeza proporcional a gravidade do ato processual.

Premissa: o que prova que "foi fulano" nao e um unico fator (chave privada),
mas a convergencia de sinais — biometria contemporanea ao ato, dispositivo
conhecido, contexto processual coerente, temporalidade encadeada — cuja
falsificacao simultanea e ordens de magnitude mais dificil que clonar um token.

CPC Art. 195: autenticidade, integridade, temporalidade, nao-repudio,
conservacao, confidencialidade, padroes abertos.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class SignalType(str, Enum):
    """Tipos de sinais que compoem a prova de autoria."""

    # Quem voce E — prova biometrica contemporanea ao ato
    BIOMETRY = "biometry"

    # O que voce TEM — dispositivo conhecido com chave no Secure Enclave/TPM
    DEVICE = "device"

    # Como voce AGE — padrao comportamental consistente
    BEHAVIOR = "behavior"

    # Onde voce ESTA no fluxo — coerencia com o contexto processual (FSM)
    CONTEXT = "context"

    # Quando aconteceu — temporalidade encadeada e verificavel
    TEMPORAL = "temporal"

    # Certificado ICP-Brasil — sinal de interoperabilidade com mundo externo
    ICP_BRASIL = "icp_brasil"

    # Autenticacao GOV.BR — sinal de identidade federada
    GOV_BR = "gov_br"


@dataclass
class SignalWeight:
    """
    Peso de cada tipo de sinal no calculo de convergencia.

    Pesos sao configuraveis por rito e por tipo de ato processual.
    Um despacho de "ciente" exige menos que uma sentenca condenatoria.
    """

    signal_type: SignalType
    weight: float  # 0.0 a 1.0
    required: bool = False  # se True, score = 0 sem este sinal

    def __post_init__(self) -> None:
        if not 0.0 <= self.weight <= 1.0:
            raise ValueError(f"Peso deve ser entre 0.0 e 1.0, recebido: {self.weight}")


@dataclass
class Signal:
    """
    Um sinal individual de identidade, capturado no momento do ato.

    Cada sinal tem um score de confianca (0.0 a 1.0) e metadados
    que permitem auditoria posterior.
    """

    signal_type: SignalType
    score: float  # 0.0 a 1.0 — confianca do sinal individual
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    # Prova criptografica do sinal (hash, assinatura, etc.)
    proof: str = ""

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"Score deve ser entre 0.0 e 1.0, recebido: {self.score}")


@dataclass
class ConvergenceScore:
    """
    Score composto de convergencia — resultado da combinacao de todos os sinais.

    O score e uma media ponderada dos sinais presentes, penalizada pela
    ausencia de sinais obrigatorios.
    """

    value: float  # 0.0 a 1.0 — certeza composta
    signals_present: list[SignalType] = field(default_factory=list)
    signals_missing: list[SignalType] = field(default_factory=list)
    required_missing: list[SignalType] = field(default_factory=list)
    detail: dict[str, float] = field(default_factory=dict)  # score por sinal

    @property
    def is_sufficient(self) -> bool:
        """True se nenhum sinal obrigatorio esta ausente."""
        return len(self.required_missing) == 0

    def meets_threshold(self, threshold: float) -> bool:
        """True se score >= threshold E nenhum obrigatorio ausente."""
        return self.value >= threshold and self.is_sufficient


# ── Niveis de certeza por tipo de ato processual ──────────────────────

class ActGravity(str, Enum):
    """
    Gravidade do ato processual — determina o score minimo exigido.

    A certeza deve ser proporcional a consequencia. Um despacho de "ciente"
    nao precisa do mesmo nivel de prova que uma sentenca.
    """

    # Consulta / leitura — login + dispositivo conhecido basta
    VIEW = "view"

    # Juntada de documento simples
    FILE = "file"

    # Peticao / manifestacao
    PETITION = "petition"

    # Ata / registro de sessao
    RECORD = "record"

    # Acordo entre partes — todas confirmam
    AGREEMENT = "agreement"

    # Decisao / despacho com conteudo decisorio
    DECISION = "decision"

    # Sentenca / homologacao
    SENTENCE = "sentence"


# Thresholds por gravidade — configuraveis por tenant (TJ)
DEFAULT_THRESHOLDS: dict[ActGravity, float] = {
    ActGravity.VIEW: 0.60,
    ActGravity.FILE: 0.70,
    ActGravity.PETITION: 0.80,
    ActGravity.RECORD: 0.80,
    ActGravity.AGREEMENT: 0.85,
    ActGravity.DECISION: 0.90,
    ActGravity.SENTENCE: 0.95,
}

# Pesos padrao dos sinais — configuraveis por tenant (TJ)
DEFAULT_WEIGHTS: list[SignalWeight] = [
    SignalWeight(SignalType.BIOMETRY, weight=0.30, required=False),
    SignalWeight(SignalType.DEVICE, weight=0.25, required=True),
    SignalWeight(SignalType.CONTEXT, weight=0.20, required=True),
    SignalWeight(SignalType.TEMPORAL, weight=0.15, required=True),
    SignalWeight(SignalType.BEHAVIOR, weight=0.10, required=False),
    # Sinais opcionais de interoperabilidade (bonus, nao substituem os acima)
    SignalWeight(SignalType.ICP_BRASIL, weight=0.30, required=False),
    SignalWeight(SignalType.GOV_BR, weight=0.20, required=False),
]


# ── Assinatura convergente ────────────────────────────────────────────

@dataclass
class ConvergenceSignature:
    """
    A assinatura de um ato processual no sistema Juizo.

    Nao e um blob criptografico opaco. E um registro composto, auditavel,
    que carrega a prova completa de autoria — quem, com que, sobre o que,
    quando, e com qual nivel de certeza.

    E a maquina do tempo probatoria: transporta certeza do presente para o futuro.
    """

    id: UUID = field(default_factory=uuid4)

    # ── Quem ──
    actor_id: str = ""
    actor_type: str = ""

    # ── Sobre o que ──
    event_hash: str = ""          # hash SHA-256 do evento/conteudo assinado
    process_id: str = ""
    fsm_state: str = ""           # estado da FSM no momento do ato
    fsm_transition: str = ""      # transicao executada

    # ── Sinais de convergencia ──
    signals: list[Signal] = field(default_factory=list)

    # ── Score calculado ──
    convergence_score: ConvergenceScore | None = None

    # ── Temporalidade ──
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    hash_anterior: str = ""       # encadeamento com assinatura anterior

    # ── ICP-Brasil (quando presente) ──
    icp_brasil_signature: bytes | None = None  # CAdES/CMS completo
    icp_brasil_certificate_cn: str = ""
    icp_brasil_certificate_serial: str = ""
    icp_brasil_issuer: str = ""

    # ── Hash da assinatura completa ──
    hash: str = ""

    def __post_init__(self) -> None:
        if not self.hash:
            self.hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Hash SHA-256 da assinatura — identidade criptografica imutavel."""
        content = json.dumps({
            "id": str(self.id),
            "actor_id": self.actor_id,
            "event_hash": self.event_hash,
            "process_id": self.process_id,
            "fsm_state": self.fsm_state,
            "fsm_transition": self.fsm_transition,
            "signals": [
                {
                    "type": s.signal_type.value,
                    "score": s.score,
                    "timestamp": s.timestamp.isoformat(),
                    "proof": s.proof,
                }
                for s in self.signals
            ],
            "timestamp": self.timestamp.isoformat(),
            "hash_anterior": self.hash_anterior,
            "icp_brasil_certificate_cn": self.icp_brasil_certificate_cn,
            "icp_brasil_certificate_serial": self.icp_brasil_certificate_serial,
        }, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(content.encode()).hexdigest()

    def compute_convergence(
        self,
        weights: list[SignalWeight] | None = None,
    ) -> ConvergenceScore:
        """
        Calcula o score de convergencia a partir dos sinais presentes.

        Algoritmo:
        1. Para cada sinal presente, multiplica score * peso
        2. Soma ponderada / soma de pesos de sinais presentes
        3. Penaliza se sinal obrigatorio ausente (score = 0)
        4. Bonus por sinais ICP-Brasil/GOV.BR (nao substituem, somam)
        """
        weights = weights or DEFAULT_WEIGHTS
        weight_map = {w.signal_type: w for w in weights}
        signal_map = {s.signal_type: s for s in self.signals}

        # Sinais de identidade primarios (nao-ICP, nao-GOV)
        primary_types = {
            SignalType.BIOMETRY,
            SignalType.DEVICE,
            SignalType.CONTEXT,
            SignalType.TEMPORAL,
            SignalType.BEHAVIOR,
        }

        # Sinais de interoperabilidade (bonus)
        interop_types = {
            SignalType.ICP_BRASIL,
            SignalType.GOV_BR,
        }

        # Calculo dos sinais primarios
        weighted_sum = 0.0
        weight_sum = 0.0
        signals_present: list[SignalType] = []
        signals_missing: list[SignalType] = []
        required_missing: list[SignalType] = []
        detail: dict[str, float] = {}

        for signal_type in primary_types:
            w = weight_map.get(signal_type)
            if w is None:
                continue

            signal = signal_map.get(signal_type)
            if signal is not None:
                contribution = signal.score * w.weight
                weighted_sum += contribution
                weight_sum += w.weight
                signals_present.append(signal_type)
                detail[signal_type.value] = signal.score
            else:
                signals_missing.append(signal_type)
                if w.required:
                    required_missing.append(signal_type)

        # Score base (0.0 a 1.0)
        base_score = weighted_sum / weight_sum if weight_sum > 0 else 0.0

        # Bonus por sinais de interoperabilidade (max +0.15)
        interop_bonus = 0.0
        for signal_type in interop_types:
            signal = signal_map.get(signal_type)
            w = weight_map.get(signal_type)
            if signal is not None and w is not None:
                interop_bonus += signal.score * w.weight * 0.5  # bonus moderado
                signals_present.append(signal_type)
                detail[signal_type.value] = signal.score
            elif signal is None and signal_type in signal_map:
                signals_missing.append(signal_type)

        # Score final: base + bonus, capped at 1.0
        final_score = min(1.0, base_score + interop_bonus)

        # Se sinal obrigatorio ausente, zera
        if required_missing:
            final_score = 0.0

        self.convergence_score = ConvergenceScore(
            value=round(final_score, 4),
            signals_present=signals_present,
            signals_missing=signals_missing,
            required_missing=required_missing,
            detail=detail,
        )

        return self.convergence_score

    def to_audit_dict(self) -> dict[str, Any]:
        """
        Serializa para registro de auditoria.

        Contem todos os dados exigidos pelo CPC Art. 195:
        - Autenticidade: actor_id, actor_type, sinais de identidade
        - Integridade: event_hash, hash encadeado
        - Temporalidade: timestamp, sinais temporais
        - Nao-repudio: sinais + provas criptograficas
        - Conservacao: hash imutavel, append-only
        - Padroes abertos: JSON, SHA-256, CAdES quando presente
        """
        return {
            "id": str(self.id),
            "hash": self.hash,
            "actor_id": self.actor_id,
            "actor_type": self.actor_type,
            "event_hash": self.event_hash,
            "process_id": self.process_id,
            "fsm_state": self.fsm_state,
            "fsm_transition": self.fsm_transition,
            "timestamp": self.timestamp.isoformat(),
            "hash_anterior": self.hash_anterior,
            "signals": [
                {
                    "type": s.signal_type.value,
                    "score": s.score,
                    "timestamp": s.timestamp.isoformat(),
                    "metadata": s.metadata,
                    "proof": s.proof,
                }
                for s in self.signals
            ],
            "convergence": {
                "score": self.convergence_score.value if self.convergence_score else 0.0,
                "signals_present": [
                    s.value for s in (self.convergence_score.signals_present
                                      if self.convergence_score else [])
                ],
                "required_missing": [
                    s.value for s in (self.convergence_score.required_missing
                                      if self.convergence_score else [])
                ],
                "detail": self.convergence_score.detail if self.convergence_score else {},
            },
            "icp_brasil": {
                "present": self.icp_brasil_signature is not None,
                "cn": self.icp_brasil_certificate_cn,
                "serial": self.icp_brasil_certificate_serial,
                "issuer": self.icp_brasil_issuer,
            },
        }
