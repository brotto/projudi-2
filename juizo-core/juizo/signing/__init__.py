"""
Modulo de assinatura por convergencia do sistema Juizo.

Implementa o modelo de prova continua de identidade vinculada a intencao,
onde a certeza da autoria de um ato e proporcional a convergencia de
multiplos sinais independentes (biometria, dispositivo, comportamento,
contexto processual, temporalidade).

Referencia legal:
- CPC Art. 195 (7 requisitos: autenticidade, integridade, temporalidade,
  nao-repudio, conservacao, confidencialidade, padroes abertos)
- MP 2.200-2/2001 Art. 10 (validade juridica de documentos eletronicos)
- Lei 11.419/2006 Art. 1 §2 (assinatura digital ICP-Brasil ou cadastro previo)
"""

from juizo.signing.convergence import (
    ConvergenceSignature,
    ConvergenceScore,
    SignalType,
    SignalWeight,
)
from juizo.signing.signals import (
    BiometrySignal,
    DeviceSignal,
    ContextSignal,
    TemporalSignal,
)
from juizo.signing.gateway import SigningGateway
from juizo.signing.verifier import SignatureVerifier

__all__ = [
    "ConvergenceSignature",
    "ConvergenceScore",
    "SignalType",
    "SignalWeight",
    "BiometrySignal",
    "DeviceSignal",
    "ContextSignal",
    "TemporalSignal",
    "SigningGateway",
    "SignatureVerifier",
]
