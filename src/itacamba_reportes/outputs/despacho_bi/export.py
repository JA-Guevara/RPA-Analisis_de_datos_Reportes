from __future__ import annotations

import logging
from pathlib import Path
import pandas as pd

from itacamba_reportes.core.db.connection import engine
from itacamba_reportes.core.io.exporter import ExcelReportExporter
from itacamba_reportes.core.settings import EnvConfig

logger = logging.getLogger(__name__)


def export_despacho_bi() -> Path:
    logger.info("Exportando DESPACHO BI a Excel...")
    query = """
    SELECT 
        fecha_salida, dia, mes, anio, nro_pedido, incoterm,
        centro_origen, centro_destino, cod_material, material,
        cod_ruta, nom_ruta, cod_destinatario, nom_destinatario,
        cod_pagador, pagador, despacho_t, traslados_t,
        centro_distribucion, localidad, departamento,
        codigo_cliente, nombre_cliente, vendedor, desarrollador,
        equipo, gerencia, canal, localidad_im, semana
    FROM int_despacho_bi
    ORDER BY dia DESC, nro_pedido;
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)

    exporter = ExcelReportExporter(EnvConfig.EXPORT_PATH)
    return exporter.export(df, "DESPACHO_BI")
