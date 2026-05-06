"""Configuracao de testes — adiciona rito-sumarissimo/ e juizo-core/ ao sys.path."""

import sys
from pathlib import Path

# Adiciona rito-sumarissimo/ ao sys.path para imports locais (fsm, models)
sys.path.insert(0, str(Path(__file__).parent))

# Adiciona juizo-core/ ao sys.path para imports do juizo-core
sys.path.insert(0, str(Path(__file__).parent.parent / "juizo-core"))
