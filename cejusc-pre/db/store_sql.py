"""
Implementacao SQLAlchemy do EventStore — persistencia em banco de dados.

Mesma interface do EventStore in-memory (api/store.py), mas persiste
dados em SQLAlchemy (SQLite no MVP, PostgreSQL em producao).

Principios (CLAUDE.md s2):
- Event Sourcing: log imutavel de eventos (append-only)
- Estado atual derivado do log + cache na tabela reclamacoes
- Nenhum evento e editado ou deletado
"""

from __future__ import annotations

from datetime import datetime, UTC
from uuid import UUID, uuid4
from typing import Any

from sqlalchemy.orm import Session

from juizo.fsm.engine import EventoTransicao

from fsm.engine import engine as fsm_engine
from fsm.estados import EstadoCejusc

from db.models import (
    EventoLog,
    ReclamacaoDB,
    SessaoDB,
    AcordoDB,
    UsuarioDB,
)


class EventStoreSql:
    """
    Repositorio de eventos com persistencia SQLAlchemy.

    Mesma interface do EventStore in-memory para manter compatibilidade
    com as rotas da API. Internamente usa SQLAlchemy Session.

    Event Sourcing (ADR-001):
    - Eventos sao a fonte de verdade
    - Estado atual e cacheado na coluna reclamacoes.estado_atual
    - Nenhum evento e editado ou deletado
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ══════════════════════════════════════════════════════════════════════
    # Reclamacoes
    # ══════════════════════════════════════════════════════════════════════

    def criar_reclamacao(self, reclamacao_id: UUID, dados: dict[str, Any]) -> EventoTransicao:
        """Cria reclamacao e registra evento SOLICITACAO_RECEBIDA."""
        agora = datetime.now(UTC)

        # Persistir reclamacao
        rec = ReclamacaoDB(
            id=str(reclamacao_id),
            cejusc_destino=dados.get("cejusc_destino", ""),
            reclamante=dados.get("reclamante", {}),
            reclamado=dados.get("reclamado", {}),
            fatos=dados.get("fatos", ""),
            pedidos=dados.get("pedidos", []),
            valor_causa=dados.get("valor_causa", "0"),
            modalidade=dados.get("modalidade", ""),
            opcao_custas=dados.get("opcao_custas", ""),
            estado_atual=EstadoCejusc.SOLICITACAO_RECEBIDA,
            protocolado_em=agora,
        )
        self._session.add(rec)

        # Criar evento de protocolo
        evento = EventoTransicao(
            id=str(uuid4()),
            processo_id=str(reclamacao_id),
            estado_anterior="",
            estado_novo=EstadoCejusc.SOLICITACAO_RECEBIDA,
            ator_id=dados.get("ator_id", "sistema"),
            ator_tipo=dados.get("ator_tipo", "PARTE"),
            timestamp=agora,
            payload={"tipo": "protocolo_reclamacao"},
            hash_anterior="",
        )

        # Persistir evento no log
        evento_db = EventoLog(
            id=evento.id,
            processo_id=evento.processo_id,
            estado_anterior=evento.estado_anterior,
            estado_novo=evento.estado_novo,
            ator_id=evento.ator_id,
            ator_tipo=evento.ator_tipo,
            timestamp=evento.timestamp,
            payload=evento.payload,
            hash_anterior=evento.hash_anterior,
            hash=evento.hash,
        )
        self._session.add(evento_db)
        self._session.commit()

        return evento

    def transicionar(
        self,
        reclamacao_id: UUID,
        estado_destino: str,
        ator_id: str,
        ator_tipo: str,
        payload: dict[str, Any] | None = None,
    ) -> EventoTransicao:
        """Executa transicao FSM e registra evento no log."""
        rec = self._session.query(ReclamacaoDB).filter(
            ReclamacaoDB.id == str(reclamacao_id)
        ).first()

        estado_atual = rec.estado_atual

        # Buscar ultimo evento para encadeamento de hash
        ultimo_evento = (
            self._session.query(EventoLog)
            .filter(EventoLog.processo_id == str(reclamacao_id))
            .order_by(EventoLog.timestamp.desc())
            .first()
        )
        hash_anterior = ultimo_evento.hash if ultimo_evento else ""

        # Delegar validacao e criacao do evento ao motor FSM
        evento = fsm_engine.transicionar(
            estado_atual=estado_atual,
            estado_destino=estado_destino,
            ator_id=ator_id,
            ator_tipo=ator_tipo,
            processo_id=str(reclamacao_id),
            payload=payload or {},
            hash_anterior=hash_anterior,
        )

        # Persistir evento no log (append-only)
        evento_db = EventoLog(
            id=evento.id,
            processo_id=evento.processo_id,
            estado_anterior=evento.estado_anterior,
            estado_novo=evento.estado_novo,
            ator_id=evento.ator_id,
            ator_tipo=evento.ator_tipo,
            timestamp=evento.timestamp,
            payload=evento.payload,
            hash_anterior=evento.hash_anterior,
            hash=evento.hash,
        )
        self._session.add(evento_db)

        # Atualizar cache de estado na reclamacao
        rec.estado_atual = estado_destino
        self._session.commit()

        return evento

    def get_reclamacao(self, reclamacao_id: UUID) -> dict[str, Any] | None:
        """Retorna dados da reclamacao pelo ID."""
        rec = self._session.query(ReclamacaoDB).filter(
            ReclamacaoDB.id == str(reclamacao_id)
        ).first()

        if rec is None:
            return None

        return {
            "id": rec.id,
            "cejusc_destino": rec.cejusc_destino,
            "reclamante": rec.reclamante,
            "reclamado": rec.reclamado,
            "fatos": rec.fatos,
            "pedidos": rec.pedidos,
            "valor_causa": rec.valor_causa,
            "modalidade": rec.modalidade,
            "opcao_custas": rec.opcao_custas,
            "estado_atual": rec.estado_atual,
            "protocolado_em": rec.protocolado_em.isoformat() if rec.protocolado_em else None,
        }

    def listar_reclamacoes(self) -> list[dict[str, Any]]:
        """Retorna todas as reclamacoes cadastradas."""
        recs = self._session.query(ReclamacaoDB).all()
        return [
            {
                "id": rec.id,
                "cejusc_destino": rec.cejusc_destino,
                "reclamante": rec.reclamante,
                "reclamado": rec.reclamado,
                "fatos": rec.fatos,
                "pedidos": rec.pedidos,
                "valor_causa": rec.valor_causa,
                "modalidade": rec.modalidade,
                "opcao_custas": rec.opcao_custas,
                "estado_atual": rec.estado_atual,
            }
            for rec in recs
        ]

    def get_historico(self, reclamacao_id: UUID) -> list[dict[str, Any]]:
        """Retorna log completo de eventos da reclamacao (append-only)."""
        eventos = (
            self._session.query(EventoLog)
            .filter(EventoLog.processo_id == str(reclamacao_id))
            .order_by(EventoLog.timestamp.asc())
            .all()
        )
        return [
            {
                "id": e.id,
                "estado_anterior": e.estado_anterior,
                "estado_novo": e.estado_novo,
                "ator_id": e.ator_id,
                "ator_tipo": e.ator_tipo,
                "timestamp": e.timestamp.isoformat() if e.timestamp else "",
                "payload": e.payload,
                "hash": e.hash,
            }
            for e in eventos
        ]

    def get_estado(self, reclamacao_id: UUID) -> str | None:
        """Retorna estado atual da reclamacao (cache na tabela)."""
        rec = self._session.query(ReclamacaoDB).filter(
            ReclamacaoDB.id == str(reclamacao_id)
        ).first()

        if rec is None:
            return None
        return rec.estado_atual

    def get_transicoes_validas(self, reclamacao_id: UUID) -> list[str]:
        """Retorna transicoes validas a partir do estado atual."""
        estado = self.get_estado(reclamacao_id)
        if estado is None:
            return []
        return fsm_engine.transicoes_validas(estado)

    # ══════════════════════════════════════════════════════════════════════
    # Sessoes
    # ══════════════════════════════════════════════════════════════════════

    def criar_sessao(self, sessao_id: UUID, dados: dict[str, Any]) -> None:
        """Persiste uma nova sessao de conciliacao/mediacao."""
        sessao = SessaoDB(
            id=str(sessao_id),
            reclamacao_id=dados.get("reclamacao_id", ""),
            conciliador_id=dados.get("conciliador_id", ""),
            conciliador_nome=dados.get("conciliador_nome", ""),
            data_agendada=dados.get("data_agendada", ""),
            numero_sessao=dados.get("numero_sessao", 1),
            resultado=dados.get("resultado"),
            criada_em=datetime.now(UTC),
        )
        self._session.add(sessao)
        self._session.commit()

    def get_sessao(self, sessao_id: UUID) -> dict[str, Any] | None:
        """Retorna dados de uma sessao pelo ID."""
        s = self._session.query(SessaoDB).filter(
            SessaoDB.id == str(sessao_id)
        ).first()

        if s is None:
            return None

        return {
            "id": s.id,
            "reclamacao_id": s.reclamacao_id,
            "conciliador_id": s.conciliador_id,
            "conciliador_nome": s.conciliador_nome,
            "data_agendada": s.data_agendada,
            "numero_sessao": s.numero_sessao,
            "resultado": s.resultado,
            "ata_conteudo": s.ata_conteudo,
            "criada_em": s.criada_em.isoformat() if s.criada_em else None,
        }

    def listar_sessoes(self, reclamacao_id: UUID | None = None) -> list[dict[str, Any]]:
        """Lista sessoes, opcionalmente filtradas por reclamacao."""
        query = self._session.query(SessaoDB)
        if reclamacao_id:
            query = query.filter(SessaoDB.reclamacao_id == str(reclamacao_id))

        sessoes = query.all()
        return [
            {
                "id": s.id,
                "reclamacao_id": s.reclamacao_id,
                "conciliador_id": s.conciliador_id,
                "conciliador_nome": s.conciliador_nome,
                "data_agendada": s.data_agendada,
                "numero_sessao": s.numero_sessao,
                "resultado": s.resultado,
                "ata_conteudo": s.ata_conteudo,
                "criada_em": s.criada_em.isoformat() if s.criada_em else None,
            }
            for s in sessoes
        ]

    def atualizar_sessao(self, sessao_id: UUID, dados: dict[str, Any]) -> None:
        """Atualiza dados de uma sessao existente."""
        s = self._session.query(SessaoDB).filter(
            SessaoDB.id == str(sessao_id)
        ).first()

        if s is None:
            return

        for campo, valor in dados.items():
            if hasattr(s, campo):
                setattr(s, campo, valor)

        self._session.commit()

    # ══════════════════════════════════════════════════════════════════════
    # Acordos
    # ══════════════════════════════════════════════════════════════════════

    def criar_acordo(self, acordo_id: UUID, dados: dict[str, Any]) -> None:
        """Persiste um novo acordo."""
        acordo = AcordoDB(
            id=str(acordo_id),
            reclamacao_id=dados.get("reclamacao_id", ""),
            sessao_id=dados.get("sessao_id", ""),
            condicoes=dados.get("condicoes", []),
            envolve_menores_incapazes=dados.get("envolve_menores_incapazes", False),
            status=dados.get("status", "REDIGIDO"),
            valor_total=dados.get("valor_total", "0"),
            pode_homologar=dados.get("pode_homologar", True),
            parecer_mp=dados.get("parecer_mp"),
            redigido_em=datetime.now(UTC),
        )
        self._session.add(acordo)
        self._session.commit()

    def get_acordo(self, acordo_id: UUID) -> dict[str, Any] | None:
        """Retorna dados de um acordo pelo ID."""
        a = self._session.query(AcordoDB).filter(
            AcordoDB.id == str(acordo_id)
        ).first()

        if a is None:
            return None

        return {
            "id": a.id,
            "reclamacao_id": a.reclamacao_id,
            "sessao_id": a.sessao_id,
            "condicoes": a.condicoes,
            "envolve_menores_incapazes": a.envolve_menores_incapazes,
            "status": a.status,
            "valor_total": a.valor_total,
            "pode_homologar": a.pode_homologar,
            "parecer_mp": a.parecer_mp,
            "redigido_em": a.redigido_em.isoformat() if a.redigido_em else None,
        }

    def atualizar_acordo(self, acordo_id: UUID, dados: dict[str, Any]) -> None:
        """Atualiza dados de um acordo existente."""
        a = self._session.query(AcordoDB).filter(
            AcordoDB.id == str(acordo_id)
        ).first()

        if a is None:
            return

        for campo, valor in dados.items():
            if hasattr(a, campo):
                setattr(a, campo, valor)

        self._session.commit()

    # ══════════════════════════════════════════════════════════════════════
    # Usuarios
    # ══════════════════════════════════════════════════════════════════════

    def criar_usuario(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Persiste um novo usuario no banco."""
        usuario = UsuarioDB(
            id=dados.get("id", str(uuid4())),
            nome=dados["nome"],
            email=dados["email"],
            senha_hash=dados["senha_hash"],
            perfil=dados["perfil"],
            ativo=dados.get("ativo", True),
            criado_em=datetime.now(UTC),
        )
        self._session.add(usuario)
        self._session.commit()

        return {
            "id": usuario.id,
            "nome": usuario.nome,
            "email": usuario.email,
            "perfil": usuario.perfil,
            "ativo": usuario.ativo,
            "criado_em": usuario.criado_em.isoformat(),
        }

    def get_usuario_por_email(self, email: str) -> dict[str, Any] | None:
        """Busca usuario pelo e-mail."""
        u = self._session.query(UsuarioDB).filter(
            UsuarioDB.email == email
        ).first()

        if u is None:
            return None

        return {
            "id": u.id,
            "nome": u.nome,
            "email": u.email,
            "senha_hash": u.senha_hash,
            "perfil": u.perfil,
            "ativo": u.ativo,
            "criado_em": u.criado_em.isoformat() if u.criado_em else None,
        }

    def get_usuario(self, usuario_id: str) -> dict[str, Any] | None:
        """Busca usuario pelo ID."""
        u = self._session.query(UsuarioDB).filter(
            UsuarioDB.id == usuario_id
        ).first()

        if u is None:
            return None

        return {
            "id": u.id,
            "nome": u.nome,
            "email": u.email,
            "senha_hash": u.senha_hash,
            "perfil": u.perfil,
            "ativo": u.ativo,
            "criado_em": u.criado_em.isoformat() if u.criado_em else None,
        }
