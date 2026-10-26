from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from sqlalchemy import text

from itacamba_reportes.core.db.connection import engine

logger = logging.getLogger(__name__)

SQL_PATH = Path(__file__).parent / "transform.sql"


def transform_gd20(corte_fecha: date | str | None = None, is_fin_de_mes: bool = False) -> int:
    logger.info("Transformando stg_gd20 -> int_gd20 en Base de Datos...")
    sql_script = SQL_PATH.read_text(encoding="utf-8")

    # Macro EliminarFilasFechaActual:
    if not is_fin_de_mes:
        if corte_fecha:
            c_str = corte_fecha if isinstance(corte_fecha, str) else corte_fecha.strftime("%Y-%m-%d")
            date_filter = f"WHERE g.fe_contabilizacion < '{c_str}'"
        else:
            date_filter = "WHERE g.fe_contabilizacion < CAST(GETDATE() AS DATE)"
        sql_script = sql_script.replace("/* DATE_FILTER */", date_filter)
    else:
        sql_script = sql_script.replace("/* DATE_FILTER */", "")

    with engine.begin() as conn:
        for stmt in sql_script.split(";"):
            cleaned = stmt.strip()
            if cleaned:
                conn.execute(text(cleaned))

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT COUNT(*) FROM int_gd20")).scalar() or 0

    logger.info("Transformacion a int_gd20 completada: %d filas", rows)
    return rows
