from __future__ import annotations

from datetime import date
import logging
from pathlib import Path
from sqlalchemy import text

from itacamba_reportes.core.db.connection import engine

logger = logging.getLogger(__name__)

SQL_PATH = Path(__file__).parent / "transform.sql"


def _resolve_end_bound(corte_fecha: date | str | None, incluir_hasta: bool) -> date | None:
    if not corte_fecha:
        return None
    end_str = corte_fecha if isinstance(corte_fecha, str) else corte_fecha.strftime("%Y-%m-%d")
    end_dt = date.fromisoformat(end_str)
    if incluir_hasta:
        end_dt = end_dt.fromordinal(end_dt.toordinal() + 1)
    return end_dt


def transform_query(
    target_month: tuple[int, int] | None = None,
    corte_fecha: date | str | None = None,
    is_fin_de_mes: bool = False,
    incluir_hasta: bool = False,
) -> int:
    logger.info("Transformando stg_query -> int_query en BD...")
    from itacamba_reportes.core.db.schema import sync_table_columns
    try:
        sync_table_columns()
    except Exception as exc:
        logger.warning("No se pudo verificar o sincronizar columnas de int_query: %s", exc)

    sql_script = SQL_PATH.read_text(encoding="utf-8")

    end_bound = _resolve_end_bound(corte_fecha, incluir_hasta or is_fin_de_mes)
    outer_cutoff = f"AND f_calc.fecha_efectiva < '{end_bound.isoformat()}'" if end_bound else ""
    inner_cutoff = (
        f"AND (CASE WHEN material = 'CLINQUER' AND fecha_salida IS NULL THEN fecha_creacion_entrega ELSE fecha_salida END) < '{end_bound.isoformat()}'"
        if end_bound
        else ""
    )

    if target_month:
        year, month = int(target_month[0]), int(target_month[1])
        month_selector = f"(YEAR(f_calc.fecha_efectiva) = {year} AND MONTH(f_calc.fecha_efectiva) = {month})"
    else:
        month_selector = (
            "DATEFROMPARTS(YEAR(f_calc.fecha_efectiva), MONTH(f_calc.fecha_efectiva), 1) = ("
            "SELECT MAX(DATEFROMPARTS("
            "YEAR(CASE WHEN material = 'CLINQUER' AND fecha_salida IS NULL THEN fecha_creacion_entrega ELSE fecha_salida END), "
            "MONTH(CASE WHEN material = 'CLINQUER' AND fecha_salida IS NULL THEN fecha_creacion_entrega ELSE fecha_salida END), 1)) "
            "FROM [stg_query] "
            "WHERE (CASE WHEN material = 'CLINQUER' AND fecha_salida IS NULL THEN fecha_creacion_entrega ELSE fecha_salida END) IS NOT NULL "
            f"{inner_cutoff})"
        )

    sql_script = sql_script.replace("/* OUTER_CUTOFF_FILTER */", outer_cutoff)
    sql_script = sql_script.replace("/* MONTH_SELECTOR */", month_selector)

    with engine.begin() as conn:
        for stmt in sql_script.split(";"):
            cleaned = stmt.strip()
            if cleaned:
                conn.execute(text(cleaned))

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT COUNT(*) FROM int_query")).scalar() or 0

    logger.info("Transformacion a int_query completada: %d filas", rows)
    return rows
