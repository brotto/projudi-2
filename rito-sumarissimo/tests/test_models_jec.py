"""
Testes dos modelos dos Juizados Especiais Civeis.

Testa:
- PeticaoInicialJEC: validacao completa de campos (art. 14)
- AutorJEC: restricao a pessoa fisica (art. 8o §1o)
- Valor da causa: maximo 40 SM (art. 3o I)
- Advogado: obrigatorio acima de 20 SM (art. 9o)
- AudienciaJEC: tipos e resultados
- SentencaJEC: tipos de decisao
- RecursoInominado: recurso para Turma Recursal
"""

from __future__ import annotations

from datetime import datetime, UTC
from decimal import Decimal
from uuid import uuid4

import pytest

from juizo.models.partes import Advogado, Endereco, Parte, TipoPessoa, UF
from juizo.models.pedidos import Pedido

from models.peticao import AutorJEC, PeticaoInicialJEC, ReuJEC
from models.audiencia import (
    AtaAudienciaJEC,
    AudienciaJEC,
    ResultadoAudiencia,
    TipoAudiencia,
)
from models.sentenca import (
    RecursoInominado,
    ResultadoRecurso,
    SentencaJEC,
    TipoSentenca,
)
from fsm.estados import LIMITE_SEM_ADVOGADO, VALOR_MAXIMO_CAUSA


# ======================================================================
# Fixtures
# ======================================================================

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
def autor(endereco: Endereco) -> AutorJEC:
    return AutorJEC(
        parte=Parte(
            nome="Joao da Silva",
            tipo_pessoa=TipoPessoa.FISICA,
            cpf="52998224725",
            email="joao@email.com",
            telefone="41999998888",
            endereco=endereco,
        ),
    )


@pytest.fixture
def autor_com_advogado(endereco: Endereco) -> AutorJEC:
    return AutorJEC(
        parte=Parte(
            nome="Joao da Silva",
            tipo_pessoa=TipoPessoa.FISICA,
            cpf="52998224725",
            email="joao@email.com",
            telefone="41999998888",
            endereco=endereco,
        ),
        advogado=Advogado(
            nome="Dra. Maria Santos",
            oab_numero="12345",
            oab_uf=UF.PR,
            email="maria@oab.com",
            telefone="41999997777",
        ),
    )


