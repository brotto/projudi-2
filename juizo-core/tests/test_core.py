"""
Testes unitários do juizo-core — FSM engine + modelos base.

Cobertura esperada: 100% da engine FSM e validações de modelos.
"""

from __future__ import annotations

from datetime import datetime, UTC
from decimal import Decimal
from uuid import uuid4

import pytest

from juizo.exceptions import (
    AtorNaoAutorizado,
    CompetenciaExcluida,
    ErroProtocolo,
    ErroValidacao,
    EstadoTerminal,
    PrazoExpirado,
    TransicaoInvalida,
)
from juizo.fsm.base import RitoFSM
from juizo.fsm.engine import EventoTransicao, FSMEngine, ResultadoValidacao
from juizo.models.base import EventoProcessual, TipoAtor
from juizo.models.partes import (
    Advogado,
    Endereco,
    Parte,
    TipoPessoa,
    UF,
    validar_cpf,
    validar_cnpj,
)
from juizo.models.pedidos import Fundamento, Pedido
from juizo.models.processo import Processo, Rito


# ══════════════════════════════════════════════════════════════════════════
# Fixtures — dados de teste reutilizáveis
# ══════════════════════════════════════════════════════════════════════════

# FSM de teste simples (3 estados)
TRANSICOES_TESTE = {
    "INICIO": ["MEIO"],
    "MEIO": ["FIM", "CANCELADO"],
    "FIM": [],
    "CANCELADO": [],
}

TERMINAIS_TESTE = {"FIM", "CANCELADO"}

PERMISSOES_TESTE = {
    "MEIO": ["SECRETARIA"],
    "FIM": ["JUIZ_COORDENADOR"],
    "CANCELADO": ["SECRETARIA", "JUIZ_COORDENADOR"],
}


@pytest.fixture
def engine() -> FSMEngine:
    return FSMEngine(
        transicoes=TRANSICOES_TESTE,
        estados_terminais=TERMINAIS_TESTE,
        permissoes=PERMISSOES_TESTE,
    )


@pytest.fixture
def endereco_valido() -> Endereco:
    return Endereco(
        logradouro="Rua XV de Novembro",
        numero="100",
        bairro="Centro",
        cidade="Curitiba",
        uf=UF.PR,
        cep="80020310",
    )


@pytest.fixture
def parte_fisica(endereco_valido: Endereco) -> Parte:
    return Parte(
        nome="João da Silva",
        tipo_pessoa=TipoPessoa.FISICA,
        cpf="52998224725",  # CPF válido para teste
        email="joao@email.com",
        telefone="41999998888",
        endereco=endereco_valido,
    )


# ══════════════════════════════════════════════════════════════════════════
# FSMEngine — testes do motor de máquina de estados
# ══════════════════════════════════════════════════════════════════════════

