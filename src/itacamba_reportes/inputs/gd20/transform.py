from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from sqlalchemy import text

from itacamba_reportes.core.db.connection import engine

logger = logging.getLogger(__name__)

SQL_PATH = Path(__file__).parent / "transform.sql"


def transform_gd20(
    corte_fecha: date | str | None = None,
    is_fin_de_mes: bool = False,
    fecha_desde: date | str | None = None,
    incluir_hasta: bool = False,
) -> int:
    logger.info("Transformando stg_gd20 -> int_gd20 en Base de Datos...")
    sql_script = SQL_PATH.read_text(encoding="utf-8")

    # Macro EliminarFilasFechaActual:
    date_parts = []
    if fecha_desde:
        start_str = fecha_desde if isinstance(fecha_desde, str) else fecha_desde.strftime("%Y-%m-%d")
        date.fromisoformat(start_str)
        date_parts.append(f"g.fe_contabilizacion >= '{start_str}'")
    if corte_fecha:
        end_str = corte_fecha if isinstance(corte_fecha, str) else corte_fecha.strftime("%Y-%m-%d")
        end_date = date.fromisoformat(end_str)
        if incluir_hasta:
            end_date = end_date.fromordinal(end_date.toordinal() + 1)
        date_parts.append(f"g.fe_contabilizacion < '{end_date.isoformat()}'")
    elif not is_fin_de_mes:
        date_parts.append("g.fe_contabilizacion < CAST(GETDATE() AS DATE)")
    date_filter = f"WHERE {' AND '.join(date_parts)}" if date_parts else ""
    sql_script = sql_script.replace("/* DATE_FILTER */", date_filter)

    with engine.begin() as conn:
        for stmt in sql_script.split(";"):
            cleaned = stmt.strip()
            if cleaned:
                conn.execute(text(cleaned))

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT COUNT(*) FROM int_gd20")).scalar() or 0

    logger.info("Transformacion a int_gd20 completada: %d filas", rows)
    return rows
