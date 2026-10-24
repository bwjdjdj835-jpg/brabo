"""Mudou para ryker/automation/tela.py (estrutura do RYKER).
Este arquivo só mantém `import tela` funcionando: é o mesmo módulo, com o mesmo estado."""
import sys

from ryker.automation import tela as _modulo

sys.modules[__name__] = _modulo
