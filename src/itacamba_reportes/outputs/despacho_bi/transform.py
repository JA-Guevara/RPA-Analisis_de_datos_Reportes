from __future__ import annotations

import logging
from pathlib import Path
from sqlalchemy import text

from itacamba_reportes.core.db.connection import engine

logger = logging.getLogger(__name__)

SQL_PATH = Path(__file__).parent / "transform.sql"


def transform_despacho_bi() -> int:
    logger.info("Transformando y acumulando DESPACHO BI en Base de Datos...")
    from itacamba_reportes.core.db.schema import sync_table_columns
    try:
        sync_table_columns()
    except Exception as exc:
        logger.warning("No se pudo verificar o sincronizar columnas de int_despacho_bi: %s", exc)

    sql_script = SQL_PATH.read_text(encoding="utf-8")

    with engine.begin() as conn:
        for stmt in sql_script.split(";"):
            cleaned = stmt.strip()
            if cleaned:
                conn.execute(text(cleaned))

    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT COUNT(*),
                   COALESCE(SUM(despacho_t), 0),
                   COALESCE(SUM(traslados_t), 0),
                   SUM(CASE WHEN canal = 'OTROS' OR vendedor = 'OTROS' OR equipo = 'OTROS' THEN 1 ELSE 0 END)
            FROM int_despacho_bi
        """)).fetchone()
        rows = int(row[0]) if row and row[0] else 0
        tot_desp = float(row[1]) if row and row[1] else 0.0
        tot_tras = float(row[2]) if row and row[2] else 0.0
        otros_cnt = int(row[3]) if row and row[3] else 0

    logger.info(
        "DESPACHO BI acumulado con exito: %d filas | despacho_t=%.2f | traslados_t=%.2f | sin_homologar(OTROS)=%d",
        rows,
        tot_desp,
        tot_tras,
        otros_cnt,
    )
    return rows
