"""Configuração de testes — adiciona cejusc-pre/ ao sys.path."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