class TestFSMEngine:
    """Testes do motor FSM genérico."""

    def test_transicao_valida(self, engine: FSMEngine) -> None:
        evento = engine.transicionar(
            estado_atual="INICIO",
            estado_destino="MEIO",
            ator_id="ator-1",
            ator_tipo="SECRETARIA",
            processo_id="proc-1",
        )
        assert evento.estado_anterior == "INICIO"
        assert evento.estado_novo == "MEIO"
        assert evento.ator_tipo == "SECRETARIA"
        assert evento.hash != ""

    def test_transicao_invalida_levanta_excecao(self, engine: FSMEngine) -> None:
        with pytest.raises(TransicaoInvalida) as exc_info:
            engine.transicionar(
                estado_atual="INICIO",
                estado_destino="FIM",  # não permitido direto
                ator_id="ator-1",
                ator_tipo="JUIZ_COORDENADOR",
                processo_id="proc-1",
            )
        assert exc_info.value.estado_atual == "INICIO"
        assert exc_info.value.transicao_tentada == "FIM"
        assert "MEIO" in exc_info.value.transicoes_validas

    def test_estado_terminal_levanta_excecao(self, engine: FSMEngine) -> None:
        with pytest.raises(EstadoTerminal) as exc_info:
            engine.transicionar(
                estado_atual="FIM",
                estado_destino="INICIO",
                ator_id="ator-1",
                ator_tipo="SECRETARIA",
                processo_id="proc-1",
            )
        assert exc_info.value.estado == "FIM"

    def test_ator_nao_autorizado(self, engine: FSMEngine) -> None:
        with pytest.raises(AtorNaoAutorizado) as exc_info:
            engine.transicionar(
                estado_atual="INICIO",
                estado_destino="MEIO",
                ator_id="ator-1",
                ator_tipo="PARTE",  # parte não pode fazer triagem
                processo_id="proc-1",
            )
        assert exc_info.value.ator_tipo == "PARTE"

    def test_transicoes_validas_retorna_lista(self, engine: FSMEngine) -> None:
        assert engine.transicoes_validas("INICIO") == ["MEIO"]
        assert set(engine.transicoes_validas("MEIO")) == {"FIM", "CANCELADO"}

    def test_transicoes_validas_terminal_vazio(self, engine: FSMEngine) -> None:
        assert engine.transicoes_validas("FIM") == []
        assert engine.transicoes_validas("CANCELADO") == []

    def test_is_terminal(self, engine: FSMEngine) -> None:
        assert engine.is_terminal("FIM") is True
        assert engine.is_terminal("CANCELADO") is True
        assert engine.is_terminal("INICIO") is False
        assert engine.is_terminal("MEIO") is False

    def test_hash_encadeado(self, engine: FSMEngine) -> None:
        evento1 = engine.transicionar(
            estado_atual="INICIO",
            estado_destino="MEIO",
            ator_id="ator-1",
            ator_tipo="SECRETARIA",
            processo_id="proc-1",
            hash_anterior="",
        )
        evento2 = engine.transicionar(
            estado_atual="MEIO",
            estado_destino="FIM",
            ator_id="ator-2",
            ator_tipo="JUIZ_COORDENADOR",
            processo_id="proc-1",
            hash_anterior=evento1.hash,
        )
        assert evento2.hash_anterior == evento1.hash
        assert evento2.hash != evento1.hash
        assert evento2.hash != ""

    def test_payload_preservado(self, engine: FSMEngine) -> None:
        payload = {"motivo": "teste", "dados": [1, 2, 3]}
        evento = engine.transicionar(
            estado_atual="INICIO",
            estado_destino="MEIO",
            ator_id="ator-1",
            ator_tipo="SECRETARIA",
            processo_id="proc-1",
            payload=payload,
        )
        assert evento.payload == payload

    def test_atos_automaticos_executados(self) -> None:
        log_atos: list[str] = []

        def ato_1(processo_id: str, payload: dict) -> None:
            log_atos.append(f"ato_1:{processo_id}")

        def ato_2(processo_id: str, payload: dict) -> None:
            log_atos.append(f"ato_2:{processo_id}")

        engine = FSMEngine(
            transicoes=TRANSICOES_TESTE,
            estados_terminais=TERMINAIS_TESTE,
            atos_automaticos={("INICIO", "MEIO"): [ato_1, ato_2]},
        )
        engine.transicionar(
            estado_atual="INICIO",
            estado_destino="MEIO",
            ator_id="ator-1",
            ator_tipo="SECRETARIA",
            processo_id="proc-1",
        )
        assert log_atos == ["ato_1:proc-1", "ato_2:proc-1"]

    def test_engine_sem_permissoes_permite_qualquer_ator(self) -> None:
        engine = FSMEngine(
            transicoes=TRANSICOES_TESTE,
            estados_terminais=TERMINAIS_TESTE,
        )
        # Deve funcionar sem permissões definidas
        evento = engine.transicionar(
            estado_atual="INICIO",
            estado_destino="MEIO",
            ator_id="ator-1",
            ator_tipo="QUALQUER",
            processo_id="proc-1",
        )
        assert evento.estado_novo == "MEIO"


