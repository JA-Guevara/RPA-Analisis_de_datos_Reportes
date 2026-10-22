from __future__ import annotations

import logging
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd

from itacamba_reportes.core.db.bulk import bulk_insert_df
from itacamba_reportes.core.settings import EnvConfig
from itacamba_reportes.inputs.referencias.models import (
    CenterRefModel,
    ChannelRefModel,
    LocalityRefModel,
    MaterialRefModel,
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
)


def resolve_referencias_path() -> Path:
    candidates = [
        EnvConfig.DATA_PATH / "fijos" / "REFERENCIAS.xlsx",
        EnvConfig.DATA_PATH / "REFERENCIAS.xlsx",
        Path(r"C:\Users\joseg_iog5jdg\OneDrive - Tecorp\Documentos\Archivos\fijos\REFERENCIAS.xlsx"),
        EnvConfig.PROJECT_ROOT / "storage" / "input" / "REFERENCIAS.xlsx",
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError("No se encontró REFERENCIAS.xlsx en ninguna ruta configurada")


def ingest_referencias() -> dict[str, int]:
    path = resolve_referencias_path()
    logger.info("Cargando catalogos de REFERENCIAS desde %s", path)

    results = {}
    for sheet_name, model, rename_map in SHEET_CONFIG:
        try:
            df = pd.read_excel(path, sheet_name=sheet_name, engine="calamine")
        except Exception:
            df = pd.read_excel(path, sheet_name=sheet_name, engine="openpyxl")

        norm_map = {}
        for c in df.columns:
            nc = _norm(c)
            if nc in rename_map:
                norm_map[c] = rename_map[nc]

        df = df.rename(columns=norm_map)
        df = df.loc[:, ~df.columns.duplicated()]
        valid_cols = list(dict.fromkeys(c for c in rename_map.values() if c in df.columns))
        df = df[valid_cols].dropna(how="all")

        # Coercion de identificadores numericos a enteros seguros
        if model == WeekRefModel and "dia" in df.columns:
            df["dia"] = pd.to_numeric(df["dia"], errors="coerce").fillna(0).astype(int)
        elif model == MaterialRefModel and "codigo" in df.columns:
            df["codigo"] = pd.to_numeric(df["codigo"], errors="coerce").fillna(0).astype("int64")
        elif model == CenterRefModel and "codigo_sap_cliente" in df.columns:
            df["codigo_sap_cliente"] = pd.to_numeric(df["codigo_sap_cliente"], errors="coerce").fillna(0).astype("int64")

        rows = bulk_insert_df(model, df, truncate_first=True)
        results[model.__tablename__] = rows

    return results
