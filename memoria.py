"""Mudou para ryker/memory/memoria.py (estrutura do RYKER).
Este arquivo só mantém `import memoria` funcionando: é o mesmo módulo, com o mesmo estado."""
import sys

from ryker.memory import memoria as _modulo

sys.modules[__name__] = _modulo
