# juizo-core

**DSL processual para o Sistema de Informação Jurisdicional Juízo.**

Biblioteca Python que define a gramática de cada ato processual como objeto de dados validável,
implementa o motor FSM genérico para qualquer rito, e fornece ferramentas de migração de legado.

## Filosofia

O processo judicial é informação estruturada, não texto livre em PDFs.
`juizo-core` força a tecnicalidade perfeita em cada ato processual —
se o sistema não compreende, retorna erro com campo exato.

## Estrutura

```
juizo/
├── fsm/
│   ├── base.py       # Classe base FSM genérica
│   └── engine.py     # Motor de transições + validação
├── models/
│   ├── base.py       # EventoProcessual base (append-only log)
│   ├── partes.py     # Parte, Advogado, Testemunha
│   ├── pedidos.py    # Pedido, Fundamento
│   └── processo.py   # Processo, Rito
├── migration/
│   └── legacy.py     # OCR, transcrição, HTR
└── exceptions.py     # ErroProtocolo, TransicaoInvalida, etc.
```

## Uso (CEJUSC-PRÉ exemplo)

```python
from juizo.models import Reclamacao, Parte, Pedido, Endereco
from juizo.fsm.engine import FSMEngine

reclamacao = Reclamacao(
    reclamante=Parte(cpf="xxx", nome="...", email="...", telefone="..."),
    reclamado=Parte(cnpj="xxx", nome="...", endereco=Endereco(...)),
    fatos="...",
    pedidos=[Pedido(descricao="...", valor=1500.00)],
    valor_causa=1500.00,
)

resultado = reclamacao.validar()
if resultado.ok:
    sistema.protocolar(reclamacao)
```

## Desenvolvimento

```bash
pip install -e ".[dev]"
pytest
```
