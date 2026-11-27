from __future__ import annotations

import logging
import unicodedata
from pathlib import Path
from typing import Any
import pandas as pd

from itacamba_reportes.core.db.bulk import bulk_insert_df
from itacamba_reportes.core.db.connection import get_engine
from itacamba_reportes.core.io.reader import (
    MissingColumnsError,
    SheetNotFoundError,
    find_matching_excel_files,
    list_excel_sheets,
    read_excel_sheet,
)
from itacamba_reportes.core.settings import EnvConfig
from itacamba_reportes.inputs.referencias.models import (
    CenterRefModel,
    ChannelRefModel,
    LocalityRefModel,
    MaterialRefModel,
    RouteRefModel,
    SalesTeamRefModel,
    WeekRefModel,
)

logger = logging.getLogger(__name__)


def _norm(text: str) -> str:
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text))
    ascii_text = "".join([c for c in nfkd if not unicodedata.combining(c)])
    return ascii_text.upper().strip()


SHEET_CONFIG = (
    ("Almacen", ChannelRefModel, {
        "DESCRIPCION SAP": "descripcion_sap",
        "CANAL": "canal",
        "SEGMENTO": "segmento",
    }),
    ("Centros", CenterRefModel, {
        "CENTRO": "centro",
        "NOMBRE": "nombre",
        "CENTRO NOMBRE": "nombre",
        "CODIGO SAP CLIENTE": "codigo_sap_cliente",
        "TIPO": "tipo",
    }),
    ("Material", MaterialRefModel, {
        "CODIGO": "codigo",
        "COD": "codigo",
        "DESCRIPCION": "descripcion",
    }),
    ("Equipo", SalesTeamRefModel, {
        "VENDEDOR SAP": "vendedor_sap",
        "VENDEDOR": "vendedor",
        "VENDEDOR OK": "vendedor_ok",
        "GRUPO VENDEDORES": "grupo_vendedores",
        "EQUIPO": "equipo",
        "GERENCIA": "gerencia",
    }),
    ("Localidades", LocalityRefModel, {
        "LOCALIDAD DESPACHO": "localidad_despacho",
        "LOCALIDAD IM": "localidad_im",
    }),
    ("Semanas", WeekRefModel, {
        "DIAS": "dia",
        "DIA": "dia",
        "SEMANA": "semana",
    }),
    ("Rutas", RouteRefModel, {
        "CODIGO RUTA": "codigo_ruta",
        "COD RUTA": "codigo_ruta",
        "RUTA": "ruta",
        "DPTO.": "departamento",
        "DPTO": "departamento",
        "DEPARTAMENTO": "departamento",
        "LOCALIDAD/MUNICIPIO": "localidad",
        "LOCALIDAD": "localidad",
    }),
)


def resolve_referencias_path() -> Path:
    fixed_dir = EnvConfig.require_fixed_inputs_path()
    matches = find_matching_excel_files(fixed_dir, "REFERENCIAS.xlsx")
    if matches:
        return matches[0]
    wildcard_matches = find_matching_excel_files(fixed_dir, "*REFERENCIAS*.xlsx")
    if wildcard_matches:
        return wildcard_matches[0]
    raise FileNotFoundError(
        f"No se encontró REFERENCIAS (.xlsx/.xls) en PATH_INSUMOS_FIJOS ({fixed_dir})"
    )


def ingest_referencias() -> dict[str, int]:
    path = resolve_referencias_path()
    logger.info("Cargando catalogos de REFERENCIAS desde %s", path)

    available_sheets = set(list_excel_sheets(path))
    missing_sheets = [sheet_name for sheet_name, _model, _map in SHEET_CONFIG if sheet_name not in available_sheets]
    if missing_sheets:
        raise SheetNotFoundError(
            f"Faltan hojas requeridas en REFERENCIAS ({missing_sheets}). Disponibles: {list(available_sheets)}"
        )

    # Leer y validar todas las hojas en memoria ANTES de truncar ninguna tabla en BD
    prepared_batches: list[tuple[Any, pd.DataFrame]] = []
    for sheet_name, model, rename_map in SHEET_CONFIG:
        df = read_excel_sheet(path, sheet=sheet_name, header_row=0)

        norm_map = {}
        for c in df.columns:
            nc = _norm(c)
            if nc in rename_map:
                norm_map[c] = rename_map[nc]

        df = df.rename(columns=norm_map)
        df = df.loc[:, ~df.columns.duplicated()]
        valid_cols = list(dict.fromkeys(c for c in rename_map.values() if c in df.columns))
        primary_col = next(iter(rename_map.values()))
        if primary_col not in valid_cols:
            raise MissingColumnsError(
                f"La hoja '{sheet_name}' de REFERENCIAS.xlsx no contiene la columna clave '{primary_col}'."
            )

        df = df[valid_cols].dropna(how="all")
        if df.empty:
            raise ValueError(
                f"La hoja '{sheet_name}' de REFERENCIAS.xlsx no contiene filas válidas; se conservan los catálogos actuales en BD."
            )

        # Coercion de identificadores numericos a enteros seguros
        if model == WeekRefModel and "dia" in df.columns:
            df["dia"] = pd.to_numeric(df["dia"], errors="coerce").fillna(0).astype(int)
        elif model == MaterialRefModel and "codigo" in df.columns:
            df["codigo"] = pd.to_numeric(df["codigo"], errors="coerce").fillna(0).astype("int64")
        elif model == CenterRefModel and "codigo_sap_cliente" in df.columns:
            df["codigo_sap_cliente"] = pd.to_numeric(df["codigo_sap_cliente"], errors="coerce").fillna(0).astype("int64")

        prepared_batches.append((model, df))

    results: dict[str, int] = {}
    eng = get_engine()
    with eng.begin() as conn:
        for model, df in prepared_batches:
            rows = bulk_insert_df(model, df, truncate_first=True, engine=eng, conn=conn)
            results[model.__tablename__] = rows

    return results