# ══════════════════════════════════════════════════════════════════════════
# EventoTransicao — testes do evento de transição
# ══════════════════════════════════════════════════════════════════════════

class TestEventoTransicao:
    """Testes do dataclass EventoTransicao."""

    def test_hash_calculado_automaticamente(self) -> None:
        evento = EventoTransicao(
            id="evt-1",
            processo_id="proc-1",
            estado_anterior="A",
            estado_novo="B",
            ator_id="ator-1",
            ator_tipo="SECRETARIA",
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            payload={},
            hash_anterior="",
        )
        assert evento.hash != ""
        assert len(evento.hash) == 64  # SHA-256 hex

    def test_hash_determinístico(self) -> None:
        ts = datetime(2026, 1, 1, tzinfo=UTC)
        kwargs = dict(
            id="evt-1",
            processo_id="proc-1",
            estado_anterior="A",
            estado_novo="B",
            ator_id="ator-1",
            ator_tipo="SECRETARIA",
            timestamp=ts,
            payload={},
            hash_anterior="",
        )
        e1 = EventoTransicao(**kwargs)
        e2 = EventoTransicao(**kwargs)
        assert e1.hash == e2.hash

    def test_hash_muda_com_dados_diferentes(self) -> None:
        ts = datetime(2026, 1, 1, tzinfo=UTC)
        e1 = EventoTransicao(
            id="evt-1", processo_id="proc-1",
            estado_anterior="A", estado_novo="B",
            ator_id="ator-1", ator_tipo="SECRETARIA",
            timestamp=ts, payload={}, hash_anterior="",
        )
        e2 = EventoTransicao(
            id="evt-2", processo_id="proc-1",
            estado_anterior="A", estado_novo="B",
            ator_id="ator-1", ator_tipo="SECRETARIA",
            timestamp=ts, payload={}, hash_anterior="",
        )
        assert e1.hash != e2.hash


# ══════════════════════════════════════════════════════════════════════════
# ResultadoValidacao
# ══════════════════════════════════════════════════════════════════════════

class TestResultadoValidacao:
    def test_sucesso(self) -> None:
        r = ResultadoValidacao.sucesso()
        assert r.ok is True
        assert r.erros == []

    def test_falha(self) -> None:
        erros = [ErroValidacao(campo="cpf", mensagem="obrigatório")]
        r = ResultadoValidacao.falha(erros)
        assert r.ok is False
        assert len(r.erros) == 1


# ══════════════════════════════════════════════════════════════════════════
# RitoFSM — testes da classe base abstrata
# ══════════════════════════════════════════════════════════════════════════

class RitoTeste(RitoFSM):
    """Implementação concreta de RitoFSM para teste."""

    @property
    def transicoes(self) -> dict[str, list[str]]:
        return TRANSICOES_TESTE

    @property
    def estados_terminais(self) -> set[str]:
        return TERMINAIS_TESTE

    @property
    def permissoes(self) -> dict[str, list[str]]:
        return PERMISSOES_TESTE


