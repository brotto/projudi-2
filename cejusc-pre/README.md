# cejusc-pre

**MVP do Sistema Juízo — CEJUSC pré-processual**
**Base legal:** Resolução 403/2023 · NUPEMEC · TJPR

## O que é

Implementação da Finite State Machine do procedimento pré-processual do CEJUSC,
conforme Res. 403/2023 do NUPEMEC do TJPR.

Este módulo é o **projeto zero** do Sistema Juízo — o caso de uso mais simples
possível para validar a arquitetura antes de avançar para ritos complexos.

## Estrutura

```
cejusc-pre/
├── fsm/
│   ├── estados.py    # Enum EstadoCejusc + TRANSICOES + PERMISSOES + PRAZOS
│   └── engine.py     # Instância do FSMEngine configurada para o CEJUSC
├── models/
│   ├── reclamacao.py # Modelo principal com validação completa
│   ├── partes.py     # Parte reclamante / reclamada / advogado
│   ├── sessao.py     # Sessão de conciliação/mediação + ata
│   └── acordo.py     # Acordo + condições + prazos de cumprimento
├── api/
│   ├── main.py       # FastAPI app
│   └── routes/       # Endpoints REST
└── tests/
    ├── test_fsm.py   # Testes da máquina de estados (cobertura 100% esperada)
    ├── test_models.py
    └── test_api.py
```

## FSM — estados e transições

Ver fluxograma visual em: `../docs/fluxogramas/cejusc-pre-fsm.html`
Ver estados em: `fsm/estados.py`

## Desenvolvimento

```bash
# A partir da raiz do projeto
pip install -e "../juizo-core[dev]"
pytest tests/ -v --cov=.
```

## Regras de negócio críticas

- Competência verificada na triagem (art. 6º §1º) — 8 matérias excluídas
- Prazo máximo sem sessão: 30 dias corridos (art. 14)
- Prazo máximo com continuações: 60 dias corridos (art. 14)
- Ausência de qualquer parte: arquivamento imediato (art. 12 §3º)
- Menores/incapazes: MP obrigatório antes da homologação (art. 15 §ú)
- NÃO induz prevenção, NÃO interrompe prescrição (art. 4º)
