"""
Testes dos modelos do CEJUSC pré-processual.

Testa:
- ReclamacaoCejuscPre: validação completa de campos (art. 9º)
- ReclamanteCejusc / ReclamadoCejusc
- SessaoCejusc: prazos e resultados
- AcordoCejusc: condições, MP, homologação
"""

from __future__ import annotations

from datetime import datetime, timedelta, UTC
from decimal import Decimal
from uuid import uuid4

import pytest

from juizo.models.partes import Advogado, Endereco, Parte, TipoPessoa, UF
from juizo.models.pedidos import Pedido

from models.partes import ReclamanteCejusc, ReclamadoCejusc
from models.reclamacao import Modalidade, OpcaoCustas, ReclamacaoCejuscPre
from models.sessao import AtaSessao, ResultadoSessao, SessaoCejusc
from models.acordo import AcordoCejusc, CondicaoAcordo, ParecerMP, StatusAcordo


# ══════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def endereco() -> Endereco:
    return Endereco(
        logradouro="Rua XV de Novembro",
        numero="100",
        bairro="Centro",
        cidade="Curitiba",
        uf=UF.PR,
        cep="80020310",
    )


@pytest.fixture
def reclamante(endereco: Endereco) -> ReclamanteCejusc:
    return ReclamanteCejusc(
        parte=Parte(
            nome="João da Silva",
            tipo_pessoa=TipoPessoa.FISICA,
            cpf="52998224725",
            email="joao@email.com",
            telefone="41999998888",
            endereco=endereco,
        ),
    )


@pytest.fixture
def reclamado(endereco: Endereco) -> ReclamadoCejusc:
    return ReclamadoCejusc(
        parte=Parte(
            nome="Empresa XYZ Ltda",
            tipo_pessoa=TipoPessoa.JURIDICA,
            cnpj="11222333000181",
            email="contato@xyz.com",
            telefone="4133334444",
            endereco=endereco,
        ),
    )


@pytest.fixture
def reclamacao(
    reclamante: ReclamanteCejusc,
    reclamado: ReclamadoCejusc,
) -> ReclamacaoCejuscPre:
    return ReclamacaoCejuscPre(
        cejusc_destino="CEJUSC-CENTRAL-CURITIBA",
        reclamante=reclamante,
        reclamado=reclamado,
        fatos="O reclamado cobrou valores indevidos na fatura de janeiro de 2026.",
        pedidos=[
            Pedido(descricao="Devolução de valores pagos indevidamente", valor=Decimal("1500.00")),
        ],
        valor_causa=Decimal("1500.00"),
        modalidade=Modalidade.CONCILIACAO,
        opcao_custas=OpcaoCustas.TAXA_PAGA,
    )


# ══════════════════════════════════════════════════════════════════════════
# ReclamacaoCejuscPre
# ══════════════════════════════════════════════════════════════════════════

