from __future__ import annotations

import calendar
from datetime import datetime
import logging
from pathlib import Path
import pandas as pd
from sqlalchemy import text

from itacamba_reportes.core.db.connection import engine
from itacamba_reportes.core.io.column_mappings import DESPACHO_MES_MAPPING, map_export_columns
from itacamba_reportes.core.io.exporter import ExcelReportExporter
from itacamba_reportes.core.settings import EnvConfig

logger = logging.getLogger(__name__)


def export_despacho_mes() -> Path:
    logger.info("Exportando DESPACHO MES a Excel...")

    # Detectar el mes y año real del lote de datos procesados (int_query o int_gd20)
    with engine.connect() as conn:
        try:
            row = conn.execute(text("""
                SELECT 
                    COALESCE(
                        (SELECT TOP 1 mes FROM int_query WHERE mes IS NOT NULL ORDER BY id DESC),
                        (SELECT TOP 1 mes FROM int_gd20 WHERE mes IS NOT NULL ORDER BY id DESC),
                        MONTH(GETDATE())
                    ) AS report_month,
                    COALESCE(
                        (SELECT TOP 1 anio FROM int_query WHERE anio IS NOT NULL ORDER BY id DESC),
                        (SELECT TOP 1 anio FROM int_gd20 WHERE anio IS NOT NULL ORDER BY id DESC),
                        YEAR(GETDATE())
                    ) AS report_year
            """)).fetchone()
            rep_month = int(row[0]) if row and row[0] else datetime.now().month
            rep_year = int(row[1]) if row and row[1] else datetime.now().year
        except Exception:
            rep_month = datetime.now().month
            rep_year = datetime.now().year

    query = f"""
    SELECT 
        gerencia, equipo, departamento, localidad, centro_distribucion,
        producto, incoterms,
        {rep_month} AS mes,
        dia, codigo_cliente,
        rf, despacho_t, rf_ajustado_im, proyeccion,
        nombre_cliente, vendedor, tipo_venta, canal, semana2
    FROM int_despacho_mes
    ORDER BY dia, gerencia, equipo;
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)

    _, max_day = calendar.monthrange(rep_year, rep_month)

    def _safe_date(d_val):
        try:
            d = int(d_val) if pd.notna(d_val) else 1
            return datetime(rep_year, rep_month, max(1, min(d, max_day))).date()
        except Exception:
            return datetime(rep_year, rep_month, 1).date()

    df["fecha"] = df["dia"].apply(_safe_date)

    # Renombrar y ordenar columnas usando el mapeo oficial de negocio (20 columnas)
    df = map_export_columns(df, DESPACHO_MES_MAPPING)
    logger.info("DESPACHO MES generado para exportación con %d columnas (esperadas: %d)", len(df.columns), len(DESPACHO_MES_MAPPING))

    exporter = ExcelReportExporter(EnvConfig.EXPORT_PATH)
    return exporter.export(df, "DESPACHO_MES")
