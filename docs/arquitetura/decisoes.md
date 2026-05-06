# Architecture Decision Records — Juízo · Sistema de Informação Jurisdicional

Este arquivo documenta as decisões arquiteturais do projeto.
Cada decisão tem contexto, opções consideradas, decisão tomada e consequências.

---

## ADR-001 · Event Sourcing como modelo de persistência

**Data:** 2026-03-03
**Status:** Aceito

**Contexto:**
O processo judicial é intrinsecamente um log de eventos. Nenhum evento processual
pode ser deletado ou editado — isso seria adulteração de documento público.

**Decisão:**
Usar Event Sourcing como padrão de persistência. O estado atual de qualquer processo
é sempre derivado do log de eventos, nunca armazenado diretamente.

**Consequências:**
- Auditabilidade total por design
- Histórico imutável com hash encadeado (similar a blockchain)
- Complexidade adicional na leitura (necessita de projeções/read models)
- Compatível com requisitos legais de autenticidade documental (ICP-Brasil)

---

## ADR-002 · FSM por rito processual

**Data:** 2026-03-03
**Status:** Aceito

**Contexto:**
Nulidades processuais ocorrem quando atos são praticados fora de fase ou por
atores não autorizados. O sistema atual aceita qualquer coisa, qualquer hora.

**Decisão:**
Cada rito processual terá sua própria FSM (Finite State Machine) implementada em código.
O sistema estruturalmente impossibilita transições inválidas — lança exceção antes de persistir.

**Consequências:**
- Nulidades processuais impossíveis por design
- Prazos computados automaticamente em cada transição
- Cada rito é um módulo independente (cejusc-pre, rito-ordinario, penal, etc.)
- `juizo-core` fornece a engine FSM genérica reutilizável

---

## ADR-003 · Python como linguagem principal

**Data:** 2026-03-03
**Status:** Aceito

**Contexto:**
O projeto requer uma DSL processual, migração de legado (OCR/HTR/transcrição),
e futura integração com modelos de IA para o agente do magistrado.

**Decisão:**
Python 3.12+ com FastAPI para o backend e pydantic para validação de modelos.

**Consequências:**
- Ecossistema rico para IA/ML (futura camada do agente)
- Pydantic garante validação de objetos processuais em runtime
- `juizo-core` publicável no PyPI quando madura
- Ferramentas de migração (pytesseract, whisper) disponíveis nativamente

---

## ADR-004 · Git como metáfora de versionamento processual

**Data:** 2026-03-03
**Status:** Aceito

**Contexto:**
Pedidos incidentais, chicanas e peças extemporâneas abarrotam o main do processo
tornando a análise do juiz trabalhosa e propensa a erros.

**Decisão:**
Pedidos incidentais tramitam como branches. Se deferidos → merge no main.
Se indeferidos → branch morto (auditável, sem peso no main).
O processo principal (main) reflete apenas o que importa para o mérito.

**Consequências:**
- Juiz analisa o main limpo; tribunal superior acessa o DAG completo
- Chicanas isoladas estruturalmente — não contaminam o fluxo principal
- Necessita de UI para visualização de branches (similar ao GitHub)
- Conflitos entre branches resolvidos sempre pelo juiz (não automaticamente)

---

## ADR-005 · MVP: CEJUSC pré-processual

**Data:** 2026-03-03
**Status:** Aceito

**Contexto:**
O sistema completo é complexo. Precisamos validar o conceito com algo construível,
testável e demonstrável antes de qualquer negociação com TJ ou CNJ.

**Decisão:**
Iniciar pelo CEJUSC pré-processual (Res. 403/2023 NUPEMEC TJPR):
~15 estados, ~3 atores principais, sem sentença de mérito, base legal clara.

**Estratégia:** Build → Prove → Then Talk.
Construir o MVP, demonstrar em produção controlada, depois apresentar ao TJ.

**Consequências:**
- Tempo de desenvolvimento estimado: 4–8 semanas para MVP funcional
- Validação real do conceito antes de investir em ritos complexos
- Aprendizados do CEJUSC alimentam a `juizo-core` para os próximos ritos

---
