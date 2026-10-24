"""Mudou para ryker/agent/agente_tela.py (estrutura do RYKER).
Este arquivo só mantém `import agente_tela` funcionando: é o mesmo módulo, com o mesmo estado."""
import sys

from ryker.agent import agente_tela as _modulo

sys.modules[__name__] = _modulo
