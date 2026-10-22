from __future__ import annotations

import logging
from pathlib import Path
from sqlalchemy import text

from itacamba_reportes.core.db.connection import engine

logger = logging.getLogger(__name__)

SQL_PATH = Path(__file__).parent / "transform.sql"


def transform_query(target_month: tuple[int, int] | None = None) -> int:
    logger.info("Transformando stg_query -> int_query en BD...")
    sql_script = SQL_PATH.read_text(encoding="utf-8")

    if target_month:
        year, month = target_month
        custom_filter = f"WHERE (YEAR(COALESCE(q.fecha_salida, q.fecha_creacion_entrega)) = {year} AND MONTH(COALESCE(q.fecha_salida, q.fecha_creacion_entrega)) = {month})"
        idx = sql_script.find("WHERE (")
        if idx != -1:
            sql_script = sql_script[:idx] + custom_filter + ";"

    with engine.begin() as conn:
        for stmt in sql_script.split(";"):
            cleaned = stmt.strip()
            if cleaned:
                conn.execute(text(cleaned))

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT COUNT(*) FROM int_query")).scalar() or 0

    logger.info("Transformacion a int_query completada: %d filas", rows)
    return rows
