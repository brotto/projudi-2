"""
Log de auditoria imutavel.

Cada entrada e encadeada por hash SHA-256 (anti-adulteracao).
O log e append-only — nunca se edita ou deleta uma entrada.

Projetado para cumprir simultaneamente:
- CPC Art. 195 (integridade, nao-repudio, conservacao)
- LGPD Art. 37 (registro de operacoes de tratamento de dados pessoais)
- Marco Civil Art. 13/15 (registros de conexao e acesso)
- DOC-ICP-17 (logs de PSC por 6 anos)
- Res. CNJ 396/2021 (comunicacao de incidentes)
- Res. CNJ 185/2013 (monitoramento de disponibilidade a cada 5 min)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Any, Protocol
from uuid import UUID, uuid4


class AuditCategory(str, Enum):
    """
    Categorias de eventos de auditoria.

    Cada categoria tem prazos de retencao distintos.
    """

    # Assinatura digital — vida util do documento
    SIGNING = "signing"

    # Autenticacao / login — 1 ano (Marco Civil Art. 13)
    AUTH = "auth"

    # Acesso a processo — 6 meses minimo (Marco Civil Art. 15)
    ACCESS = "access"

    # Transicao de estado FSM — vida util do processo
    TRANSITION = "transition"

    # Operacao de PSC cloud — 6 anos (DOC-ICP-17)
    PSC = "psc"

    # Verificacao de certificado (OCSP/CRL) — vida util do certificado
    CERTIFICATE = "certificate"

    # Disponibilidade do sistema — Res. CNJ 185/2013
    AVAILABILITY = "availability"

    # Incidente de seguranca — indefinido (Res. CNJ 396/2021)
    INCIDENT = "incident"

    # Tratamento de dados pessoais — LGPD Art. 37
    DATA_TREATMENT = "data_treatment"


@dataclass
class AuditEntry:
    """
    Entrada imutavel no log de auditoria.

    Cada entrada e auto-contida: carrega todos os dados necessarios
    para auditoria futura, incluindo o hash da entrada anterior
    (encadeamento para deteccao de adulteracao).
    """

    id: UUID = field(default_factory=uuid4)
    category: AuditCategory = AuditCategory.ACCESS
    event_type: str = ""  # "signing_approved", "login_success", etc.
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Quem
    actor_id: str = ""
    actor_type: str = ""
    actor_ip: str = ""
    actor_device: str = ""  # hash do device_id

    # O que
    resource_type: str = ""  # "processo", "assinatura", "certificado"
    resource_id: str = ""

    # Detalhes
    data: dict[str, Any] = field(default_factory=dict)
    result: str = ""  # "success", "failure", "rejected"

    # Encadeamento
    hash_anterior: str = ""
    hash: str = ""

    def __post_init__(self) -> None:
        if not self.hash:
            self.hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Hash SHA-256 da entrada — integridade e encadeamento."""
        content = json.dumps({
            "id": str(self.id),
            "category": self.category.value,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "actor_id": self.actor_id,
            "resource_id": self.resource_id,
            "data": self.data,
            "result": self.result,
            "hash_anterior": self.hash_anterior,
        }, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(content.encode()).hexdigest()


class AuditStore(Protocol):
    """Interface para persistencia do log de auditoria."""

    def append(self, entry: AuditEntry) -> None:
        """Persiste entrada no log (append-only)."""
        ...

    def get_last_hash(self) -> str:
        """Retorna hash da ultima entrada (encadeamento)."""
        ...

    def query(
        self,
        category: AuditCategory | None = None,
        actor_id: str | None = None,
        resource_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """Consulta entradas do log com filtros."""
        ...


class AuditLog:
    """
    Log de auditoria do sistema Juizo.

    Ponto unico de registro de eventos auditaveis.
    Encadeia automaticamente cada entrada com a anterior.

    Uso:
        audit = AuditLog(store=SqlAuditStore(session))
        audit.log_signing("actor_123", "process_456", {...})
        audit.log_access("actor_123", "process_456", "read")
    """

    def __init__(self, store: AuditStore) -> None:
        self.store = store

    def _log(
        self,
        category: AuditCategory,
        event_type: str,
        actor_id: str = "",
        actor_type: str = "",
        actor_ip: str = "",
        actor_device: str = "",
        resource_type: str = "",
        resource_id: str = "",
        data: dict[str, Any] | None = None,
        result: str = "success",
    ) -> AuditEntry:
        """Registra uma entrada no log com encadeamento automatico."""
        hash_anterior = self.store.get_last_hash()

        entry = AuditEntry(
            category=category,
            event_type=event_type,
            actor_id=actor_id,
            actor_type=actor_type,
            actor_ip=actor_ip,
            actor_device=actor_device,
            resource_type=resource_type,
            resource_id=resource_id,
            data=data or {},
            result=result,
            hash_anterior=hash_anterior,
        )

        self.store.append(entry)
        return entry

    # ── Metodos de conveniencia por categoria ─────────────────────────

    def log_signing(
        self,
        actor_id: str,
        process_id: str,
        signature_data: dict[str, Any],
        result: str = "success",
        **kwargs: Any,
    ) -> AuditEntry:
        """Registra evento de assinatura digital."""
        return self._log(
            category=AuditCategory.SIGNING,
            event_type=f"signing_{result}",
            actor_id=actor_id,
            resource_type="processo",
            resource_id=process_id,
            data=signature_data,
            result=result,
            **kwargs,
        )

    def log_auth(
        self,
        actor_id: str,
        method: str,
        result: str = "success",
        **kwargs: Any,
    ) -> AuditEntry:
        """
        Registra evento de autenticacao.
        Marco Civil Art. 13: retencao minima 1 ano.
        """
        return self._log(
            category=AuditCategory.AUTH,
            event_type=f"auth_{result}",
            actor_id=actor_id,
            data={"method": method},
            result=result,
            **kwargs,
        )

    def log_access(
        self,
        actor_id: str,
        resource_id: str,
        access_type: str = "read",
        **kwargs: Any,
    ) -> AuditEntry:
        """
        Registra evento de acesso a recurso.
        Marco Civil Art. 15: retencao minima 6 meses.
        CPC Art. 195: confidencialidade para segredo de justica.
        """
        return self._log(
            category=AuditCategory.ACCESS,
            event_type=f"access_{access_type}",
            actor_id=actor_id,
            resource_type="processo",
            resource_id=resource_id,
            result="success",
            **kwargs,
        )

    def log_transition(
        self,
        actor_id: str,
        process_id: str,
        state_from: str,
        state_to: str,
        **kwargs: Any,
    ) -> AuditEntry:
        """Registra transicao de estado FSM."""
        return self._log(
            category=AuditCategory.TRANSITION,
            event_type="fsm_transition",
            actor_id=actor_id,
            resource_type="processo",
            resource_id=process_id,
            data={"state_from": state_from, "state_to": state_to},
            **kwargs,
        )

    def log_psc_operation(
        self,
        actor_id: str,
        psc_provider: str,
        transaction_id: str,
        operation: str,
        **kwargs: Any,
    ) -> AuditEntry:
        """
        Registra operacao com PSC (Prestador de Servico de Confianca).
        DOC-ICP-17: retencao 6 anos, analise maxima semanal.
        """
        return self._log(
            category=AuditCategory.PSC,
            event_type=f"psc_{operation}",
            actor_id=actor_id,
            data={
                "psc_provider": psc_provider,
                "transaction_id": transaction_id,
                "operation": operation,
            },
            **kwargs,
        )

    def log_incident(
        self,
        description: str,
        severity: str,
        affected_systems: list[str] | None = None,
        **kwargs: Any,
    ) -> AuditEntry:
        """
        Registra incidente de seguranca.
        Res. CNJ 396/2021 Art. 18: comunicacao imediata ao CPTRIC-PJ.
        LGPD Art. 48: comunicacao a ANPD e titulares.
        """
        return self._log(
            category=AuditCategory.INCIDENT,
            event_type=f"incident_{severity}",
            data={
                "description": description,
                "severity": severity,
                "affected_systems": affected_systems or [],
            },
            result=severity,
            **kwargs,
        )

    def log_data_treatment(
        self,
        actor_id: str,
        data_subject_id: str,
        treatment_type: str,
        legal_basis: str,
        **kwargs: Any,
    ) -> AuditEntry:
        """
        Registra operacao de tratamento de dados pessoais.
        LGPD Art. 37: registro obrigatorio de todas as operacoes.
        """
        return self._log(
            category=AuditCategory.DATA_TREATMENT,
            event_type=f"data_{treatment_type}",
            actor_id=actor_id,
            resource_type="dados_pessoais",
            resource_id=data_subject_id,
            data={
                "treatment_type": treatment_type,
                "legal_basis": legal_basis,
            },
            **kwargs,
        )
