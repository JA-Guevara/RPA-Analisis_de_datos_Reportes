from __future__ import annotations

import logging
from pathlib import Path
import pandas as pd
from sqlalchemy import text

from itacamba_reportes.core.db.connection import engine
from itacamba_reportes.core.io.exporter import ExcelReportExporter
from itacamba_reportes.core.settings import EnvConfig

logger = logging.getLogger(__name__)


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

    exporter = ExcelReportExporter(EnvConfig.EXPORT_PATH)
    return exporter.export(df, "VENTAS_BI")
