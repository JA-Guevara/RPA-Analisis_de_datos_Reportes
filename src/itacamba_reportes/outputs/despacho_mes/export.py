from __future__ import annotations

import logging
from pathlib import Path
import pandas as pd

from itacamba_reportes.core.db.connection import engine
from itacamba_reportes.core.io.exporter import ExcelReportExporter
from itacamba_reportes.core.settings import EnvConfig

logger = logging.getLogger(__name__)


def export_despacho_mes() -> Path:
    logger.info("Exportando DESPACHO MES a Excel...")
    query = """
    SELECT 
        gerencia, equipo, departamento, localidad, centro_distribucion,
        producto, incoterms, dia, codigo_cliente,
        despacho_t, rf, rf_ajustado_im, proyeccion,
        nombre_cliente, vendedor, tipo_venta, canal, semana2
    FROM int_despacho_mes
    ORDER BY dia, gerencia, equipo;
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)

    exporter = ExcelReportExporter(EnvConfig.EXPORT_PATH)
    return exporter.export(df, "DESPACHO_MES")
