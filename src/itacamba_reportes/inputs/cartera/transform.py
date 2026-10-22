from __future__ import annotations

import logging
from pathlib import Path
from sqlalchemy import text

from itacamba_reportes.core.db.connection import engine

logger = logging.getLogger(__name__)

SQL_PATH = Path(__file__).parent / "transform.sql"


def transform_cartera() -> int:
    logger.info("Ejecutando transformacion de Cartera en Base de Datos...")
    sql_script = SQL_PATH.read_text(encoding="utf-8")

    with engine.begin() as conn:
        for stmt in sql_script.split(";"):
            cleaned = stmt.strip()
            if cleaned:
                conn.execute(text(cleaned))

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT COUNT(*) FROM int_cartera")).scalar() or 0

    logger.info("Transformacion int_cartera completada: %d filas", rows)
    return rows
