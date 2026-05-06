"""
Sinais de identidade para o modelo de convergencia.

Cada sinal e uma evidencia independente de autoria. Nenhum sinal isolado
e suficiente — a forca esta na convergencia.

Analogia: um tribunal nao condena com base em uma unica prova.
Condena quando multiplas provas independentes convergem para a mesma conclusao.
O modelo de assinatura segue a mesma logica.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any

from juizo.signing.convergence import Signal, SignalType


# ── Sinal biometrico ─────────────────────────────────────────────────

@dataclass
class BiometrySignal:
    """
    Sinal biometrico — prova de que a pessoa fisica estava presente no momento do ato.

    A biometria e capturada NO MOMENTO do ato, nao numa AR meses antes.
    O hash biometrico e comparado localmente (Secure Enclave / TEE) — o template
    biometrico NUNCA sai do dispositivo.

    LGPD Art. 5-II: dados biometricos = dados sensiveis.
    LGPD Art. 11-II-a: base legal = obrigacao legal/regulatoria.
    """

    method: str  # "face_id", "touch_id", "fingerprint", "voice"
    match_score: float  # 0.0 a 1.0 — confianca do match local
    captured_on_device: bool = True  # biometria nunca deve sair do dispositivo
    device_tee: str = ""  # "secure_enclave", "trustzone", "tpm"

    def to_signal(self) -> Signal:
        """Converte para sinal generico."""
        # Hash do metodo + score — NEM o template NEM a imagem saem do dispositivo
        proof_data = f"{self.method}:{self.match_score}:{self.device_tee}"
        proof = hashlib.sha256(proof_data.encode()).hexdigest()

        return Signal(
            signal_type=SignalType.BIOMETRY,
            score=self.match_score,
            metadata={
                "method": self.method,
                "captured_on_device": self.captured_on_device,
                "device_tee": self.device_tee,
            },
            proof=proof,
        )


# ── Sinal de dispositivo ─────────────────────────────────────────────

@dataclass
class DeviceSignal:
    """
    Sinal de dispositivo — prova de que o dispositivo registrado foi usado.

    A chave privada reside no Secure Enclave / TPM / Android Keystore.
    E nao-exportavel por design do hardware. A assinatura do dispositivo
    prova que o dispositivo especifico esteve presente.

    O score aumenta com o tempo de uso do dispositivo (confianca acumulada).
    """

    device_id: str  # hash da chave publica do dispositivo
    device_signature: str  # assinatura Ed25519/ECDSA do challenge
    key_origin: str  # "secure_enclave", "tpm", "android_keystore", "software"
    known_since: datetime | None = None  # quando o dispositivo foi registrado
    platform: str = ""  # "ios", "macos", "android", "windows", "linux"
    ip_address: str = ""
    user_agent: str = ""

    def to_signal(self) -> Signal:
        """Converte para sinal generico."""
        # Score baseado na origem da chave e tempo de conhecimento
        base_score = {
            "secure_enclave": 0.95,
            "tpm": 0.90,
            "android_keystore": 0.85,
            "software": 0.50,
        }.get(self.key_origin, 0.30)

        # Bonus por tempo de uso (max +0.05)
        if self.known_since:
            days_known = (datetime.now(UTC) - self.known_since).days
            time_bonus = min(0.05, days_known / 365 * 0.05)
            base_score = min(1.0, base_score + time_bonus)

        return Signal(
            signal_type=SignalType.DEVICE,
            score=round(base_score, 4),
            metadata={
                "device_id": self.device_id,
                "key_origin": self.key_origin,
                "platform": self.platform,
                "ip_address": self.ip_address,
                "known_since": self.known_since.isoformat() if self.known_since else None,
            },
            proof=self.device_signature,
        )


# ── Sinal de contexto processual ─────────────────────────────────────

@dataclass
class ContextSignal:
    """
    Sinal de contexto — prova de que o ato faz sentido dentro do fluxo processual.

    A FSM valida que:
    1. O ator tem papel autorizado neste estado
    2. A transicao tentada e valida a partir do estado atual
    3. O ato e coerente com a fase processual

    Se a FSM aceita a transicao, o contexto e coerente → score alto.
    Se requer override (ex: juiz coordenador corrigindo estado), score menor.
    """

    fsm_state: str
    fsm_transition: str
    actor_authorized: bool  # FSM validou permissao do ator
    transition_valid: bool  # FSM validou a transicao
    override: bool = False  # ato executado com override de permissao

    def to_signal(self) -> Signal:
        """Converte para sinal generico."""
        if not self.transition_valid:
            # Transicao invalida → score 0
            score = 0.0
        elif not self.actor_authorized:
            # Ator nao autorizado → score 0
            score = 0.0
        elif self.override:
            # Override → score reduzido (valido mas atipico)
            score = 0.60
        else:
            # Tudo normal → score maximo
            score = 1.0

        return Signal(
            signal_type=SignalType.CONTEXT,
            score=score,
            metadata={
                "fsm_state": self.fsm_state,
                "fsm_transition": self.fsm_transition,
                "actor_authorized": self.actor_authorized,
                "transition_valid": self.transition_valid,
                "override": self.override,
            },
            proof=hashlib.sha256(
                f"{self.fsm_state}:{self.fsm_transition}:{self.actor_authorized}".encode()
            ).hexdigest(),
        )


# ── Sinal temporal ────────────────────────────────────────────────────

@dataclass
class TemporalSignal:
    """
    Sinal temporal — prova de QUANDO o ato foi praticado.

    Tres camadas de temporalidade:
    1. Timestamp do cliente (declarado pelo assinante — signingTime)
    2. Timestamp do servidor (registrado no evento)
    3. Carimbo de tempo RFC 3161 de ACT ICP-Brasil (prova independente — AD-RT)

    A divergencia entre camadas reduz o score.
    CPC Art. 195: temporalidade e requisito obrigatorio.
    """

    client_timestamp: datetime
    server_timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    rfc3161_token: bytes | None = None  # carimbo de ACT ICP-Brasil (Fase 4)
    rfc3161_tsa: str = ""  # Autoridade de Carimbo do Tempo
    hash_anterior: str = ""  # hash da assinatura anterior (encadeamento)
    ntp_synced: bool = True  # cliente sincronizado com NTP

    def to_signal(self) -> Signal:
        """Converte para sinal generico."""
        # Score baseado na consistencia temporal
        drift = abs((self.server_timestamp - self.client_timestamp).total_seconds())

        if drift < 5:
            # Menos de 5s de diferenca → excelente
            score = 1.0
        elif drift < 30:
            # Menos de 30s → aceitavel
            score = 0.90
        elif drift < 300:
            # Menos de 5min → suspeito mas valido
            score = 0.60
        else:
            # Mais de 5min → algo errado
            score = 0.20

        # Bonus por NTP sync
        if not self.ntp_synced:
            score *= 0.80

        # Bonus por carimbo RFC 3161
        if self.rfc3161_token is not None:
            score = min(1.0, score + 0.10)

        return Signal(
            signal_type=SignalType.TEMPORAL,
            score=round(score, 4),
            metadata={
                "client_timestamp": self.client_timestamp.isoformat(),
                "server_timestamp": self.server_timestamp.isoformat(),
                "drift_seconds": round(drift, 2),
                "ntp_synced": self.ntp_synced,
                "rfc3161_present": self.rfc3161_token is not None,
                "rfc3161_tsa": self.rfc3161_tsa,
                "hash_anterior": self.hash_anterior,
            },
            proof=hashlib.sha256(
                f"{self.server_timestamp.isoformat()}:{self.hash_anterior}".encode()
            ).hexdigest(),
        )


# ── Sinal ICP-Brasil (interoperabilidade) ────────────────────────────

@dataclass
class ICPBrasilSignal:
    """
    Sinal ICP-Brasil — certificado qualificado para interoperabilidade.

    Este sinal NAO e obrigatorio no modelo de convergencia. E um sinal
    bonus que aumenta o score e garante interoperabilidade com sistemas
    externos (PJe, eProc, PDPJ-Br, cartórios).

    Quando presente, a assinatura CAdES completa e armazenada junto
    com o registro de convergencia.

    DOC-ICP-15: CAdES AD-RB minimo, AD-RT recomendado.
    DOC-ICP-15.01: atributos obrigatorios (contentType, messageDigest,
    signingCertificateV2, sigPolicyId, signingTime).
    """

    certificate_cn: str  # Common Name do certificado
    certificate_serial: str  # Numero de serie hex
    issuer_cn: str  # AC emissora
    certificate_type: str  # "A1", "A3", "A3_PF", "A4_PF", "cloud"
    cades_signature: bytes = b""  # assinatura CAdES/CMS completa
    ocsp_response: bytes = b""  # resposta OCSP no momento da assinatura
    chain_valid: bool = False  # cadeia validada ate AC Raiz ICP-Brasil
    not_revoked: bool = False  # OCSP/CRL confirma nao-revogacao
    psc_provider: str = ""  # "birdid", "vidaas", "govbr" (se cloud)
    psc_transaction_id: str = ""  # ID da transacao no PSC

    def to_signal(self) -> Signal:
        """Converte para sinal generico."""
        # Score baseado na qualidade da validacao
        if not self.chain_valid:
            score = 0.20  # cadeia invalida → baixa confianca
        elif not self.not_revoked:
            score = 0.10  # certificado revogado → quase zero
        else:
            # Cadeia valida + nao revogado → score por tipo de certificado
            score = {
                "A3": 0.95,
                "A3_PF": 0.95,
                "A4_PF": 0.98,
                "cloud": 0.90,  # PSC com MFA
                "A1": 0.70,     # chave em software (sendo descontinuado)
            }.get(self.certificate_type, 0.50)

        return Signal(
            signal_type=SignalType.ICP_BRASIL,
            score=round(score, 4),
            metadata={
                "cn": self.certificate_cn,
                "serial": self.certificate_serial,
                "issuer": self.issuer_cn,
                "type": self.certificate_type,
                "chain_valid": self.chain_valid,
                "not_revoked": self.not_revoked,
                "psc_provider": self.psc_provider,
                "psc_transaction_id": self.psc_transaction_id,
            },
            proof=hashlib.sha256(
                f"{self.certificate_serial}:{self.issuer_cn}:{self.chain_valid}".encode()
            ).hexdigest(),
        )
