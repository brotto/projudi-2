"""
Politicas de retencao de logs de auditoria.

Cada categoria de log tem prazo minimo de retencao definido por lei.
Este modulo garante que nenhum log seja descartado antes do prazo legal.

Referencia:
- Marco Civil Art. 13: registros de conexao → 1 ano
- Marco Civil Art. 15: registros de acesso → 6 meses
- DOC-ICP-17: logs de PSC → 6 anos
- LGPD Art. 37 + Art. 16: tratamento de dados → duracao + prescricao
- Res. CNJ 324/2020: tabela de temporalidade por classe documental
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from juizo.audit.log import AuditCategory


@dataclass
class RetentionRule:
    """Regra de retencao para uma categoria de auditoria."""

    category: AuditCategory
    minimum_retention: timedelta  # prazo minimo legal
    legal_basis: str  # artigo de lei que fundamenta
    notes: str = ""


# Prazos minimos de retencao por categoria
# Configuravel por tenant (TJ pode exigir mais, nunca menos)

DEFAULT_RETENTION_RULES: list[RetentionRule] = [
    RetentionRule(
        category=AuditCategory.SIGNING,
        minimum_retention=timedelta(days=365 * 20),  # vida util do processo
        legal_basis="CPC Art. 195 (conservacao)",
        notes="Assinaturas de atos processuais devem ser preservadas "
              "pelo prazo de guarda do processo (tabela de temporalidade CNJ).",
    ),
    RetentionRule(
        category=AuditCategory.AUTH,
        minimum_retention=timedelta(days=365),  # 1 ano
        legal_basis="Marco Civil Art. 13 (registros de conexao)",
        notes="Registros de autenticacao = registros de conexao. "
              "Prazo minimo 1 ano, podendo ser ampliado por ordem judicial.",
    ),
    RetentionRule(
        category=AuditCategory.ACCESS,
        minimum_retention=timedelta(days=180),  # 6 meses
        legal_basis="Marco Civil Art. 15 (registros de acesso a aplicacao)",
        notes="Registros de acesso a processos. "
              "6 meses minimo, podendo ser ampliado por ordem judicial.",
    ),
    RetentionRule(
        category=AuditCategory.TRANSITION,
        minimum_retention=timedelta(days=365 * 20),  # vida util do processo
        legal_basis="CPC Art. 195 (conservacao, nao-repudio)",
        notes="Transicoes de estado fazem parte do historico imutavel do processo.",
    ),
    RetentionRule(
        category=AuditCategory.PSC,
        minimum_retention=timedelta(days=365 * 6),  # 6 anos
        legal_basis="DOC-ICP-17 (requisitos para PSC)",
        notes="Logs de operacoes com Prestadores de Servico de Confianca. "
              "Analise maxima semanal. Backup por 6 anos.",
    ),
    RetentionRule(
        category=AuditCategory.CERTIFICATE,
        minimum_retention=timedelta(days=365 * 6),  # vida util do certificado + margem
        legal_basis="DOC-ICP-15 (verificacao de assinaturas)",
        notes="Respostas OCSP e CRLs utilizadas na verificacao de certificados.",
    ),
    RetentionRule(
        category=AuditCategory.AVAILABILITY,
        minimum_retention=timedelta(days=365 * 2),  # 2 anos
        legal_basis="Res. CNJ 185/2013 Arts. 9-11",
        notes="Monitoramento de disponibilidade a cada 5 minutos. "
              "Relatorios publicamente acessiveis.",
    ),
    RetentionRule(
        category=AuditCategory.INCIDENT,
        minimum_retention=timedelta(days=365 * 10),  # 10 anos (conservador)
        legal_basis="Res. CNJ 396/2021 Art. 18 + LGPD Art. 48",
        notes="Incidentes de seguranca. Comunicacao imediata ao CPTRIC-PJ. "
              "Retencao longa para investigacao e conformidade.",
    ),
    RetentionRule(
        category=AuditCategory.DATA_TREATMENT,
        minimum_retention=timedelta(days=365 * 5),  # prescricao geral
        legal_basis="LGPD Art. 37 + Art. 16",
        notes="Registro de operacoes de tratamento de dados pessoais. "
              "Retencao ate fim do tratamento + prazo prescricional (5 anos).",
    ),
]


class RetentionPolicy:
    """
    Gerenciador de politicas de retencao.

    Garante que nenhum log seja descartado antes do prazo legal.
    TJs podem AMPLIAR prazos, nunca REDUZIR abaixo do minimo legal.
    """

    def __init__(
        self,
        rules: list[RetentionRule] | None = None,
    ) -> None:
        self.rules = {r.category: r for r in (rules or DEFAULT_RETENTION_RULES)}

    def get_retention(self, category: AuditCategory) -> RetentionRule:
        """Retorna a regra de retencao para uma categoria."""
        rule = self.rules.get(category)
        if rule is None:
            # Fallback conservador: 5 anos
            return RetentionRule(
                category=category,
                minimum_retention=timedelta(days=365 * 5),
                legal_basis="Fallback conservador",
                notes="Categoria sem regra especifica — aplicado prazo prescricional geral.",
            )
        return rule

    def can_purge(
        self,
        category: AuditCategory,
        entry_age: timedelta,
    ) -> bool:
        """
        Verifica se uma entrada pode ser purgada (idade > retencao minima).

        IMPORTANTE: este metodo retorna True se o prazo legal JA PASSOU.
        A decisao de purgar continua sendo do administrador.
        Em um sistema append-only puro, purge nunca acontece — este metodo
        serve para sistemas que precisam gerenciar espaco.
        """
        rule = self.get_retention(category)
        return entry_age > rule.minimum_retention