@pytest.fixture
def reu(endereco: Endereco) -> ReuJEC:
    return ReuJEC(
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
def peticao(autor: AutorJEC, reu: ReuJEC) -> PeticaoInicialJEC:
    return PeticaoInicialJEC(
        juizado_destino="JEC-CENTRAL-CURITIBA",
        autor=autor,
        reu=reu,
        fatos="O reu cobrou valores indevidos na fatura de janeiro de 2026.",
        pedidos=[
            Pedido(descricao="Devolucao de valores pagos indevidamente", valor=Decimal("1500.00")),
        ],
        valor_causa=Decimal("1500.00"),
    )


# ======================================================================
# PeticaoInicialJEC
# ======================================================================

class TestPeticao:
    """Testes do modelo de peticao inicial — art. 14."""

    def test_peticao_valida(self, peticao: PeticaoInicialJEC) -> None:
        assert peticao.juizado_destino == "JEC-CENTRAL-CURITIBA"
        resultado = peticao.validar()
        assert resultado.ok is True

    def test_peticao_pessoa_juridica_como_autor_rejeita(
        self,
        endereco: Endereco,
    ) -> None:
        """art. 8o §1o — autor deve ser pessoa fisica."""
        with pytest.raises(ValueError, match="pessoa fisica"):
            AutorJEC(
                parte=Parte(
                    nome="Empresa ABC Ltda",
                    tipo_pessoa=TipoPessoa.JURIDICA,
                    cnpj="11222333000181",
                    email="contato@abc.com",
                    telefone="4133334444",
                    endereco=endereco,
                ),
            )

    def test_valor_acima_40_sm_rejeita(
        self, autor: AutorJEC, reu: ReuJEC,
    ) -> None:
        """art. 3o I — valor maximo 40 SM."""
        valor_excedente = VALOR_MAXIMO_CAUSA + Decimal("0.01")
        with pytest.raises(ValueError, match="40 salarios minimos"):
            PeticaoInicialJEC(
                juizado_destino="JEC-CENTRAL",
                autor=autor,
                reu=reu,
                fatos="Teste de validacao de valor da causa acima do teto.",
                pedidos=[
                    Pedido(descricao="Pedido alto", valor=valor_excedente),
                ],
                valor_causa=valor_excedente,
            )

    def test_valor_exato_40_sm_aceita(
        self, autor_com_advogado: AutorJEC, reu: ReuJEC,
    ) -> None:
        """art. 3o I — no limite exato de 40 SM deve aceitar (com advogado)."""
        peticao = PeticaoInicialJEC(
            juizado_destino="JEC-CENTRAL",
            autor=autor_com_advogado,  # advogado obrigatorio acima de 20 SM
            reu=reu,
            fatos="Teste com valor no limite dos 40 salarios minimos.",
            pedidos=[
                Pedido(descricao="Pedido no limite", valor=VALOR_MAXIMO_CAUSA),
            ],
            valor_causa=VALOR_MAXIMO_CAUSA,
        )
        assert peticao.valor_causa == VALOR_MAXIMO_CAUSA

    def test_valor_causa_inferior_soma_pedidos(
        self, autor: AutorJEC, reu: ReuJEC,
    ) -> None:
        """Valor da causa nao pode ser inferior a soma dos pedidos."""
        with pytest.raises(ValueError, match="inferior"):
            PeticaoInicialJEC(
                juizado_destino="JEC-CENTRAL",
                autor=autor,
                reu=reu,
                fatos="Teste de validacao de valor da causa.",
                pedidos=[
                    Pedido(descricao="Pedido 1", valor=Decimal("1000.00")),
                    Pedido(descricao="Pedido 2", valor=Decimal("500.00")),
                ],
                valor_causa=Decimal("1200.00"),  # < 1500
            )

    def test_advogado_obrigatorio_acima_20_sm(
        self, autor: AutorJEC, reu: ReuJEC,
    ) -> None:
        """art. 9o — advogado obrigatorio acima de 20 SM."""
        valor_acima_20sm = LIMITE_SEM_ADVOGADO + Decimal("0.01")
        with pytest.raises(ValueError, match="Advogado obrigatorio"):
            PeticaoInicialJEC(
                juizado_destino="JEC-CENTRAL",
                autor=autor,  # sem advogado
                reu=reu,
                fatos="Teste com valor acima de 20 SM sem advogado.",
                pedidos=[
                    Pedido(descricao="Pedido", valor=valor_acima_20sm),
                ],
                valor_causa=valor_acima_20sm,
            )

    def test_advogado_facultativo_ate_20_sm(
        self, autor: AutorJEC, reu: ReuJEC,
    ) -> None:
        """art. 9o — sem advogado ate 20 SM aceita."""
        peticao = PeticaoInicialJEC(
            juizado_destino="JEC-CENTRAL",
            autor=autor,  # sem advogado
            reu=reu,
            fatos="Teste com valor ate 20 SM sem advogado.",
            pedidos=[
                Pedido(descricao="Pedido simples", valor=Decimal("1000.00")),
            ],
            valor_causa=Decimal("1000.00"),
        )
        assert peticao.autor.advogado is None

    def test_com_advogado_acima_20_sm_aceita(
        self, autor_com_advogado: AutorJEC, reu: ReuJEC,
    ) -> None:
        """art. 9o — com advogado acima de 20 SM aceita."""
        valor_acima = LIMITE_SEM_ADVOGADO + Decimal("1000.00")
        peticao = PeticaoInicialJEC(
            juizado_destino="JEC-CENTRAL",
            autor=autor_com_advogado,
            reu=reu,
            fatos="Teste com advogado e valor acima de 20 SM.",
            pedidos=[
                Pedido(descricao="Pedido", valor=valor_acima),
            ],
            valor_causa=valor_acima,
        )
        assert peticao.autor.advogado is not None

    def test_valor_causa_zero_erro(
        self, autor: AutorJEC, reu: ReuJEC,
    ) -> None:
        with pytest.raises(Exception):
            PeticaoInicialJEC(
                juizado_destino="JEC-CENTRAL",
                autor=autor,
                reu=reu,
                fatos="Teste de validacao de valor da causa.",
                pedidos=[Pedido(descricao="Pedido teste", valor=Decimal("100.00"))],
                valor_causa=Decimal("0"),
            )

    def test_sem_pedidos_erro(
        self, autor: AutorJEC, reu: ReuJEC,
    ) -> None:
        with pytest.raises(Exception):
            PeticaoInicialJEC(
                juizado_destino="JEC-CENTRAL",
                autor=autor,
                reu=reu,
                fatos="Teste sem pedidos.",
                pedidos=[],
                valor_causa=Decimal("1000.00"),
            )

    def test_fatos_curtos_erro(
        self, autor: AutorJEC, reu: ReuJEC,
    ) -> None:
        with pytest.raises(Exception):
            PeticaoInicialJEC(
                juizado_destino="JEC-CENTRAL",
                autor=autor,
                reu=reu,
                fatos="Curto",
                pedidos=[Pedido(descricao="Pedido teste", valor=Decimal("100.00"))],
                valor_causa=Decimal("100.00"),
            )


# ======================================================================
# AudienciaJEC
# ======================================================================

class TestAudiencia:
    """Testes do modelo de audiencia — art. 21-29."""

    def test_audiencia_conciliacao_valida(self) -> None:
        audiencia = AudienciaJEC(
            processo_id=uuid4(),
            tipo=TipoAudiencia.CONCILIACAO,
            condutor_id=uuid4(),
            condutor_nome="Carlos Conciliador",
            data_designada=datetime(2026, 4, 1, 14, 0, tzinfo=UTC),
        )
        assert audiencia.is_conciliacao is True
        assert audiencia.is_instrucao is False
        assert audiencia.resultado is None

    def test_audiencia_instrucao_valida(self) -> None:
        audiencia = AudienciaJEC(
            processo_id=uuid4(),
            tipo=TipoAudiencia.INSTRUCAO,
            condutor_id=uuid4(),
            condutor_nome="Dr. Juiz",
            data_designada=datetime(2026, 4, 15, 9, 0, tzinfo=UTC),
        )
        assert audiencia.is_instrucao is True
        assert audiencia.is_conciliacao is False

    def test_audiencia_ausencia(self) -> None:
        audiencia = AudienciaJEC(
            processo_id=uuid4(),
            tipo=TipoAudiencia.CONCILIACAO,
            condutor_id=uuid4(),
            condutor_nome="Carlos Conciliador",
            data_designada=datetime(2026, 4, 1, 14, 0, tzinfo=UTC),
            resultado=ResultadoAudiencia.AUSENCIA_REU,
        )
        assert audiencia.is_ausencia is True

    def test_audiencia_acordo_nao_e_ausencia(self) -> None:
        audiencia = AudienciaJEC(
            processo_id=uuid4(),
            tipo=TipoAudiencia.CONCILIACAO,
            condutor_id=uuid4(),
            condutor_nome="Carlos Conciliador",
            data_designada=datetime(2026, 4, 1, 14, 0, tzinfo=UTC),
            resultado=ResultadoAudiencia.ACORDO,
        )
        assert audiencia.is_ausencia is False


# ======================================================================
# SentencaJEC
# ======================================================================

class TestSentenca:
    """Testes do modelo de sentenca — art. 38-40."""

    def test_sentenca_procedente(self) -> None:
        sentenca = SentencaJEC(
            processo_id=uuid4(),
            tipo=TipoSentenca.PROCEDENTE,
            fundamentacao="O autor demonstrou o direito alegado com documentos idoneos.",
            dispositivo="Julgo procedente o pedido para condenar o reu ao pagamento de R$ 1.500,00.",
            juiz_id=uuid4(),
            juiz_nome="Dr. Magistrado",
            valor_condenacao=Decimal("1500.00"),
        )
        assert sentenca.is_merito is True
        assert sentenca.is_condenatoria is True
        assert sentenca.recorrivel is True

    def test_sentenca_improcedente(self) -> None:
        sentenca = SentencaJEC(
            processo_id=uuid4(),
            tipo=TipoSentenca.IMPROCEDENTE,
            fundamentacao="O autor nao logrou exito em comprovar suas alegacoes.",
            dispositivo="Julgo improcedente o pedido.",
            juiz_id=uuid4(),
            juiz_nome="Dr. Magistrado",
        )
        assert sentenca.is_merito is True
        assert sentenca.is_condenatoria is False

    def test_sentenca_parcialmente_procedente(self) -> None:
        sentenca = SentencaJEC(
            processo_id=uuid4(),
            tipo=TipoSentenca.PARCIALMENTE_PROCEDENTE,
            fundamentacao="O autor comprovou parcialmente o pedido.",
            dispositivo="Julgo parcialmente procedente para condenar em R$ 750,00.",
            juiz_id=uuid4(),
            juiz_nome="Dr. Magistrado",
            valor_condenacao=Decimal("750.00"),
        )
        assert sentenca.is_merito is True
        assert sentenca.is_condenatoria is True

    def test_sentenca_extincao(self) -> None:
        sentenca = SentencaJEC(
            processo_id=uuid4(),
            tipo=TipoSentenca.EXTINCAO,
            fundamentacao="O autor deixou de comparecer a audiencia designada.",
            dispositivo="Julgo extinto o processo sem resolucao de merito.",
            juiz_id=uuid4(),
            juiz_nome="Dr. Magistrado",
        )
        assert sentenca.is_merito is False
        assert sentenca.is_condenatoria is False

    def test_sentenca_valor_condenacao_negativo_erro(self) -> None:
        with pytest.raises(Exception):
            SentencaJEC(
                processo_id=uuid4(),
                tipo=TipoSentenca.PROCEDENTE,
                fundamentacao="Fundamentacao da sentenca.",
                dispositivo="Dispositivo da sentenca.",
                juiz_id=uuid4(),
                juiz_nome="Dr. Magistrado",
                valor_condenacao=Decimal("-100.00"),
            )


# ======================================================================
# RecursoInominado
# ======================================================================

class TestRecurso:
    """Testes do modelo de recurso inominado — art. 41-46."""

    def test_recurso_valido(self) -> None:
        recurso = RecursoInominado(
            processo_id=uuid4(),
            sentenca_id=uuid4(),
            recorrente_id=uuid4(),
            recorrente_nome="Joao da Silva",
            razoes="A sentenca merece reforma pois os fatos foram interpretados erroneamente.",
        )
        assert recurso.is_julgado is False
        assert recurso.resultado is None

    def test_recurso_julgado(self) -> None:
        recurso = RecursoInominado(
            processo_id=uuid4(),
            sentenca_id=uuid4(),
            recorrente_id=uuid4(),
            recorrente_nome="Joao da Silva",
            razoes="Razoes do recurso.",
            resultado=ResultadoRecurso.IMPROVIDO,
            relator_id=uuid4(),
            relator_nome="Dr. Relator",
            julgado_em=datetime(2026, 5, 15, tzinfo=UTC),
        )
        assert recurso.is_julgado is True
        assert recurso.resultado == ResultadoRecurso.IMPROVIDO

    def test_tipos_resultado_recurso(self) -> None:
        """art. 46 — possiveis resultados do recurso."""
        assert ResultadoRecurso.PROVIDO.value == "PROVIDO"
        assert ResultadoRecurso.PARCIALMENTE_PROVIDO.value == "PARCIALMENTE_PROVIDO"
        assert ResultadoRecurso.IMPROVIDO.value == "IMPROVIDO"
        assert ResultadoRecurso.NAO_CONHECIDO.value == "NAO_CONHECIDO"