class TestReclamacao:
    """Testes do modelo principal de reclamação — art. 9º."""

    def test_reclamacao_valida(self, reclamacao: ReclamacaoCejuscPre) -> None:
        assert reclamacao.cejusc_destino == "CEJUSC-CENTRAL-CURITIBA"
        assert reclamacao.modalidade == Modalidade.CONCILIACAO
        resultado = reclamacao.validar()
        assert resultado.ok is True

    def test_reclamacao_valor_causa_inferior_soma_pedidos(
        self,
        reclamante: ReclamanteCejusc,
        reclamado: ReclamadoCejusc,
    ) -> None:
        """Valor da causa não pode ser inferior à soma dos pedidos."""
        with pytest.raises(ValueError, match="inferior"):
            ReclamacaoCejuscPre(
                cejusc_destino="CEJUSC-CENTRAL",
                reclamante=reclamante,
                reclamado=reclamado,
                fatos="Teste de validação de valor da causa.",
                pedidos=[
                    Pedido(descricao="Pedido 1", valor=Decimal("1000.00")),
                    Pedido(descricao="Pedido 2", valor=Decimal("500.00")),
                ],
                valor_causa=Decimal("1200.00"),  # < 1500
                modalidade=Modalidade.CONCILIACAO,
                opcao_custas=OpcaoCustas.TAXA_PAGA,
            )

    def test_reclamacao_valor_causa_zero_erro(
        self,
        reclamante: ReclamanteCejusc,
        reclamado: ReclamadoCejusc,
    ) -> None:
        with pytest.raises(Exception):
            ReclamacaoCejuscPre(
                cejusc_destino="CEJUSC-CENTRAL",
                reclamante=reclamante,
                reclamado=reclamado,
                fatos="Teste de validação de valor da causa.",
                pedidos=[Pedido(descricao="Pedido teste", valor=Decimal("100.00"))],
                valor_causa=Decimal("0"),  # deve ser > 0
                modalidade=Modalidade.CONCILIACAO,
                opcao_custas=OpcaoCustas.TAXA_PAGA,
            )

    def test_reclamacao_sem_pedidos_erro(
        self,
        reclamante: ReclamanteCejusc,
        reclamado: ReclamadoCejusc,
    ) -> None:
        with pytest.raises(Exception):
            ReclamacaoCejuscPre(
                cejusc_destino="CEJUSC-CENTRAL",
                reclamante=reclamante,
                reclamado=reclamado,
                fatos="Teste sem pedidos.",
                pedidos=[],  # min_length=1
                valor_causa=Decimal("1000.00"),
                modalidade=Modalidade.MEDIACAO,
                opcao_custas=OpcaoCustas.PEDIDO_GRATUIDADE,
            )

    def test_reclamacao_fatos_curtos_erro(
        self,
        reclamante: ReclamanteCejusc,
        reclamado: ReclamadoCejusc,
    ) -> None:
        with pytest.raises(Exception):
            ReclamacaoCejuscPre(
                cejusc_destino="CEJUSC-CENTRAL",
                reclamante=reclamante,
                reclamado=reclamado,
                fatos="Curto",  # min_length=10
                pedidos=[Pedido(descricao="Pedido teste", valor=Decimal("100.00"))],
                valor_causa=Decimal("100.00"),
                modalidade=Modalidade.CONCILIACAO,
                opcao_custas=OpcaoCustas.TAXA_PAGA,
            )

    def test_reclamacao_com_advogado(
        self,
        reclamante: ReclamanteCejusc,
        reclamado: ReclamadoCejusc,
    ) -> None:
        reclamante_adv = ReclamanteCejusc(
            parte=reclamante.parte,
            advogado=Advogado(
                nome="Dra. Maria Santos",
                oab_numero="12345",
                oab_uf=UF.PR,
                email="maria@oab.com",
                telefone="41999997777",
            ),
        )
        rec = ReclamacaoCejuscPre(
            cejusc_destino="CEJUSC-CENTRAL",
            reclamante=reclamante_adv,
            reclamado=reclamado,
            fatos="O reclamado entregou produto com defeito grave.",
            pedidos=[Pedido(descricao="Troca do produto", valor=Decimal("500.00"))],
            valor_causa=Decimal("500.00"),
            modalidade=Modalidade.CONCILIACAO,
            opcao_custas=OpcaoCustas.TAXA_PAGA,
        )
        assert rec.reclamante.advogado is not None
        assert rec.reclamante.advogado.oab_numero == "12345"

    def test_modalidade_mediacao(self, reclamacao: ReclamacaoCejuscPre) -> None:
        assert Modalidade.MEDIACAO.value == "MEDIACAO"

    def test_opcao_custas_gratuidade(self) -> None:
        assert OpcaoCustas.PEDIDO_GRATUIDADE.value == "PEDIDO_GRATUIDADE"


# ══════════════════════════════════════════════════════════════════════════
# SessaoCejusc
# ══════════════════════════════════════════════════════════════════════════