class TestRitoFSM:
    """Testes da classe base RitoFSM."""

    def test_criar_engine(self) -> None:
        rito = RitoTeste()
        engine = rito.criar_engine()
        assert isinstance(engine, FSMEngine)
        assert engine.transicoes_validas("INICIO") == ["MEIO"]

    def test_validar_definicao_valida(self) -> None:
        rito = RitoTeste()
        erros = rito.validar_definicao()
        assert erros == []

    def test_validar_definicao_terminal_com_saida(self) -> None:
        class RitoInvalido(RitoFSM):
            @property
            def transicoes(self) -> dict[str, list[str]]:
                return {"A": ["B"], "B": ["A"]}  # B não é terminal mas…

            @property
            def estados_terminais(self) -> set[str]:
                return {"B"}  # …marcado como terminal

        rito = RitoInvalido()
        erros = rito.validar_definicao()
        assert any("terminal" in e.lower() and "B" in e for e in erros)

    def test_validar_definicao_destino_inexistente(self) -> None:
        class RitoInvalido(RitoFSM):
            @property
            def transicoes(self) -> dict[str, list[str]]:
                return {"A": ["FANTASMA"]}

            @property
            def estados_terminais(self) -> set[str]:
                return set()

        rito = RitoInvalido()
        erros = rito.validar_definicao()
        assert any("FANTASMA" in e for e in erros)

    def test_validar_definicao_permissao_estado_inexistente(self) -> None:
        class RitoInvalido(RitoFSM):
            @property
            def transicoes(self) -> dict[str, list[str]]:
                return {"A": ["B"], "B": []}

            @property
            def estados_terminais(self) -> set[str]:
                return {"B"}

            @property
            def permissoes(self) -> dict[str, list[str]]:
                return {"INEXISTENTE": ["SECRETARIA"]}

        rito = RitoInvalido()
        erros = rito.validar_definicao()
        assert any("INEXISTENTE" in e for e in erros)


# ══════════════════════════════════════════════════════════════════════════
# Exceções
# ══════════════════════════════════════════════════════════════════════════

class TestExcecoes:
    def test_erro_protocolo(self) -> None:
        erros = [
            ErroValidacao(campo="cpf", mensagem="obrigatório"),
            ErroValidacao(campo="valor_causa", mensagem="deve ser > 0"),
        ]
        exc = ErroProtocolo(erros)
        assert len(exc.erros) == 2
        assert "cpf" in str(exc)

    def test_transicao_invalida(self) -> None:
        exc = TransicaoInvalida("A", "C", ["B"])
        assert exc.estado_atual == "A"
        assert exc.transicao_tentada == "C"
        assert exc.transicoes_validas == ["B"]

    def test_ator_nao_autorizado(self) -> None:
        exc = AtorNaoAutorizado("PARTE", "TRIAGEM", "INICIO")
        assert "PARTE" in str(exc)
        assert "TRIAGEM" in str(exc)

    def test_estado_terminal(self) -> None:
        exc = EstadoTerminal("ARQUIVADO")
        assert "ARQUIVADO" in str(exc)
        assert "imutável" in str(exc).lower() or "terminal" in str(exc).lower()

    def test_prazo_expirado(self) -> None:
        exc = PrazoExpirado("regularização", 5, "art. 9º §2º")
        assert exc.prazo_dias == 5
        assert "art. 9º" in str(exc)

    def test_competencia_excluida(self) -> None:
        exc = CompetenciaExcluida("matéria criminal", "art. 6º §1º III")
        assert "criminal" in str(exc)


# ══════════════════════════════════════════════════════════════════════════
# EventoProcessual — modelo Pydantic do log
# ══════════════════════════════════════════════════════════════════════════

class TestEventoProcessual:
    def test_criacao(self) -> None:
        proc_id = uuid4()
        ator_id = uuid4()
        evento = EventoProcessual(
            tipo="SOLICITACAO_RECEBIDA",
            processo_id=proc_id,
            ator_id=ator_id,
            ator_tipo=TipoAtor.PARTE,
        )
        assert evento.tipo == "SOLICITACAO_RECEBIDA"
        assert evento.processo_id == proc_id
        assert evento.hash != ""
        assert len(evento.hash) == 64

    def test_imutavel(self) -> None:
        evento = EventoProcessual(
            tipo="TESTE",
            processo_id=uuid4(),
            ator_id=uuid4(),
            ator_tipo=TipoAtor.SECRETARIA,
        )
        with pytest.raises(Exception):  # frozen=True
            evento.tipo = "OUTRO"  # type: ignore[misc]

    def test_hash_deterministico(self) -> None:
        proc_id = uuid4()
        ator_id = uuid4()
        ts = datetime(2026, 1, 1, tzinfo=UTC)
        kwargs = dict(
            id=uuid4(),
            tipo="TESTE",
            processo_id=proc_id,
            ator_id=ator_id,
            ator_tipo=TipoAtor.SECRETARIA,
            timestamp=ts,
        )
        e1 = EventoProcessual(**kwargs)
        e2 = EventoProcessual(**kwargs)
        assert e1.hash == e2.hash


