from __future__ import annotations

import logging
from pathlib import Path
import pandas as pd

from itacamba_reportes.core.db.bulk import bulk_insert_df
from itacamba_reportes.core.io.reader import FastExcelReader, ExcelSourceSpec
from itacamba_reportes.core.settings import EnvConfig
from itacamba_reportes.inputs.cartera.models import CustomerStgModel

logger = logging.getLogger(__name__)

CARTERA_SPEC = ExcelSourceSpec(
    name="cartera",
    file_pattern="CARTERA*.xlsx",
    sheet="Q_VCBO_ZSDI_I03_CAD_CLIENTE_000",
    header_row=6,
    subdir="dinamicos",
    column_renames={
        "Cliente": "cliente",
        "Unnamed: 1": "nombre_cliente",
        "Attribute 10": "attribute_10",
        "Población": "poblacion",
        "Barrio": "barrio",
        "Attribute 7": "attribute_7",
        "Attribute 6": "attribute_6",
        "Región": "region",
        "Unnamed: 8": "region_nombre",
        "Grupo de cuentas": "grupo_cuentas",
        "Sector": "sector",
        "Unnamed: 22": "sector_desc",
        "Canal Distribución": "canal_distribucion",
        "Unnamed: 24": "canal_distribucion_desc",
        "Organización de Ventas": "organizacion_ventas",
        "Oficina de Ventas": "oficina_ventas",
        "Grupo de vendedores": "grupo_vendedores",
        "Unnamed: 30": "equipo",
        "Unnamed: 32": "vendedor",
        "Unnamed: 34": "coordinador",
        "Unnamed: 36": "canal",
        "Condición pago": "condicion_pago",
    },
)


def ingest_cartera() -> int:
    reader = FastExcelReader(CARTERA_SPEC, EnvConfig.DATA_PATH)
    df = reader.read_raw()

    # Columna cliente: normalizacion a entero de 64 bits seguro
    if "cliente" in df.columns:
        df["cliente"] = pd.to_numeric(df["cliente"], errors="coerce").fillna(0).astype("int64")

    # Columna orden_origen: preserva la secuencia original de filas del extracto
    df["orden_origen"] = range(1, len(df) + 1)

    model_cols = [c.name for c in CustomerStgModel.__table__.columns if c.name not in ("id", "created_at", "updated_at")]
    valid_cols = [c for c in model_cols if c in df.columns]

    rows = bulk_insert_df(CustomerStgModel, df[valid_cols], truncate_first=True)
    logger.info("Ingesta de Cartera a stg_cartera: %d filas", rows)
    return rows