class TestSessao:
    """Testes do modelo de sessão — art. 11–14."""

    def test_sessao_valida(self) -> None:
        sessao = SessaoCejusc(
            reclamacao_id=uuid4(),
            numero_sessao=1,
            conciliador_id=uuid4(),
            conciliador_nome="Carlos Conciliador",
            data_agendada=datetime(2026, 4, 1, 14, 0, tzinfo=UTC),
        )
        assert sessao.numero_sessao == 1
        assert sessao.resultado is None

    def test_prazo_agendamento_dentro(self) -> None:
        """art. 14 — dentro dos 30 dias."""
        data_cadastro = datetime(2026, 3, 1, tzinfo=UTC)
        sessao = SessaoCejusc(
            reclamacao_id=uuid4(),
            numero_sessao=1,
            conciliador_id=uuid4(),
            conciliador_nome="Carlos",
            data_agendada=datetime(2026, 3, 25, tzinfo=UTC),
        )
        assert sessao.verificar_prazo_agendamento(data_cadastro) is True

    def test_prazo_agendamento_expirado(self) -> None:
        """art. 14 — fora dos 30 dias."""
        data_cadastro = datetime(2026, 3, 1, tzinfo=UTC)
        sessao = SessaoCejusc(
            reclamacao_id=uuid4(),
            numero_sessao=1,
            conciliador_id=uuid4(),
            conciliador_nome="Carlos",
            data_agendada=datetime(2026, 4, 5, tzinfo=UTC),  # 35 dias
        )
        assert sessao.verificar_prazo_agendamento(data_cadastro) is False

    def test_prazo_continuacao_dentro(self) -> None:
        """art. 14 — continuação dentro dos 60 dias."""
        data_primeira = datetime(2026, 3, 1, tzinfo=UTC)
        sessao = SessaoCejusc(
            reclamacao_id=uuid4(),
            numero_sessao=3,
            conciliador_id=uuid4(),
            conciliador_nome="Carlos",
            data_agendada=datetime(2026, 4, 20, tzinfo=UTC),  # 50 dias
        )
        assert sessao.verificar_prazo_continuacao(data_primeira) is True

    def test_prazo_continuacao_expirado(self) -> None:
        """art. 14 — continuação fora dos 60 dias."""
        data_primeira = datetime(2026, 3, 1, tzinfo=UTC)
        sessao = SessaoCejusc(
            reclamacao_id=uuid4(),
            numero_sessao=3,
            conciliador_id=uuid4(),
            conciliador_nome="Carlos",
            data_agendada=datetime(2026, 5, 10, tzinfo=UTC),  # 70 dias
        )
        assert sessao.verificar_prazo_continuacao(data_primeira) is False

    def test_primeira_sessao_sempre_dentro_continuacao(self) -> None:
        """Primeira sessão não verifica prazo de continuação."""
        sessao = SessaoCejusc(
            reclamacao_id=uuid4(),
            numero_sessao=1,
            conciliador_id=uuid4(),
            conciliador_nome="Carlos",
            data_agendada=datetime(2026, 12, 31, tzinfo=UTC),
        )
        assert sessao.verificar_prazo_continuacao(datetime(2026, 1, 1, tzinfo=UTC)) is True

    def test_is_ausencia(self) -> None:
        sessao = SessaoCejusc(
            reclamacao_id=uuid4(),
            numero_sessao=1,
            conciliador_id=uuid4(),
            conciliador_nome="Carlos",
            data_agendada=datetime(2026, 4, 1, tzinfo=UTC),
            resultado=ResultadoSessao.AUSENCIA_RECLAMANTE,
        )
        assert sessao.is_ausencia is True

    def test_is_ausencia_false(self) -> None:
        sessao = SessaoCejusc(
            reclamacao_id=uuid4(),
            numero_sessao=1,
            conciliador_id=uuid4(),
            conciliador_nome="Carlos",
            data_agendada=datetime(2026, 4, 1, tzinfo=UTC),
            resultado=ResultadoSessao.ACORDO,
        )
        assert sessao.is_ausencia is False

    def test_is_ausencia_sem_resultado(self) -> None:
        sessao = SessaoCejusc(
            reclamacao_id=uuid4(),
            numero_sessao=1,
            conciliador_id=uuid4(),
            conciliador_nome="Carlos",
            data_agendada=datetime(2026, 4, 1, tzinfo=UTC),
        )
        assert sessao.is_ausencia is False


# ══════════════════════════════════════════════════════════════════════════
# AtaSessao
# ══════════════════════════════════════════════════════════════════════════

class TestAtaSessao:
    """Testes da ata de sessão — art. 13."""

    def test_ata_valida(self) -> None:
        ata = AtaSessao(
            sessao_id=uuid4(),
            conteudo="As partes compareceram e tentaram acordo sem sucesso.",
            reclamante_presente=True,
            reclamado_presente=True,
            resultado=ResultadoSessao.SEM_ACORDO,
            lavrada_por_id=uuid4(),
            lavrada_por_nome="Carlos Conciliador",
        )
        assert ata.resultado == ResultadoSessao.SEM_ACORDO

    def test_ata_ausencia(self) -> None:
        ata = AtaSessao(
            sessao_id=uuid4(),
            conteudo="O reclamado não compareceu à sessão designada.",
            reclamante_presente=True,
            reclamado_presente=False,
            resultado=ResultadoSessao.AUSENCIA_RECLAMADO,
            lavrada_por_id=uuid4(),
            lavrada_por_nome="Carlos Conciliador",
        )
        assert ata.reclamado_presente is False


# ══════════════════════════════════════════════════════════════════════════
# AcordoCejusc
# ══════════════════════════════════════════════════════════════════════════

