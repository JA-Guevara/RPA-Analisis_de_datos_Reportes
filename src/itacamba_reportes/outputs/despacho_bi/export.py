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
    query = "SELECT * FROM int_despacho_bi ORDER BY dia DESC, nro_pedido;"
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)

    exporter = ExcelReportExporter(EnvConfig.EXPORT_PATH)
    control = {
        "Total filas despachadas": len(df),
        "Total Toneladas Despacho": df["despacho_t"].sum() if "despacho_t" in df.columns else 0,
    }
    return exporter.export(df, "DESPACHO_BI", control_info=control)
