from __future__ import annotations

import logging
from pathlib import Path
import pandas as pd

from itacamba_reportes.core.db.connection import engine
from itacamba_reportes.core.io.column_mappings import DESPACHO_MES_MAPPING, map_export_columns
from itacamba_reportes.core.io.exporter import ExcelReportExporter
from itacamba_reportes.core.settings import EnvConfig

logger = logging.getLogger(__name__)


def export_despacho_mes() -> Path:
    logger.info("Exportando DESPACHO MES a Excel...")
    query = """
    SELECT 
        gerencia, equipo, departamento, localidad, centro_distribucion,
        producto, incoterms,
        DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), dia) AS fecha,
        MONTH(GETDATE()) AS mes,
        dia, codigo_cliente,
        rf, despacho_t, rf_ajustado_im, proyeccion,
        nombre_cliente, vendedor, tipo_venta, canal, semana2
    FROM int_despacho_mes
    ORDER BY dia, gerencia, equipo;
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)

    # Renombrar y ordenar columnas usando el mapeo oficial de negocio (20 columnas)
    df = map_export_columns(df, DESPACHO_MES_MAPPING)
    logger.info("DESPACHO MES generado para exportación con %d columnas (esperadas: %d)", len(df.columns), len(DESPACHO_MES_MAPPING))

    exporter = ExcelReportExporter(EnvConfig.EXPORT_PATH)
    return exporter.export(df, "DESPACHO_MES")