class TestAcordo:
    """Testes do modelo de acordo — art. 13 §3º / art. 15–16."""

    def test_acordo_simples(self) -> None:
        acordo = AcordoCejusc(
            reclamacao_id=uuid4(),
            sessao_id=uuid4(),
            condicoes=[
                CondicaoAcordo(
                    descricao="Devolver R$ 1.500,00 em 3 parcelas",
                    parte_responsavel="Empresa XYZ Ltda",
                    valor=Decimal("1500.00"),
                    forma_pagamento="PIX mensal",
                ),
            ],
        )
        assert acordo.status == StatusAcordo.REDIGIDO
        assert acordo.valor_total == Decimal("1500.00")

    def test_acordo_com_multiplas_condicoes(self) -> None:
        acordo = AcordoCejusc(
            reclamacao_id=uuid4(),
            sessao_id=uuid4(),
            condicoes=[
                CondicaoAcordo(
                    descricao="Devolução de valores",
                    parte_responsavel="Empresa",
                    valor=Decimal("1000.00"),
                ),
                CondicaoAcordo(
                    descricao="Carta de desculpas",
                    parte_responsavel="Empresa",
                ),
            ],
        )
        assert acordo.valor_total == Decimal("1000.00")

    def test_acordo_sem_condicoes_erro(self) -> None:
        with pytest.raises(Exception):
            AcordoCejusc(
                reclamacao_id=uuid4(),
                sessao_id=uuid4(),
                condicoes=[],  # min_length=1
            )

    def test_requer_mp_menores(self) -> None:
        """art. 15 §ú — menores/incapazes requer MP."""
        acordo = AcordoCejusc(
            reclamacao_id=uuid4(),
            sessao_id=uuid4(),
            condicoes=[
                CondicaoAcordo(
                    descricao="Pensão alimentícia",
                    parte_responsavel="Genitor",
                    valor=Decimal("2000.00"),
                ),
            ],
            envolve_menores_incapazes=True,
        )
        assert acordo.requer_mp() is True

    def test_nao_requer_mp_adultos(self) -> None:
        acordo = AcordoCejusc(
            reclamacao_id=uuid4(),
            sessao_id=uuid4(),
            condicoes=[
                CondicaoAcordo(
                    descricao="Devolução",
                    parte_responsavel="Empresa",
                    valor=Decimal("500.00"),
                ),
            ],
        )
        assert acordo.requer_mp() is False

    def test_pode_homologar_sem_menores(self) -> None:
        acordo = AcordoCejusc(
            reclamacao_id=uuid4(),
            sessao_id=uuid4(),
            condicoes=[
                CondicaoAcordo(
                    descricao="Devolução",
                    parte_responsavel="Empresa",
                    valor=Decimal("500.00"),
                ),
            ],
        )
        assert acordo.pode_homologar() is True

    def test_nao_pode_homologar_sem_parecer_mp(self) -> None:
        """art. 15 §ú — não pode homologar sem parecer do MP."""
        acordo = AcordoCejusc(
            reclamacao_id=uuid4(),
            sessao_id=uuid4(),
            condicoes=[
                CondicaoAcordo(
                    descricao="Pensão",
                    parte_responsavel="Genitor",
                    valor=Decimal("2000.00"),
                ),
            ],
            envolve_menores_incapazes=True,
        )
        assert acordo.pode_homologar() is False

    def test_pode_homologar_com_parecer_favoravel(self) -> None:
        acordo = AcordoCejusc(
            reclamacao_id=uuid4(),
            sessao_id=uuid4(),
            condicoes=[
                CondicaoAcordo(
                    descricao="Pensão",
                    parte_responsavel="Genitor",
                    valor=Decimal("2000.00"),
                ),
            ],
            envolve_menores_incapazes=True,
            parecer_mp=ParecerMP(
                acordo_id=uuid4(),
                promotor_id=uuid4(),
                promotor_nome="Dr. Promotor",
                favoravel=True,
                fundamentacao="Acordo atende aos interesses do menor.",
            ),
        )
        assert acordo.pode_homologar() is True

    def test_nao_pode_homologar_parecer_desfavoravel(self) -> None:
        acordo = AcordoCejusc(
            reclamacao_id=uuid4(),
            sessao_id=uuid4(),
            condicoes=[
                CondicaoAcordo(
                    descricao="Pensão insuficiente",
                    parte_responsavel="Genitor",
                    valor=Decimal("100.00"),
                ),
            ],
            envolve_menores_incapazes=True,
            parecer_mp=ParecerMP(
                acordo_id=uuid4(),
                promotor_id=uuid4(),
                promotor_nome="Dr. Promotor",
                favoravel=False,
                fundamentacao="Valor insuficiente para as necessidades do menor.",
            ),
        )
        assert acordo.pode_homologar() is False

    def test_condicao_valor_negativo_erro(self) -> None:
        with pytest.raises(Exception):
            CondicaoAcordo(
                descricao="Condição inválida",
                parte_responsavel="Parte",
                valor=Decimal("-100.00"),
            )