# ══════════════════════════════════════════════════════════════════════════
# Endereco
# ══════════════════════════════════════════════════════════════════════════

class TestEndereco:
    def test_endereco_valido(self) -> None:
        e = Endereco(
            logradouro="Rua XV",
            numero="100",
            bairro="Centro",
            cidade="Curitiba",
            uf=UF.PR,
            cep="80020310",
        )
        assert e.cep == "80020-310"

    def test_cep_com_formatacao(self) -> None:
        e = Endereco(
            logradouro="Rua XV",
            numero="100",
            bairro="Centro",
            cidade="Curitiba",
            uf=UF.PR,
            cep="80020-310",
        )
        assert e.cep == "80020-310"

    def test_cep_invalido(self) -> None:
        with pytest.raises(Exception):
            Endereco(
                logradouro="Rua XV",
                numero="100",
                bairro="Centro",
                cidade="Curitiba",
                uf=UF.PR,
                cep="123",  # muito curto
            )


# ══════════════════════════════════════════════════════════════════════════
# Parte
# ══════════════════════════════════════════════════════════════════════════

class TestParte:
    def test_parte_fisica_valida(self, endereco_valido: Endereco) -> None:
        parte = Parte(
            nome="João da Silva",
            tipo_pessoa=TipoPessoa.FISICA,
            cpf="52998224725",
            email="joao@email.com",
            telefone="41999998888",
            endereco=endereco_valido,
        )
        assert parte.nome == "João da Silva"
        assert parte.cpf == "529.982.247-25"  # formatado

    def test_parte_juridica_valida(self, endereco_valido: Endereco) -> None:
        parte = Parte(
            nome="Empresa XPTO Ltda",
            tipo_pessoa=TipoPessoa.JURIDICA,
            cnpj="11222333000181",
            email="contato@xpto.com.br",
            telefone="4133334444",
            endereco=endereco_valido,
        )
        assert parte.cnpj == "11.222.333/0001-81"

    def test_pessoa_fisica_sem_cpf_erro(self, endereco_valido: Endereco) -> None:
        with pytest.raises(ValueError, match="CPF"):
            Parte(
                nome="João",
                tipo_pessoa=TipoPessoa.FISICA,
                email="joao@email.com",
                telefone="41999998888",
                endereco=endereco_valido,
            )

    def test_pessoa_juridica_sem_cnpj_erro(self, endereco_valido: Endereco) -> None:
        with pytest.raises(ValueError, match="CNPJ"):
            Parte(
                nome="Empresa",
                tipo_pessoa=TipoPessoa.JURIDICA,
                email="contato@empresa.com",
                telefone="4133334444",
                endereco=endereco_valido,
            )

    def test_email_invalido(self, endereco_valido: Endereco) -> None:
        with pytest.raises(Exception):
            Parte(
                nome="João",
                tipo_pessoa=TipoPessoa.FISICA,
                cpf="52998224725",
                email="nao-e-email",
                telefone="41999998888",
                endereco=endereco_valido,
            )

    def test_telefone_invalido(self, endereco_valido: Endereco) -> None:
        with pytest.raises(Exception):
            Parte(
                nome="João",
                tipo_pessoa=TipoPessoa.FISICA,
                cpf="52998224725",
                email="joao@email.com",
                telefone="123",  # muito curto
                endereco=endereco_valido,
            )


# ══════════════════════════════════════════════════════════════════════════
# Validação CPF/CNPJ
# ══════════════════════════════════════════════════════════════════════════

