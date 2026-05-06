"""
Modulo de auditoria do sistema Juizo.

Log imutavel de todos os eventos do sistema — assinaturas, acessos,
transicoes, verificacoes, incidentes.

Referencia legal:
- CPC Art. 195 (conservacao, nao-repudio)
- LGPD Art. 37 (registro de operacoes de tratamento)
- Marco Civil Art. 13 (registros de conexao: 1 ano)
- Marco Civil Art. 15 (registros de acesso: 6 meses)
- DOC-ICP-17 (logs PSC: 6 anos, analise semanal)
- Res. CNJ 185/2013 Arts. 9-11 (disponibilidade: 5 min)
- Res. CNJ 396/2021 Art. 18 (comunicacao de incidentes)
"""

from juizo.audit.log import AuditLog, AuditEntry, AuditCategory
from juizo.audit.retention import RetentionPolicy

__all__ = [
    "AuditLog",
    "AuditEntry",
    "AuditCategory",
    "RetentionPolicy",
]
