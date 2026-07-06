"""Simulador de calibración GD20/VENTAS BI — reproduce en memoria el
enriquecimiento (mapping + normalize + rules) y los HASHES SCD2 de
int_gd20, sin SQL Server.

El gate de la Fase 4 del plan: tras migrar gd20 a catálogo declarativo,
int_gd20 y sus source_hash/derived_hash deben ser IDÉNTICOS (si un hash
cambiara, el histórico int_ventas_bi versionaría filas falsamente).

Uso:
    python tools/calibracion/simular_gd20.py [--data RUTA] [--out RUTA]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "tools" / "calibracion"))

CONFIGS = PROJECT_ROOT / "assets" / "configs"


def build_stg_query(data: Path) -> pd.DataFrame:
    """stg_query como la ve gd20: raw completo renombrado (sin filtro mes)."""
    from itacamba_reportes.config.sources import load_all_excel_sources
    from itacamba_reportes.ingestion.excel_reader import ExcelReader
    from itacamba_reportes.persistence.models.stg.stg_query_model import StgQueryModel
    from simular_despacho import as_table

    sources = load_all_excel_sources(CONFIGS)
    df = ExcelReader(source=sources["query"], data_path=data).read()
    df = as_table(df, StgQueryModel)
    print(f"  stg_query: {len(df)} filas x {len(df.columns)} cols")
    return df


def build_int_gd20(data: Path, cartera: pd.DataFrame,
                   refs: dict[str, pd.DataFrame],
                   stg_query: pd.DataFrame) -> pd.DataFrame:
    from itacamba_reportes.ingestion.excel_reader import ExcelReader
    from itacamba_reportes.persistence.models.int.gd20_model import Gd20IntModel
    from itacamba_reportes.persistence.row_hasher import add_hashes_to_dataframe
    from simular_despacho import as_table

    from itacamba_reportes.config.sources import excel_source_from_cfg
    from itacamba_reportes.reportes.gd20_ventas_bi import load_config
    from itacamba_reportes.reportes.gd20_ventas_bi.enriquecimiento import enrich_gd20
    from itacamba_reportes.reportes.gd20_ventas_bi.mapping import apply_gd20_mapping

    cfg = load_config()
    source = excel_source_from_cfg("gd20", cfg["source"])
    df_raw = ExcelReader(source=source, data_path=data).read()
    print(f"  GD20 raw: {len(df_raw)} filas x {len(df_raw.columns)} cols")

    df = apply_gd20_mapping(df_raw, cfg)
    df = enrich_gd20(
        df, cfg,
        cartera_df=cartera, equipo_df=refs["equipo"],
        almacen_df=refs["almacen"], material_df=refs["material"],
        centro_df=refs["centro"], query_df=stg_query,
        localidad_df=refs["localidad"],
    )
    df = as_table(df, Gd20IntModel)
    df = add_hashes_to_dataframe(df)
    print(f"  int_gd20 (+hashes): {len(df)} filas x {len(df.columns)} cols")
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=None)
    parser.add_argument("--out", type=Path,
                        default=PROJECT_ROOT / "storage" / "calibracion")
    args = parser.parse_args()

    if args.data is None:
        from itacamba_reportes.config.env_config import EnvConfig
        data = EnvConfig.DATA_PATH
    else:
        data = args.data
    if not data.exists():
        raise SystemExit(f"Carpeta de datos no existe: {data}")
    args.out.mkdir(parents=True, exist_ok=True)

    from simular_despacho import build_cartera, build_references

    print("== REFERENCIAS =="); refs = build_references(data)
    print("== CARTERA =="); cartera = build_cartera(data)
    print("== STG QUERY =="); stg_query = build_stg_query(data)
    print("== GD20 -> int_gd20 + hashes ==")
    int_gd20 = build_int_gd20(data, cartera, refs, stg_query)

    int_gd20.to_pickle(args.out / "int_gd20_hashed.pkl")
    print(f"\nSimulación GD20 OK -> {args.out}")


if __name__ == "__main__":
    main()
