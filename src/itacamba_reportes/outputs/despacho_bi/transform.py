from __future__ import annotations

import logging
from pathlib import Path
from sqlalchemy import text

from itacamba_reportes.core.db.connection import engine

logger = logging.getLogger(__name__)

SQL_PATH = Path(__file__).parent / "transform.sql"


def transform_despacho_bi() -> int:
    logger.info("Transformando y acumulando DESPACHO BI en Base de Datos...")
    sql_script = SQL_PATH.read_text(encoding="utf-8")

    with engine.begin() as conn:
        for stmt in sql_script.split(";"):
            cleaned = stmt.strip()
            if cleaned:
                conn.execute(text(cleaned))

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT COUNT(*) FROM int_despacho_bi")).scalar() or 0

    logger.info("DESPACHO BI acumulado con exito: %d filas totales", rows)
    return rows
