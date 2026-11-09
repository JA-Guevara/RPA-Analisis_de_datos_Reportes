from __future__ import annotations

import calendar
from datetime import datetime
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
        MONTH(GETDATE()) AS mes,
        dia, codigo_cliente,
        rf, despacho_t, rf_ajustado_im, proyeccion,
        nombre_cliente, vendedor, tipo_venta, canal, semana2
    FROM int_despacho_mes
    ORDER BY dia, gerencia, equipo;
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)

    now = datetime.now()
    _, max_day = calendar.monthrange(now.year, now.month)

    def _safe_date(d_val):
        try:
            d = int(d_val) if pd.notna(d_val) else 1
            return datetime(now.year, now.month, max(1, min(d, max_day))).date()
        except Exception:
            return now.date()

    df["fecha"] = df["dia"].apply(_safe_date)

    # Renombrar y ordenar columnas usando el mapeo oficial de negocio (20 columnas)
    df = map_export_columns(df, DESPACHO_MES_MAPPING)
    logger.info("DESPACHO MES generado para exportación con %d columnas (esperadas: %d)", len(df.columns), len(DESPACHO_MES_MAPPING))

    exporter = ExcelReportExporter(EnvConfig.EXPORT_PATH)
    return exporter.export(df, "DESPACHO_MES")
