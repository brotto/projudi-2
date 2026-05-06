"""
Verificador de assinaturas convergentes.

Valida a integridade de uma assinatura existente:
- Hash encadeado (nao foi adulterado)
- Score de convergencia (recalcula e compara)
- Consistencia temporal (timestamps fazem sentido)
- Cadeia de assinaturas (toda a cadeia do processo e integra)

CPC Art. 195: integridade e conservacao.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from juizo.signing.convergence import (
    ActGravity,
    ConvergenceSignature,
    DEFAULT_THRESHOLDS,
    DEFAULT_WEIGHTS,
    SignalWeight,
)


@dataclass
class VerificationResult:
    """Resultado da verificacao de uma assinatura."""

    valid: bool
    checks: list[VerificationCheck] = field(default_factory=list)

    @property
    def summary(self) -> str:
        failed = [c for c in self.checks if not c.passed]
        if not failed:
            return "Assinatura valida — todos os checks passaram."
        msgs = "; ".join(f"{c.name}: {c.message}" for c in failed)
        return f"Assinatura invalida — {msgs}"


@dataclass
class VerificationCheck:
    """Um check individual de verificacao."""

    name: str
    passed: bool
    message: str = ""


class SignatureVerifier:
    """
    Verificador de assinaturas convergentes.

    Executa checks de integridade sobre assinaturas individuais
    e sobre cadeias de assinaturas de um processo.
    """

    def __init__(
        self,
        weights: list[SignalWeight] | None = None,
        thresholds: dict[ActGravity, float] | None = None,
    ) -> None:
        self.weights = weights or DEFAULT_WEIGHTS
        self.thresholds = thresholds or DEFAULT_THRESHOLDS

    def verify(
        self,
        signature: ConvergenceSignature,
        expected_previous_hash: str = "",
    ) -> VerificationResult:
        """
        Verifica integridade de uma assinatura individual.

        Checks:
        1. Hash integrity — hash recalculado confere com o armazenado
        2. Chain integrity — hash_anterior confere com assinatura anterior
        3. Convergence integrity — score recalculado confere
        4. Signal consistency — sinais fazem sentido
        """
        checks: list[VerificationCheck] = []

        # 1. Hash integrity
        recalculated = signature._compute_hash()
        hash_ok = recalculated == signature.hash
        checks.append(VerificationCheck(
            name="hash_integrity",
            passed=hash_ok,
            message="" if hash_ok else (
                f"Hash adulterado. Esperado: {signature.hash[:16]}..., "
                f"Calculado: {recalculated[:16]}..."
            ),
        ))

        # 2. Chain integrity (se hash anterior fornecido)
        if expected_previous_hash:
            chain_ok = signature.hash_anterior == expected_previous_hash
            checks.append(VerificationCheck(
                name="chain_integrity",
                passed=chain_ok,
                message="" if chain_ok else (
                    f"Cadeia quebrada. Esperado: {expected_previous_hash[:16]}..., "
                    f"Encontrado: {signature.hash_anterior[:16]}..."
                ),
            ))

        # 3. Convergence recalculation
        original_score = signature.convergence_score
        recalc_score = signature.compute_convergence(self.weights)
        if original_score:
            score_ok = abs(recalc_score.value - original_score.value) < 0.001
            checks.append(VerificationCheck(
                name="convergence_integrity",
                passed=score_ok,
                message="" if score_ok else (
                    f"Score diverge. Original: {original_score.value}, "
                    f"Recalculado: {recalc_score.value}"
                ),
            ))

        # 4. Signals present
        has_signals = len(signature.signals) > 0
        checks.append(VerificationCheck(
            name="signals_present",
            passed=has_signals,
            message="" if has_signals else "Nenhum sinal de identidade presente",
        ))

        # 5. Actor present
        has_actor = bool(signature.actor_id and signature.actor_type)
        checks.append(VerificationCheck(
            name="actor_identified",
            passed=has_actor,
            message="" if has_actor else "Ator nao identificado",
        ))

        all_valid = all(c.passed for c in checks)
        return VerificationResult(valid=all_valid, checks=checks)

    def verify_chain(
        self,
        signatures: list[ConvergenceSignature],
    ) -> VerificationResult:
        """
        Verifica integridade de toda a cadeia de assinaturas de um processo.

        Percorre do primeiro ao ultimo, verificando:
        - Cada assinatura individualmente
        - O encadeamento hash_anterior → hash entre cada par
        - Ordem temporal (timestamps crescentes)
        """
        checks: list[VerificationCheck] = []

        if not signatures:
            checks.append(VerificationCheck(
                name="chain_not_empty",
                passed=False,
                message="Cadeia vazia",
            ))
            return VerificationResult(valid=False, checks=checks)

        # Verificar primeira assinatura
        first = signatures[0]
        first_result = self.verify(first)
        checks.extend(first_result.checks)

        # Verificar encadeamento
        for i in range(1, len(signatures)):
            prev = signatures[i - 1]
            curr = signatures[i]

            # Verificar assinatura individual
            individual = self.verify(curr, expected_previous_hash=prev.hash)
            checks.extend(individual.checks)

            # Verificar ordem temporal
            temporal_ok = curr.timestamp >= prev.timestamp
            checks.append(VerificationCheck(
                name=f"temporal_order_{i}",
                passed=temporal_ok,
                message="" if temporal_ok else (
                    f"Assinatura {i} tem timestamp anterior a assinatura {i-1}"
                ),
            ))

        all_valid = all(c.passed for c in checks)
        return VerificationResult(valid=all_valid, checks=checks)
