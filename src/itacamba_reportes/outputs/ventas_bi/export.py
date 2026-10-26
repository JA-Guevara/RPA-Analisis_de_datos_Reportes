from __future__ import annotations

import logging
from pathlib import Path
import pandas as pd
from sqlalchemy import text

from itacamba_reportes.core.db.connection import engine
from itacamba_reportes.core.io.exporter import ExcelReportExporter
from itacamba_reportes.core.settings import EnvConfig

logger = logging.getLogger(__name__)

HEADER_MAPPING = {
    "ejercicio": "Ejercicio",
    "sociedad": "Sociedad",
    "organizacion_ventas": "Organización ventas",
    "centro": "Centro",
    "division": "División",
    "oficina_ventas": "Oficina de ventas",
    "canal_distribucion": "Canal distribución",
    "sector": "Sector",
    "numero_cuenta": "Número de cuenta",
    "centro_beneficio": "Centro de beneficio",
    "material": "Material",
    "unidad_medida_base": "Unidad medida base",
    "periodo_contable": "Período contable",
    "clave_pais": "Clave de país",
    "region_sap": "Región SAP",
    "poblacion_sap": "Población SAP",
    "grupo_vendedores": "Grupo de vendedores",
    "pagador": "Pagador/ Responsable de Pago",
    "emisor_solicitante": "Emisor Orden/ Solicitante",
    "customer_bill_to": "Customer number (Bill-to",
    "destinatario": "Destinatario",
    "grupo_clientes_2": "Grupo de clientes 2",
    "atributo_6": "Atributo 6",
    "atributo_7": "Atributo 7",
    "atributo_10": "Atributo 10",
    "clase_factura": "Clase de factura",
    "nombre_usuario": "Nombre del usuario",
    "texto": "Texto",
    "numero_documento": "Nº documento",
    "cantidad": "Cantidad",
    "moneda_sociedad": "Moneda de sociedad",
    "fe_contabilizacion": "Fe.contabilización",
    "fecha_entrada": "Fecha de entrada",
    "fecha_valor": "Fecha valor",
    "documento_comercial": "Documento comercial",
    "hora_entrada": "Hora de entrada",
    "moneda_transaccion": "Moneda transacción",
    "clave_moneda_transaccion": "Clave Moneda transacción",
    "moneda_fuerte": "Moneda fuerte",
    "clave_moneda_fuerte": "Clave Moneda fuerte",
    "numero_doc_referencia": "Nº doc.referencia",
    "numero_documento_2": "Nº documento2",
    "incoterms": "Incoterms",
    "incoterms_parte_2": "Incoterms, parte 2",
    "clase_documento": "Clase de documento",
    "cond_pago": "Cond. Pago",
    "dias_1": "Días 1",
    "numero_transporte": "Nº de transporte",
    "e": "E",
    "tipo_embalaje": "TIPO DE EMBALAJE",
    "nombre_producto": "NOMBRE DE PRODUCTO",
    "volumen_toneladas": "VOLUMEN TONELADAS",
    "nombre_pagador": "NOMBRE PAGADOR",
    "nombre_solicitante": "NOMBRE SOLICITANTE",
    "vendedor_sap": "VENDEDOR SAP",
    "vendedor": "VENDEDOR",
    "vendedor_ok": "VENDEDOR OK",
    "gerencia": "GERENCIA",
    "equipo": "EQUIPO",
    "canal": "CANAL",
    "sub_canal": "SUB CANAL",
    "dia": "DIA",
    "mes": "MES",
    "anio": "AÑO",
    "tipo_venta": "TIPO DE VENTA",
    "localidad": "LOCALIDAD",
    "provincia": "PROVINCIA",
    "dpto": "DPTO",
    "region_m": "REGION M",
    "ingreso_bruto": "INGRESO BRUTO",
    "dpto_pagador": "DPTO PAGADOR",
    "localidad_pagador": "LOCALIDAD PAGADOR",
    "codigo_cliente": "CÓDIGO CLIENTE",
    "bonificaciones": "BONIFICACIONES",
    "centro_distribucion": "CENTRO DE DISTRIBUCIÓN",
    "zona_entrega": "ZONA DE ENTREGA",
    "nombre_destinatario": "NOMBRE DESTINATARIO",
}


def export_ventas_bi() -> Path:
    logger.info("Exportando VENTAS BI a Excel...")
    query = """
    SELECT 
        ejercicio, sociedad, organizacion_ventas, centro, division, oficina_ventas,
        canal_distribucion, sector, numero_cuenta, centro_beneficio, material,
        unidad_medida_base, periodo_contable, clave_pais, region_sap, poblacion_sap,
        grupo_vendedores, pagador, emisor_solicitante, customer_bill_to, destinatario,
        grupo_clientes_2, atributo_6, atributo_7, atributo_10, clase_factura,
        nombre_usuario, texto, numero_documento, cantidad, moneda_sociedad,
        fe_contabilizacion, fecha_entrada, fecha_valor, documento_comercial,
        hora_entrada, moneda_transaccion, clave_moneda_transaccion, moneda_fuerte,
        clave_moneda_fuerte, numero_doc_referencia, numero_documento_2, incoterms,
        incoterms_parte_2, clase_documento, cond_pago, dias_1, numero_transporte, e,
        tipo_embalaje, nombre_producto, volumen_toneladas, nombre_pagador,
        nombre_solicitante, vendedor_sap, vendedor, vendedor_ok, gerencia, equipo,
        canal, sub_canal, dia, mes, anio, tipo_venta, localidad, provincia,
        dpto, region_m, ingreso_bruto, dpto_pagador, localidad_pagador,
        codigo_cliente, bonificaciones, centro_distribucion, zona_entrega,
        nombre_destinatario
    FROM int_ventas_bi
    WHERE is_current = 1
    ORDER BY fe_contabilizacion DESC, documento_comercial;
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)

    # Reemplazo de regla Power Query: GENERIC -> EXPORTACION
    if "dpto" in df.columns:
        df["dpto"] = df["dpto"].replace({"GENERIC": "EXPORTACION"})
    if "region_m" in df.columns:
        df["region_m"] = df["region_m"].replace({"GENERIC": "EXPORTACION"})
    if "dpto_pagador" in df.columns:
        df["dpto_pagador"] = df["dpto_pagador"].replace({"GENERIC": "EXPORTACION"})

    # Renombrar columnas tecnicas a encabezados de negocio identicos a BASE PANEL
    df = df.rename(columns=HEADER_MAPPING)

    exporter = ExcelReportExporter(EnvConfig.EXPORT_PATH)
    return exporter.export(df, "VENTAS_BI")
