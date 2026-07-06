"""Entrypoint del bot. Preferir: python -m itacamba_reportes.cli

Funciona tanto con el paquete instalado (pip install -e .) como
ejecutando directo desde la raiz del repo (inserta src/ al path).
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from itacamba_reportes.cli import main
except ImportError:  # ejecucion directa sin instalar el paquete
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
    from itacamba_reportes.cli import main


if __name__ == "__main__":
    sys.exit(main())
