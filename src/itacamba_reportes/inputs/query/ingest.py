from __future__ import annotations

import logging
from pathlib import Path
import pandas as pd

from itacamba_reportes.core.db.bulk import bulk_insert_df
from itacamba_reportes.core.io.reader import FastExcelReader, ExcelSourceSpec
from itacamba_reportes.core.settings import EnvConfig
from itacamba_reportes.inputs.query.models import QueryStgModel

logger = logging.getLogger(__name__)

QUERY_SPEC = ExcelSourceSpec(
    name="query",
    file_pattern="QUERY*.xlsx",
    sheet="base",
    header_row=0,
    subdir="dinamicos",
    column_renames={
        "FECHA SALIDA": "fecha_salida",
        "FECHA CREAC. ENTREGA": "fecha_creacion_entrega",
        "Nº PEDIDO": "nro_pedido",
        "N° PEDIDO": "nro_pedido",
        "INCOTERM": "incoterm",
        "CENTRO OR.": "centro_origen",
        "CENTRO DEST.": "centro_destino",
        "COD. MATERIAL": "cod_material",
        "MATERIAL": "material",
        "COD. RUTA": "cod_ruta",
        "NOM. RUTA": "nom_ruta",
        "COD. DEST. MERCANCÍA": "cod_destinatario",
        "COD. DEST. MERCANCIA": "cod_destinatario",
        "DESTINATARIO MERCANC": "nom_destinatario",
        "COD. PAGADOR": "cod_pagador",
        "PAGADOR": "pagador",
        "CANTIDAD TON.": "cantidad_ton",
        "PRECIO PEDIDO": "precio_pedido",
        "UNID. ENT.": "unidad_entrega",
        "NOM. CENTRO OR.": "nom_centro_origen",
        "NOM. CENTRO DEST.": "nom_centro_destino",
        "FECHA FACTURACIÓN": "fecha_facturacion",
        "FECHA FACTURACION": "fecha_facturacion",
        "NRO FACTURA": "nro_factura",
        "TIPO POS. PED.": "tipo_pos_pedido",
        "Documento Referencia": "documento_referencia",
        "Código Ferretero": "codigo_ferretero",
        "Codigo Ferretero": "codigo_ferretero",
    },
)


def ingest_query() -> int:
    reader = FastExcelReader(QUERY_SPEC, EnvConfig.DATA_PATH)
    df = reader.read_raw()

    # Columnas centro_origen / centro_destino: normalizacion de centros SAP
    for col in ("centro_origen", "centro_destino"):
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace("#", "0").str.strip()

    # Coercion de identificadores SAP numericos (BigInteger)
    for col in ("nro_pedido", "cod_material", "cod_destinatario", "cod_pagador", "nro_factura"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("int64")

    # Coercion de metricas de pesaje y precio a float para Numeric(18, 4)
    for col in ("cantidad_ton", "precio_pedido"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    model_cols = [c.name for c in QueryStgModel.__table__.columns if c.name not in ("id", "created_at", "updated_at")]
    valid_cols = [c for c in model_cols if c in df.columns]

    rows = bulk_insert_df(QueryStgModel, df[valid_cols], truncate_first=True)
    logger.info("Ingesta de QUERY ZBCS a stg_query: %d filas", rows)
    return rows
