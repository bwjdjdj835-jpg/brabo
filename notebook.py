"""Mudou para ryker/desktop/notebook.py (estrutura do RYKER).
Este arquivo só mantém `import notebook` funcionando: é o mesmo módulo, com o mesmo estado."""
import sys

from ryker.desktop import notebook as _modulo

sys.modules[__name__] = _modulo
