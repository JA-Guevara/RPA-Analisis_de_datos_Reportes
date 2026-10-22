from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from sqlalchemy import text

from itacamba_reportes.core.db.connection import engine

logger = logging.getLogger(__name__)

SQL_PATH = Path(__file__).parent / "transform.sql"


def transform_despacho_mes(dia_corte: int | None = None) -> int:
    logger.info("Transformando DESPACHO MES con unión vertical (Real + Proyección)...")
    if dia_corte is None:
        dia_corte = datetime.now().day

    sql_script = SQL_PATH.read_text(encoding="utf-8")
    sql_script = sql_script.replace("/* DIA_CORTE */", str(dia_corte))

    with engine.begin() as conn:
        for stmt in sql_script.split(";"):
            cleaned = stmt.strip()
            if cleaned:
                conn.execute(text(cleaned))

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT COUNT(*) FROM int_despacho_mes")).scalar() or 0

    logger.info("DESPACHO MES generado exitosamente: %d filas agregadas", rows)
    return rows
