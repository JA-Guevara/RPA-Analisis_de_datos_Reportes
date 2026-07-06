"""Simulador de calibración DESPACHO — reproduce en memoria lo que generan
los pipelines (fase 1 int_query, fase 2 int_despacho_bi, int_despacho_mes)
usando el código real del proyecto, SIN SQL Server.

Simula el roundtrip por BD reindexando cada DataFrame al set de columnas
del modelo SQLAlchemy (las cols no pobladas quedan NA, igual que en BD).

Uso:
    python tools/calibracion/simular_despacho.py [--data RUTA] [--out RUTA]

    --data  Carpeta con dinamicos/ y fijos/ (default: DATA_PATH del .env)
    --out   Carpeta de salida de los .pkl   (default: storage/calibracion)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

CONFIGS = PROJECT_ROOT / "assets" / "configs"


def model_cols(model) -> list[str]:
    skip = {"id", "created_at", "updated_at"}
    return [c.name for c in model.__table__.columns if c.name not in skip]


def as_table(df: pd.DataFrame, model) -> pd.DataFrame:
    """Simula pd.read_sql_table: solo cols del modelo, faltantes = NA."""
    cols = model_cols(model)
    out = df.copy()
    for c in cols:
        if c not in out.columns:
            out[c] = pd.NA
    return out[cols]


def build_references(data: Path) -> dict[str, pd.DataFrame]:
    import yaml

    from itacamba_reportes.ingestion.excel_reader import ExcelReader
    from itacamba_reportes.ingestion.excel_source import ExcelSource
    from itacamba_reportes.persistence.repositories.reference_loader import (
        CATALOGS,
        df_to_clean_rows,
    )

    cfg = yaml.safe_load((CONFIGS / "references.yaml").read_text(encoding="utf-8"))
    out: dict[str, pd.DataFrame] = {}
    for cat in CATALOGS:
        c = cfg["catalogs"][cat.key]
        src = ExcelSource(
            name=f"ref_{cat.key}",
            file_pattern=c["file_pattern"],
            subdir=c.get("subdir"),
            sheet=c["sheet"],
            header_row=c.get("header_row", 0),
            metadata_rows_to_skip=c.get("metadata_rows_to_skip", 0),
            column_renames=c.get("column_renames", {}),
            dedupe_on=tuple(c.get("dedupe_on", []) or []),
            dedupe_case_insensitive=bool(c.get("dedupe_case_insensitive", False)),
        )
        df = ExcelReader(source=src, data_path=data).read()
        rows = df_to_clean_rows(df, cat.model)
        out[cat.key] = pd.DataFrame(rows) if rows else pd.DataFrame()
        print(f"  int_ref_{cat.key}: {len(out[cat.key])} filas")
    return out


def build_cartera(data: Path) -> pd.DataFrame:
    from itacamba_reportes.config.yaml_loader import YamlDatasetLoader
    from itacamba_reportes.ingestion.excel_reader import ExcelReader
    from itacamba_reportes.ingestion.excel_source import ExcelSource
    from itacamba_reportes.transforms.cartera_business_rules import (
        ApplyDonationsFromSpecRule,
        ValidateRegionFromLookupRule,
    )
    from itacamba_reportes.transforms.cartera_normalize import NormalizeCarteraFromSpec
    from itacamba_reportes.transforms.common import apply_column_mapping

    spec = YamlDatasetLoader(CONFIGS).load("cartera")
    s = spec.source
    src = ExcelSource(
        name="cartera", file_pattern=s.file_pattern, subdir=s.subdir,
        sheet=s.sheet, header_row=s.header_row,
        metadata_rows_to_skip=s.metadata_rows_to_skip,
        column_renames={}, dedupe_on=(),
    )
    raw = ExcelReader(source=src, data_path=data).read()
    df = NormalizeCarteraFromSpec(spec).execute(raw)
    df = apply_column_mapping(
        df, rename=spec.to_int_model.rename, drop=spec.to_int_model.drop,
        dataset="cartera",
    )
    rules = []
    if spec.lookups.donaciones is not None:
        rules.append(ApplyDonationsFromSpecRule(
            lookup=spec.lookups.donaciones, sap_tokens=spec.sap_tokens))
    if spec.lookups.regiones_validas is not None:
        rules.append(ValidateRegionFromLookupRule(
            lookup=spec.lookups.regiones_validas, strict=False))
    for r in rules:
        df = r.apply(df)
    print(f"  int_cartera: {len(df)} filas x {len(df.columns)} cols")
    return df


def build_int_query(data: Path) -> pd.DataFrame:
    from itacamba_reportes.config.sources import load_all_excel_sources
    from itacamba_reportes.config.yaml_loader import load_pipeline_config
    from itacamba_reportes.ingestion.excel_reader import ExcelReader
    from itacamba_reportes.persistence.models.int.query_model import IntQueryModel
    from itacamba_reportes.transforms.query_business_rules import (
        QueryBusinessRulesUseCase,
    )
    from itacamba_reportes.transforms.query_mapping import apply_query_mapping
    from itacamba_reportes.transforms.query_normalize import QueryNormalizeUseCase

    sources = load_all_excel_sources(CONFIGS)
    reader = ExcelReader(source=sources["query"], data_path=data)
    cfg = load_pipeline_config(CONFIGS, "query")

    df_raw = reader.read()
    print(f"  QUERY raw: {len(df_raw)} filas x {len(df_raw.columns)} cols")
    df = apply_query_mapping(df_raw, cfg)
    df = QueryNormalizeUseCase(config=cfg).execute(df)
    df = QueryBusinessRulesUseCase(config=cfg).execute(df)
    df = as_table(df, IntQueryModel)
    print(f"  int_query: {len(df)} filas x {len(df.columns)} cols")
    return df


def build_despacho_bi(int_query: pd.DataFrame, cartera: pd.DataFrame,
                      refs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    from itacamba_reportes.persistence.models.int.despacho_bi_model import (
        DespachoBiIntModel,
    )
    from itacamba_reportes.reportes.despacho_bi import load_catalog, load_config
    from itacamba_reportes.reportes.despacho_bi.mapping import (
        apply_despacho_bi_mapping,
    )
    from itacamba_reportes.transforms.column_engine import ColumnEngine

    cfg = load_config()
    catalog = load_catalog()

    # Mismos nombres de tabla que usa el pipeline real en _load_lookups()
    lookups = {
        "int_cartera": cartera,
        "int_ref_equipo": refs["equipo"],
        "int_ref_almacen": refs["almacen"],
        "int_ref_localidad": refs["localidad"],
        "int_ref_centro": refs["centro"],
        "int_ref_semana": refs["semana"],
    }
    df = apply_despacho_bi_mapping(int_query, cfg)
    df = ColumnEngine(lookups=lookups).apply(df, catalog)
    df = as_table(df, DespachoBiIntModel)
    print(f"  int_despacho_bi: {len(df)} filas x {len(df.columns)} cols")
    return df


def build_despacho_mes(despacho_bi: pd.DataFrame, cartera: pd.DataFrame,
                       refs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    from itacamba_reportes.persistence.models.int.despacho_mes_model import (
        DespachoMesIntModel,
    )
    from itacamba_reportes.reportes.despacho_mes import (
        load_catalog as load_mes_catalog,
        load_config as load_mes_config,
    )
    from itacamba_reportes.reportes.despacho_mes.agregacion import (
        DespachoMesAggregateUseCase,
    )
    from itacamba_reportes.reportes.despacho_mes.pipeline import DespachoMesPipeline
    from itacamba_reportes.reportes.despacho_mes.reglas import (
        DespachoMesBusinessRulesUseCase,
    )
    from itacamba_reportes.transforms.column_engine import ColumnEngine

    cfg = load_mes_config()
    catalog = load_mes_catalog()

    # Filtro de mes objetivo: misma lógica del pipeline, sin BD.
    pipe = DespachoMesPipeline.__new__(DespachoMesPipeline)
    object.__setattr__(pipe, "config", cfg)
    target = pipe._resolve_target_month(despacho_bi)
    df = despacho_bi
    if target is not None:
        anio = pd.to_numeric(df["anio"], errors="coerce")
        mes = pd.to_numeric(df["mes"], errors="coerce")
        df = df.loc[(anio == target[0]) & (mes == target[1])].reset_index(drop=True)
    print(f"  filtro mes {target}: {len(df)} filas")

    df = DespachoMesAggregateUseCase(config=cfg).execute(df)
    lookups_mes = {
        "int_cartera": cartera,
        "int_ref_almacen": refs["almacen"],
        "int_ref_semana": refs["semana"],
    }
    df = ColumnEngine(lookups=lookups_mes).apply(df, catalog)
    df = DespachoMesBusinessRulesUseCase(config=cfg).execute(df)
    df = as_table(df, DespachoMesIntModel)
    print(f"  int_despacho_mes: {len(df)} filas x {len(df.columns)} cols")
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=None,
                        help="Carpeta de datos (default: DATA_PATH del .env)")
    parser.add_argument("--out", type=Path,
                        default=PROJECT_ROOT / "storage" / "calibracion",
                        help="Carpeta de salida")
    args = parser.parse_args()

    if args.data is None:
        from itacamba_reportes.config.env_config import EnvConfig
        data = EnvConfig.DATA_PATH
    else:
        data = args.data
    if not data.exists():
        raise SystemExit(f"Carpeta de datos no existe: {data}")

    args.out.mkdir(parents=True, exist_ok=True)

    print("== REFERENCIAS ==")
    refs = build_references(data)
    print("== CARTERA ==")
    cartera = build_cartera(data)
    print("== QUERY (fase 1) ==")
    int_query = build_int_query(data)
    print("== DESPACHO BI (fase 2) ==")
    despacho_bi = build_despacho_bi(int_query, cartera, refs)
    print("== DESPACHO MES ==")
    despacho_mes = build_despacho_mes(despacho_bi, cartera, refs)

    for name, df in [
        ("int_query", int_query), ("int_cartera", cartera),
        ("int_despacho_bi", despacho_bi), ("int_despacho_mes", despacho_mes),
    ]:
        df.to_pickle(args.out / f"{name}.pkl")
    for key, df in refs.items():
        df.to_pickle(args.out / f"ref_{key}.pkl")
    print(f"\nSimulación OK -> {args.out}")


if __name__ == "__main__":
    main()
