from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from sqlalchemy import text

from itacamba_reportes.core.db.connection import engine

logger = logging.getLogger(__name__)

SQL_PATH = Path(__file__).parent / "transform.sql"


def resolve_dia_corte(
    dia_corte: int | None = None,
    corte_fecha: date | str | None = None,
    is_fin_de_mes: bool = False,
    incluir_hasta: bool = False,
) -> int:
    if dia_corte is not None:
        return int(dia_corte)
    if corte_fecha:
        c_str = corte_fecha if isinstance(corte_fecha, str) else corte_fecha.strftime("%Y-%m-%d")
        c_dt = date.fromisoformat(c_str)
        return c_dt.day + 1 if (incluir_hasta or is_fin_de_mes) else c_dt.day
    if is_fin_de_mes:
        return 32
    return datetime.now().day


def transform_despacho_mes(
    dia_corte: int | None = None,
    corte_fecha: date | str | None = None,
    is_fin_de_mes: bool = False,
    incluir_hasta: bool = False,
) -> int:
    logger.info("Transformando DESPACHO MES con unión vertical (Real + Proyección)...")
    resolved_dia = resolve_dia_corte(
        dia_corte=dia_corte,
        corte_fecha=corte_fecha,
        is_fin_de_mes=is_fin_de_mes,
        incluir_hasta=incluir_hasta,
    )

    sql_script = SQL_PATH.read_text(encoding="utf-8")
    sql_script = sql_script.replace("/* DIA_CORTE */", str(resolved_dia))

    with engine.begin() as conn:
        for stmt in sql_script.split(";"):
            cleaned = stmt.strip()
            if cleaned:
                conn.execute(text(cleaned))

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT COUNT(*) FROM int_despacho_mes")).scalar() or 0

    logger.info("DESPACHO MES generado exitosamente (dia_corte=%d): %d filas agregadas", resolved_dia, rows)
    return rows
