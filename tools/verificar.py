"""Gate único de verificación del proyecto (Fase 7 del plan 2026-07-06).

Corre en orden:
  1. Compilación de todo src/ + tools/ + tests/  (detecta truncaciones)
  2. Suite de tests offline (motor + goldens + unitarias)
  3. Validación de manifests de todos los reportes (que no mientan)
  4. [--data RUTA] Simuladores despacho + gd20 con PARIDAD contra el
     baseline de storage/calibracion/baseline/ (lo crea si no existe)

Uso:
    python tools/verificar.py [--data C:/ruta/Archivos]

Exit code 0 = todos los gates verdes. Correr SIEMPRE antes de commitear
un cambio de fórmulas/columnas/reglas.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

BASELINE = PROJECT / "storage" / "calibracion" / "baseline"
ACTUAL = PROJECT / "storage" / "calibracion" / "actual"

TARGETS = {
    "simular_despacho.py": ["int_despacho_bi", "int_despacho_mes"],
    "simular_gd20.py": ["int_gd20_hashed"],
}


def paso(nombre: str, ok: bool, detalle: str = "") -> bool:
    print(f"[{'OK ' if ok else 'FAIL'}] {nombre}" + (f" — {detalle}" if detalle else ""))
    return ok


def gate_compilacion() -> bool:
    import ast
    malos = []
    for carpeta in ("src", "tools", "tests"):
        for p in (PROJECT / carpeta).rglob("*.py"):
            if "__pycache__" in str(p):
                continue
            try:
                ast.parse(p.read_text(encoding="utf-8"))
            except Exception as exc:
                malos.append(f"{p.name}: {exc}")
    return paso("compilación", not malos, "; ".join(malos[:3]))


def gate_tests() -> bool:
    import os
    import tempfile

    # Config propia y rootdir explicito: corrida identica en cualquier
    # maquina, sin depender de la deteccion automatica de pytest.
    with tempfile.NamedTemporaryFile("w", suffix=".ini", delete=False) as f:
        f.write("[pytest]\n")
        ini = f.name
    env = dict(os.environ)
    env.update({"PYTHONPATH": "src", "PYTHONDONTWRITEBYTECODE": "1"})
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-c", ini,
         f"--rootdir={PROJECT}",
         "tests/test_column_engine.py", "tests/test_bulk_insert.py",
         "tests/test_native_records.py",
         "tests/characterization/test_goldens.py"],
        cwd=PROJECT, capture_output=True, text=True, env=env,
    )
    salida = (r.stdout.strip().splitlines() or r.stderr.strip().splitlines() or ["?"])
    return paso("tests", r.returncode == 0, salida[-1])


def gate_manifests() -> bool:
    from itacamba_reportes.config.manifest import validate_all
    resultados = validate_all(PROJECT / "src" / "itacamba_reportes" / "reportes")
    problemas = [p for lista in resultados.values() for p in lista]
    detalle = f"{len(resultados)} reportes" if not problemas else "; ".join(problemas[:4])
    return paso("manifests", not problemas, detalle)


def gate_paridad(data: Path) -> bool:
    import pandas as pd
    ACTUAL.mkdir(parents=True, exist_ok=True)
    ok_total = True
    for script, nombres in TARGETS.items():
        r = subprocess.run(
            [sys.executable, str(PROJECT / "tools" / "calibracion" / script),
             "--data", str(data), "--out", str(ACTUAL)],
            capture_output=True, text=True)
        if r.returncode != 0:
            ok_total &= paso(f"simulador {script}", False,
                             (r.stderr.strip().splitlines() or ["?"])[-1])
            continue
        for n in nombres:
            base_p = BASELINE / f"{n}.pkl"
            act_p = ACTUAL / f"{n}.pkl"
            if not base_p.exists():
                BASELINE.mkdir(parents=True, exist_ok=True)
                act_p.replace(base_p)
                ok_total &= paso(f"paridad {n}", True, "baseline CREADO (primera corrida)")
                continue
            a = pd.read_pickle(base_p).astype("string")
            b = pd.read_pickle(act_p).astype("string")
            if a.shape != b.shape or list(a.columns) != list(b.columns):
                ok_total &= paso(f"paridad {n}", False, f"estructura {a.shape} vs {b.shape}")
                continue
            a = a.sort_values(list(a.columns), na_position="last").reset_index(drop=True)
            b = b.sort_values(list(b.columns), na_position="last").reset_index(drop=True)
            diff = [c for c in a.columns
                    if not ((a[c] == b[c]) | (a[c].isna() & b[c].isna())).all()]
            ok_total &= paso(f"paridad {n}", not diff,
                             f"{len(a)} filas" if not diff else f"DIFF en {diff[:5]}")
    return ok_total


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, default=None,
                    help="Carpeta de datos para el gate de paridad")
    args = ap.parse_args()

    ok = gate_compilacion()
    ok &= gate_tests()
    ok &= gate_manifests()
    if args.data is not None:
        ok &= gate_paridad(args.data)
    else:
        print("[SKIP] paridad (pasar --data para correrla)")
    print("\nVERIFICACIÓN", "COMPLETA — todo verde" if ok else "CON FALLOS")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
