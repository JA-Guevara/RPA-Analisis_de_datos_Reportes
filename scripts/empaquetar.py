"""Genera un ZIP limpio del proyecto para entregas/revisiones.

Usa `git archive` sobre HEAD: solo entra lo versionado — sin venv,
sin .env, sin __pycache__, sin storage runtime (todo eso esta en
.gitignore y por lo tanto fuera del archivo).

Uso:
    python scripts/empaquetar.py [salida.zip]

Requisito: repo git inicializado (fase 00 del plan de refactor).
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    nombre = (
        sys.argv[1]
        if len(sys.argv) > 1
        else f"Bot_Itacamba_Reportes_{datetime.now():%Y-%m-%d}.zip"
    )
    destino = Path(nombre)
    if not destino.is_absolute():
        destino = PROJECT_ROOT / destino

    resultado = subprocess.run(
        ["git", "archive", "--format=zip", "-o", str(destino), "HEAD"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if resultado.returncode != 0:
        print(f"ERROR git archive: {resultado.stderr.strip()}")
        return 1

    mb = destino.stat().st_size / 1_048_576
    print(f"Paquete limpio: {destino} ({mb:.1f} MB)")
    if mb > 10:
        print("AVISO: >10 MB — revisar si entro algo indebido (git ls-files).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