class TestValidacaoCPF:
    def test_cpf_valido(self) -> None:
        assert validar_cpf("52998224725") == "529.982.247-25"

    def test_cpf_com_formatacao(self) -> None:
        assert validar_cpf("529.982.247-25") == "529.982.247-25"

    def test_cpf_invalido_digito(self) -> None:
        with pytest.raises(ValueError, match="dígito verificador"):
            validar_cpf("52998224720")  # dígito errado

    def test_cpf_sequencia_repetida(self) -> None:
        with pytest.raises(ValueError, match="inválido"):
            validar_cpf("11111111111")

    def test_cpf_tamanho_errado(self) -> None:
        with pytest.raises(ValueError, match="11 dígitos"):
            validar_cpf("123")


class TestValidacaoCNPJ:
    def test_cnpj_valido(self) -> None:
        assert validar_cnpj("11222333000181") == "11.222.333/0001-81"

    def test_cnpj_invalido_digito(self) -> None:
        with pytest.raises(ValueError, match="dígito verificador"):
            validar_cnpj("11222333000182")

    def test_cnpj_sequencia_repetida(self) -> None:
        with pytest.raises(ValueError, match="inválido"):
            validar_cnpj("11111111111111")


# ══════════════════════════════════════════════════════════════════════════
# Advogado
# ══════════════════════════════════════════════════════════════════════════

class TestAdvogado:
    def test_advogado_valido(self) -> None:
        adv = Advogado(
            nome="Dra. Maria Santos",
            oab_numero="12345",
            oab_uf=UF.PR,
            email="maria@advocacia.com",
            telefone="41999997777",
        )
        assert adv.oab_uf == UF.PR

    def test_advogado_email_normalizado(self) -> None:
        adv = Advogado(
            nome="Dr. Pedro",
            oab_numero="54321",
            oab_uf=UF.SP,
            email="  Pedro@Advocacia.COM  ",
            telefone="11999998888",
        )
        assert adv.email == "pedro@advocacia.com"


# ══════════════════════════════════════════════════════════════════════════
# Pedido
# ══════════════════════════════════════════════════════════════════════════

class TestPedido:
    def test_pedido_valido(self) -> None:
        pedido = Pedido(
            descricao="Devolução de valores pagos indevidamente",
            valor=Decimal("1500.00"),
        )
        assert pedido.valor == Decimal("1500.00")

    def test_pedido_com_fundamentos(self) -> None:
        pedido = Pedido(
            descricao="Indenização por danos morais",
            valor=Decimal("5000.00"),
            fundamentos=[
                Fundamento(
                    tipo="LEGAL",
                    descricao="Responsabilidade civil",
                    dispositivo_legal="art. 186 CC",
                ),
            ],
        )
        assert len(pedido.fundamentos) == 1

    def test_pedido_valor_zero_permitido(self) -> None:
        pedido = Pedido(
            descricao="Obrigação de fazer",
            valor=Decimal("0"),
        )
        assert pedido.valor == Decimal("0")

    def test_pedido_valor_negativo_erro(self) -> None:
        with pytest.raises(Exception):
            Pedido(
                descricao="Pedido inválido",
                valor=Decimal("-100"),
            )


# ══════════════════════════════════════════════════════════════════════════
# Processo
# ══════════════════════════════════════════════════════════════════════════

class TestProcesso:
    def test_processo_criacao(self) -> None:
        proc = Processo(
            rito=Rito.CEJUSC_PRE,
            estado_atual="SOLICITACAO_RECEBIDA",
            unidade="CEJUSC-CENTRAL-CURITIBA",
        )
        assert proc.rito == Rito.CEJUSC_PRE
        assert proc.estado_atual == "SOLICITACAO_RECEBIDA"
        assert proc.numero is None  # gerado apenas em CADASTRADO

    def test_processo_com_numero(self) -> None:
        proc = Processo(
            rito=Rito.CEJUSC_PRE,
            estado_atual="CADASTRADO",
            numero="0001234-56.2026.8.16.0001",
            unidade="CEJUSC-CENTRAL-CURITIBA",
            comarca="Curitiba",
        )
        assert proc.numero is not None
