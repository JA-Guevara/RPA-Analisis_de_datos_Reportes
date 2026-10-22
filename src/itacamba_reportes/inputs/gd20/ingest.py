from __future__ import annotations

import logging
from pathlib import Path
import pandas as pd

from itacamba_reportes.core.db.bulk import bulk_insert_df
from itacamba_reportes.core.io.reader import FastExcelReader, ExcelSourceSpec
from itacamba_reportes.core.settings import EnvConfig
from itacamba_reportes.inputs.gd20.models import Gd20StgModel

logger = logging.getLogger(__name__)

GD20_SPEC = ExcelSourceSpec(
    name="gd20",
    file_pattern="GD20*.xlsx",
    sheet="Data",
    header_row=0,
    subdir="dinamicos",
    column_renames={
        "Ejercicio": "ejercicio",
        "Sociedad": "sociedad",
        "Organización ventas": "organizacion_ventas",
        "Centro": "centro",
        "División": "division",
        "Oficina de ventas": "oficina_ventas",
        "Canal distribución": "canal_distribucion",
        "Sector": "sector",
        "Número de cuenta": "numero_cuenta",
        "Centro de beneficio": "centro_beneficio",
        "Material": "material",
        "Unidad medida base": "unidad_medida_base",
        "Período contable": "periodo_contable",
        "Clave de país/región": "clave_pais_region",
        "Región": "region",
        "Población": "poblacion",
        "Grupo de vendedores": "grupo_vendedores",
        "Cliente": "cliente",
        "Emisor Orden": "emisor_orden",
        "Customer number (Bill-to": "customer_bill_to",
        "Customer number (rebate reci": "customer_rebate",
        "Grupo de clientes 2": "grupo_clientes_2",
        "Atributo 6": "atributo_6",
        "Atributo 7": "atributo_7",
        "Atributo 10": "atributo_10",
        "Clase de factura": "clase_factura",
        "Nombre del usuario": "nombre_usuario",
        "Texto": "texto",
        "Nº documento": "numero_documento",
        "N° documento": "numero_documento",
        "Cantidad": "cantidad",
        "Moneda de sociedad": "moneda_sociedad",
        "Fe.contabilización": "fe_contabilizacion",
        "Fe.contabilizacion": "fe_contabilizacion",
        "Fecha de entrada": "fecha_entrada",
        "Fecha valor": "fecha_valor",
        "Documento comercial": "documento_comercial",
        "Hora de entrada": "hora_entrada",
        "Moneda transacción": "moneda_transaccion",
        "Clave Moneda transacción": "clave_moneda_transaccion",
        "Moneda fuerte": "moneda_fuerte",
        "Clave Moneda fuerte": "clave_moneda_fuerte",
        "Nº doc.referencia": "numero_doc_referencia",
        "Nº documento.1": "numero_documento_2",
        "Incoterms": "incoterms",
        "Incoterms (parte 2)": "incoterms_parte_2",
        "Incoterms, parte 2": "incoterms_parte_2",
        "Clase de documento": "clase_documento",
        "Cond. pago": "cond_pago",
        "Días 1": "dias_1",
        "Nº de transporte": "numero_transporte",
        "E": "e",
    },
)


def ingest_gd20() -> int:
    reader = FastExcelReader(GD20_SPEC, EnvConfig.DATA_PATH)
    df = reader.read_raw()

    # Coercion de identificadores SAP numericos (BigInteger)
    for col in (
        "cliente", "emisor_orden", "customer_bill_to", "customer_rebate",
        "numero_documento", "documento_comercial", "numero_doc_referencia",
        "numero_documento_2", "numero_transporte", "numero_cuenta", "material",
    ):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("int64")

    # Coercion de importes monetarios y cantidades a float para Numeric(18, 4)
    for col in ("cantidad", "moneda_sociedad", "moneda_transaccion", "moneda_fuerte"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    model_cols = [c.name for c in Gd20StgModel.__table__.columns if c.name not in ("id", "created_at", "updated_at")]
    valid_cols = [c for c in model_cols if c in df.columns]

    rows = bulk_insert_df(Gd20StgModel, df[valid_cols], truncate_first=True)
    logger.info("Ingesta GD20 a stg_gd20: %d filas", rows)
    return rows
