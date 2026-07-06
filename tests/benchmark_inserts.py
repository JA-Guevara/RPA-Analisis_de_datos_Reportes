"""Benchmark A/B del insert bulk contra la BD real.

Compara las dos rutas con los MISMOS datos (tipos nativos):
  A) SQLAlchemy  session.execute(insert(Model), records)   ← camino anterior
  B) RAW pyodbc  cursor.fast_executemany + executemany     ← camino nuevo

USO (en tu máquina, con la BD real configurada en .env):

    python tests/benchmark_inserts.py --compare      # A vs B con el Excel QUERY real
    python tests/benchmark_inserts.py                # solo B (raw)
    python tests/benchmark_inserts.py --rows 20000   # con df sintético

Escribe únicamente en **stg_query** (staging que el pipeline trunca en
cada corrida normal — seguro). Al terminar queda cargada igual que tras
un run-query.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from time import perf_counter

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import insert, text  # noqa: E402

from itacamba_reportes.config.env_config import EnvConfig  # noqa: E402
from itacamba_reportes.config.sources import load_excel_source  # noqa: E402
from itacamba_reportes.ingestion.excel_reader import ExcelReader  # noqa: E402
from itacamba_reportes.persistence.bulk_insert import bulk_insert  # noqa: E402
from itacamba_reportes.persistence.engine import SessionLocal, engine  # noqa: E402
from itacamba_reportes.persistence.models.stg.stg_query_model import (  # noqa: E402
    StgQueryModel,
)
from itacamba_reportes.persistence.session import get_session  # noqa: E402
from itacamba_reportes.persistence.type_coercion import (  # noqa: E402
    coerce_dataframe_for_model,
)

CONFIGS_DIR = ROOT / "assets" / "configs"


def load_real_query_df() -> pd.DataFrame | None:
    try:
        source = load_excel_source(CONFIGS_DIR, "query")
        reader = ExcelReader(source=source, data_path=EnvConfig.DATA_PATH)
        print(f"Leyendo Excel real: {reader.resolve_path().name} ...")
        return reader.read()
    except Exception as exc:
        print(f"(no se pudo leer el Excel real: {exc})")
        return None


def synthetic_df(rows: int) -> pd.DataFrame:
    print(f"Generando df sintético de {rows} filas ...")
    base = {
        "centro_proveedor": "C001", "sucursal": "SCZ", "material": 10000123,
        "nombre_material": "CEMENTO PORTLAND X", "dia_natural": "01.02.2026",
        "documento_venta": 800000001, "destinatario_mcia": 700000001,
        "nombre_centro_destinatario": "CLIENTE EJEMPLO SRL",
        "poblacion": "SANTA CRUZ", "incoterms": "CIF",
        "clase_doc_ventas": "ZVTA", "tipo_venta": "VENTA DIRECTA",
        "centro_receptor": "C002", "nombre_centro_receptor": "RECEPTOR X",
        "transportista": 600000001, "nombre_transportista": "TRANSP. EJEMPLO",
        "ruta": "R01", "nombre_ruta": "RUTA EJEMPLO", "numero_transporte": 500000001,
        "distancia": 123.45, "cantidad": 28.5, "fecha": "15/01/2026",
        "despacho_t": 28.5, "departamento": "SC", "traslados_t": 0.0,
        "dia": 15, "mes": 1, "anio": 2026, "grupo_producto": "CEMENTO",
        "tipo_traslado": "-", "producto": "IFCA", "centro_distribucion": "CD SCZ",
        "provincia": "ANDRES IBANEZ", "semana_anio": "S3", "traslados": 0,
        "zona_descarga": "ZONA 1", "cd": "CD1", "localidad": "SANTA CRUZ",
        "distancia_km": 120,
    }
    df = pd.DataFrame([base] * rows)
    df.loc[df.index % 7 == 0, "poblacion"] = "#"
    df.loc[df.index % 11 == 0, "fecha"] = None
    df["documento_venta"] = df["documento_venta"] + df.index
    return df


def _truncate() -> None:
    with get_session(SessionLocal) as session:
        session.execute(text(f"TRUNCATE TABLE [{StgQueryModel.__tablename__}]"))


def run_sqlalchemy(records: list[dict]) -> float:
    _truncate()
    t0 = perf_counter()
    with get_session(SessionLocal) as session:
        session.execute(insert(StgQueryModel), records)
    return perf_counter() - t0


def run_raw(records: list[dict]) -> float:
    _truncate()
    t0 = perf_counter()
    bulk_insert(StgQueryModel, records)
    return perf_counter() - t0


def report(label: str, n: int, secs: float) -> None:
    print(f"  {label:<26} {n:>7} filas en {secs:>7.2f}s  → {n/max(secs,1e-9):>8,.0f} filas/s")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rows", type=int, default=0,
                    help="df sintético de N filas (default: Excel QUERY real)")
    ap.add_argument("--compare", action="store_true",
                    help="correr SQLAlchemy y RAW, mostrar speedup")
    args = ap.parse_args()

    if engine is None:
        print("ERROR: engine no inicializado — revisar DB_* en .env")
        return 1

    if args.rows:
        df = synthetic_df(args.rows)
    else:
        df = load_real_query_df()
        if df is None:
            df = synthetic_df(20000)
    print(f"\nDataset: {len(df)} filas x {len(df.columns)} cols")
    print(f"Destino: {StgQueryModel.__tablename__} (TRUNCATE+INSERT, seguro)\n")

    t0 = perf_counter()
    records = coerce_dataframe_for_model(df, StgQueryModel)
    print(f"coerce a tipos nativos: {perf_counter()-t0:.2f}s "
          f"({len(records)} records)\n")

    if args.compare:
        sa = run_sqlalchemy(records)
        report("A) SQLAlchemy (anterior):", len(records), sa)
        raw = run_raw(records)
        report("B) RAW fast_executemany:", len(records), raw)
        if raw > 0:
            print(f"\n  SPEEDUP B vs A: {sa / raw:.1f}x")
    else:
        raw = run_raw(records)
        report("RAW fast_executemany:", len(records), raw)

    print("\n(la tabla queda cargada con los mismos datos que un run-query)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
