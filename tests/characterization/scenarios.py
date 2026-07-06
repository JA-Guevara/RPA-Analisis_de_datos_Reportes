"""Escenarios de caracterización — capturan el comportamiento observable
del código que el refactor reorganiza, para garantizar equivalencia exacta.

Cada escenario produce una estructura JSON-serializable determinística.
`capture_goldens.py --write` la persiste en golden/ usando el código
vigente; `test_goldens.py` la recomputa y compara. Si el refactor cambia
cualquier salida, el test lo detecta.

NewWorld encapsula los imports del paquete (historicamente existia un
OldWorld pre-refactor, eliminado en Fase 2 del plan 2026-07-06).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIGS_DIR = PROJECT_ROOT / "assets" / "configs"


# ──────────────────────────────────────────────────────────────────────
# Serialización determinística de DataFrames
# ──────────────────────────────────────────────────────────────────────

def df_snapshot(df: pd.DataFrame) -> dict[str, Any]:
    def cell(v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, float) and np.isnan(v):
            return "<NaN>"
        if pd.api.types.is_scalar(v) and pd.isna(v):
            return "<NA>"
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, (np.floating,)):
            return float(v)
        if isinstance(v, pd.Timestamp):
            return v.isoformat()
        return v if isinstance(v, (int, float, bool, str)) else str(v)

    return {
        "columns": [str(c) for c in df.columns],
        "dtypes": {str(c): str(t) for c, t in df.dtypes.items()},
        "rows": [[cell(v) for v in row] for row in df.itertuples(index=False, name=None)],
    }


def rows_snapshot(rows: list[dict]) -> list[dict]:
    def cell(v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, float) and np.isnan(v):
            return "<NaN>"
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, (np.floating,)):
            return float(v)
        return v if isinstance(v, (int, float, bool, str)) else str(v)

    return [{k: cell(v) for k, v in r.items()} for r in rows]


# ──────────────────────────────────────────────────────────────────────
# Worlds: viejo (pre-refactor) y nuevo (post-refactor)
# ──────────────────────────────────────────────────────────────────────

class NewWorld:
    name = "new"

    def load_cartera_spec(self):
        from itacamba_reportes.config.yaml_loader import YamlDatasetLoader
        return YamlDatasetLoader(CONFIGS_DIR).load("cartera")

    def load_config(self, dataset: str) -> dict:
        from itacamba_reportes.config.yaml_loader import load_pipeline_config
        return load_pipeline_config(CONFIGS_DIR, dataset)

    def cartera_mapping(self, df, spec):
        from itacamba_reportes.transforms.common import apply_column_mapping
        return apply_column_mapping(
            df, rename=spec.to_int_model.rename, drop=spec.to_int_model.drop,
            dataset="cartera",
        )

    def query_mapping(self, df, config):
        from itacamba_reportes.reportes.query.mapping import apply_query_mapping
        return apply_query_mapping(df, config)

    def gd20_mapping(self, df, config):
        from itacamba_reportes.reportes.gd20_ventas_bi.mapping import (
            apply_gd20_mapping,
        )
        return apply_gd20_mapping(df, config)

    def despacho_bi_mapping(self, df, config):
        from itacamba_reportes.reportes.despacho_bi.mapping import (
            apply_despacho_bi_mapping,
        )
        return apply_despacho_bi_mapping(df, config)

    def normalize_cartera(self, df, spec):
        from itacamba_reportes.reportes.cartera.normalizacion import (
            NormalizeCarteraFromSpec,
        )
        return NormalizeCarteraFromSpec(spec).execute(df)

    def cartera_rules(self, spec):
        from itacamba_reportes.reportes.cartera.reglas import (
            ApplyDonationsFromSpecRule,
            ValidateRegionFromLookupRule,
        )
        rules = []
        if spec.lookups.donaciones is not None:
            rules.append(ApplyDonationsFromSpecRule(
                lookup=spec.lookups.donaciones, sap_tokens=spec.sap_tokens))
        if spec.lookups.regiones_validas is not None:
            rules.append(ValidateRegionFromLookupRule(
                lookup=spec.lookups.regiones_validas, strict=False))
        return rules

    def clean_reference_rows(self, catalog_key: str, df) -> list[dict]:
        from itacamba_reportes.persistence.repositories.reference_loader import (
            CATALOGS,
            df_to_clean_rows,
        )
        catalog = next(c for c in CATALOGS if c.key == catalog_key)
        return df_to_clean_rows(df, catalog.model)

    def make_reader(self, source_kwargs: dict, data_path: Path):
        from itacamba_reportes.ingestion.excel_source import ExcelSource
        from itacamba_reportes.ingestion.excel_reader import ExcelReader
        return ExcelReader(source=ExcelSource(**source_kwargs), data_path=data_path)

    def excel_sources_snapshot(self) -> dict:
        from itacamba_reportes.config.sources import load_all_excel_sources
        sources = load_all_excel_sources(CONFIGS_DIR)
        return {
            name: _source_to_dict(src) for name, src in sorted(sources.items())
        }

    def state_tracker(self, path: Path):
        from itacamba_reportes.pipelines.file_state import (
            FileFingerprint,
            FileStateTracker,
            StateEntry,
        )
        return FileStateTracker(path), FileFingerprint, StateEntry


def _source_to_dict(src) -> dict:
    return {
        "name": src.name,
        "file_pattern": src.file_pattern,
        "subdir": src.subdir,
        "sheet": src.sheet,
        "header_row": src.header_row,
        "metadata_rows_to_skip": src.metadata_rows_to_skip,
        "column_renames": dict(src.column_renames),
        "dedupe_on": list(src.dedupe_on),
        "dedupe_case_insensitive": bool(getattr(src, "dedupe_case_insensitive", False)),
    }


def get_world():
    # Post-refactor 2026-06: existe un solo mundo. La clase conserva el
    # nombre NewWorld para no invalidar goldens/documentacion previa.
    return NewWorld()


# ──────────────────────────────────────────────────────────────────────
# Inputs sintéticos (determinísticos)
# ──────────────────────────────────────────────────────────────────────

def _mk_mapping_input(rename_keys: list[str], drop_keys: list[str]) -> pd.DataFrame:
    """df con la mayoría de cols del rename, las de drop, 2 extra y 2 faltantes."""
    present = rename_keys[:-2] if len(rename_keys) > 2 else rename_keys
    cols = list(dict.fromkeys(present + drop_keys + ["col_extra_1", "col_extra_2"]))
    data = {c: [f"{c}_v{i}" for i in range(4)] for c in cols}
    return pd.DataFrame(data)


def _mk_query_mapping_input() -> pd.DataFrame:
    cols = ["centro_proveedor", "sucursal", "material", "cantidad",
            "xx", "xx2", "xx3", "xx4", "nota_manual"]
    return pd.DataFrame({c: [f"{c}_{i}" for i in range(3)] for c in cols})


def _mk_gd20_mapping_input() -> pd.DataFrame:
    cols = ["cliente", "emisor_orden", "customer_rebate", "region",
            "poblacion", "clave_pais_region", "cantidad", "texto"]
    return pd.DataFrame({c: [f"{c}_{i}" for i in range(3)] for c in cols})


def _mk_despacho_bi_input(source_columns: list[str]) -> pd.DataFrame:
    present = list(source_columns[:-3]) + ["telefono_1", "placa", "otra_col"]
    return pd.DataFrame({c: [f"{c}_{i}" for i in range(3)] for c in present})


REFERENCE_DIRTY_INPUTS: dict[str, pd.DataFrame] = {
    "almacen": pd.DataFrame({
        "descripcion_sap": ["  ALMACEN UNO ", "ALM DOS", "#", "ALM TRES", None],
        "segmento": ["Seg A", "  ", "N/A", "Sin asignar", "Seg E"],
        "canal": ["C1", np.nan, "null", " C4 ", "#REF!"],
        "columna_basura": ["x", "y", "z", "w", "v"],
    }),
    "centro": pd.DataFrame({
        "centro": [" C001 ", "C002", "--", None, "C005"],
        "codigo_sap_cliente": [1001, 1002.0, np.nan, 1004, 1005],
        "tipo": ["VENTA DIRECTA", " VENTA INDIRECTA ", "NA", "None", "V"],
    }),
    "equipo": pd.DataFrame({
        "grupo_vendedores": ["G1 ", "G2", "#", "G4", "G5"],
        "vendedor_sap": ["V SAP 1", "  V SAP 2", "nan", None, "V5"],
        "vendedor": ["Juan", "Maria ", "-", "Pedro", "Not assigned"],
        "vendedor_ok": ["JUAN", "MARIA", "PEDRO", "", "LUIS"],
        "equipo": ["EQ1", "EQ2", "EQ3", "EQ4", None],
        "gerencia": ["GER A", "GER B", "GER C", "GER D", "GER E"],
    }),
    "localidad": pd.DataFrame({
        "localidad_despacho": ["SAN MATIAS", " puerto suarez ", "#N/A", "OTRA", None],
        "localidad_im": ["SM", "PS", "X", " sin asignar ", "Y"],
    }),
    "material": pd.DataFrame({
        "codigo": [10, 20.0, np.nan, 40, 50],
        "descripcion": [" CEMENTO X ", "CEMENTO Y", "N/A", None, "CAL Z"],
    }),
    "semana": pd.DataFrame({
        "dia": [1, 2, 3, np.nan, 5],
        "semana": ["S1", " S1 ", "#", "S2", None],
    }),
}


def _mk_reader_input() -> pd.DataFrame:
    return pd.DataFrame({
        "KEY": [" A ", "a", "B", "#", None, "C", "C", "N/A", "D "],
        "VAL": list("123456789"),
        "OTRA": ["x"] * 9,
    })


def _mk_cartera_raw_input(spec) -> pd.DataFrame:
    """Simula el df crudo de cartera tras el reader (antes de rename posicional).

    Columnas en el orden del Excel real (= orden de to_int_model.rename).
    Las posiciones cubiertas por rename_by_position llevan un header dummy
    que el normalize debe corregir. Los datos ejercitan: dtypes (Int64,
    datetime dayfirst), transforms (uppercase+replace de Column9), regla de
    donaciones (Sin asignar/Not assigned) y validación de regiones.
    """
    headers = list(spec.to_int_model.rename.keys())
    donation_names: list[str] = []
    if spec.lookups.donaciones is not None:
        donation_names = [i.cliente_nombre for i in spec.lookups.donaciones.items][:3]
    regiones = list(spec.lookups.regiones_validas.items[:3]) if spec.lookups.regiones_validas else ["SC"]
    n = 8

    def values_for(header: str, snake: str) -> list:
        if snake == "cliente":
            return [str(100000 + i) for i in range(n)]
        if snake == "nombre_cliente":
            return (donation_names + [f"CLIENTE {i}" for i in range(n)])[:n]
        if snake == "region":
            return (regiones + ["ZZ", "#", None] + regiones + regiones)[:n]
        if snake == "region_nombre":
            return ["potosí", "BO/PT", "santa cruz", "POTOSÍ", "#",
                    "la paz", "beni", "tarija"][:n]
        if snake == "fecha_inclusion":
            return ["01/02/2024", "15/03/2024", "31/12/2023", "#", None,
                    "10/10/2025", "05/05/2024", "20/06/2024"][:n]
        if snake == "contador":
            return ["1", "2", "3", "#", None, "6", "7", "8"][:n]
        if snake in ("vendedor", "coordinador"):
            return ["Sin asignar", "Not assigned", "JUAN PEREZ", "Sin asignar",
                    "MARIA LOPEZ", "#", "Not assigned", "PEDRO GOMEZ"][:n]
        return [f"{snake}_{i}" if (i + len(snake)) % 7 else "#" for i in range(n)]

    data: dict[str, list] = {}
    rename_map = spec.to_int_model.rename
    for pos, header in enumerate(headers):
        col_name = f"RAW_{pos}" if pos in spec.rename_by_position else header
        data[col_name] = values_for(header, rename_map[header])
    return pd.DataFrame(data)


# ──────────────────────────────────────────────────────────────────────
# Escenarios
# ──────────────────────────────────────────────────────────────────────

def compute_scenarios(world) -> dict[str, Any]:
    out: dict[str, Any] = {}

    # 1 — Config: snapshot de todos los ExcelSource (clave de la migración a YAML)
    out["excel_sources"] = world.excel_sources_snapshot()

    # 2 — Mappings por dataset
    spec = world.load_cartera_spec()
    cart_in = _mk_mapping_input(
        list(spec.to_int_model.rename.keys()), list(spec.to_int_model.drop),
    )
    out["mapping_cartera"] = df_snapshot(world.cartera_mapping(cart_in.copy(), spec))

    q_cfg = world.load_config("query")
    out["mapping_query_cfg"] = df_snapshot(world.query_mapping(_mk_query_mapping_input(), q_cfg))
    out["mapping_query_none"] = df_snapshot(world.query_mapping(_mk_query_mapping_input(), None))

    from itacamba_reportes.reportes.gd20_ventas_bi import load_config as _g20_cfg
    g_cfg = _g20_cfg()
    out["mapping_gd20_cfg"] = df_snapshot(world.gd20_mapping(_mk_gd20_mapping_input(), g_cfg))
    out["mapping_gd20_none"] = df_snapshot(world.gd20_mapping(_mk_gd20_mapping_input(), None))

    from itacamba_reportes.reportes.despacho_bi import load_config as _dbi_cfg
    d_cfg = _dbi_cfg()
    dbi_cols = d_cfg.get("source_columns") or []
    out["mapping_despacho_bi_cfg"] = df_snapshot(
        world.despacho_bi_mapping(_mk_despacho_bi_input(list(dbi_cols) or
                                  ["centro_proveedor", "sucursal", "material"]), d_cfg))
    out["mapping_despacho_bi_none"] = df_snapshot(
        world.despacho_bi_mapping(_mk_despacho_bi_input(
            ["centro_proveedor", "sucursal", "material", "cantidad", "fecha"]), None))

    # 3 — Limpieza de referencias (NULL_TOKENS, strip, NaN→None)
    for key, dirty in REFERENCE_DIRTY_INPUTS.items():
        out[f"reference_clean_{key}"] = rows_snapshot(
            world.clean_reference_rows(key, dirty.copy()))

    # 4 — Operaciones del reader (skip/renames/null-key/dedupe)
    src_kw = dict(
        name="synthetic", file_pattern="X*.xlsx", subdir=None, sheet="S",
        header_row=0, metadata_rows_to_skip=2,
        column_renames={"KEY": "key", "VAL": "val"},
        dedupe_on=("key",),
    )
    rdr = world.make_reader(src_kw, Path("/tmp"))
    df_r = _mk_reader_input()
    df_r = rdr._apply_metadata_skip(df_r)
    df_r = rdr._apply_column_renames(df_r)
    df_r = rdr._drop_rows_with_null_key(df_r)
    out["reader_pipeline_cs"] = df_snapshot(rdr._apply_dedupe(df_r.copy()))

    src_kw_ci = dict(src_kw, dedupe_case_insensitive=True, metadata_rows_to_skip=0)
    rdr_ci = world.make_reader(src_kw_ci, Path("/tmp"))
    df_r2 = _mk_reader_input()
    df_r2 = rdr_ci._apply_column_renames(df_r2)
    df_r2 = rdr_ci._drop_rows_with_null_key(df_r2)
    out["reader_pipeline_ci"] = df_snapshot(rdr_ci._apply_dedupe(df_r2.copy()))

    # 5 — Normalize + rules de cartera (config-driven, YAML real)
    raw = _mk_cartera_raw_input(spec)
    normalized = world.normalize_cartera(raw.copy(), spec)
    out["cartera_normalize"] = df_snapshot(normalized)
    mapped = world.cartera_mapping(normalized.copy(), spec)
    ruled = mapped.copy()
    for rule in world.cartera_rules(spec):
        ruled = rule.apply(ruled)
    out["cartera_rules"] = df_snapshot(ruled)

    # 6 — Formato del state JSON (compatibilidad de pipeline_state.json)
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        sp = Path(td) / "state.json"
        tracker, FP, SE = world.state_tracker(sp)
        fp = FP(path="C:/x/CARTERA.xlsx", mtime=1718000000.0, size=12345)
        tracker.save("cartera", SE(
            fingerprint=fp, last_run_at="2026-06-12T10:00:00",
            rows_loaded={"stg_cartera": 10, "int_cartera": 9},
        ))
        out["state_json"] = json.loads(sp.read_text(encoding="utf-8"))
        loaded = tracker.get("cartera")
        out["state_roundtrip"] = {
            "rows_loaded": loaded.rows_loaded,
            "changed_same": tracker.has_changed(fp, loaded.fingerprint),
            "changed_diff": tracker.has_changed(
                FP(path="C:/x/CARTERA.xlsx", mtime=1718000001.0, size=12345),
                loaded.fingerprint,
            ),
        }

    return out
