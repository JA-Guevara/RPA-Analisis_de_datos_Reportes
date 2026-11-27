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
        excluded_cement = conn.execute(text("""
            SELECT COUNT(*) FROM (
                SELECT DISTINCT material AS prod FROM int_query WHERE UPPER(material) LIKE '%CEMENTO%'
                UNION
                SELECT DISTINCT material AS prod FROM stg_proyeccion WHERE UPPER(material) LIKE '%CEMENTO%'
            ) u
            WHERE u.prod NOT IN (
                'CEMENTO IM-40 (BIG-BAG )',
                'CEMENTO IM-40 (BOLSAS 50KG.)',
                'CEMENTO IM-40 (GRANEL TN.)',
                'CEMENTO PORTLAND IF-30 50 KG',
                'CEMENTO PORTLAND IF-30 BIG BAG',
                'CEMENTO PORTLAND IF-30 GRANEL',
                'CEMENTO PORTLAND IF-40 50 KG',
                'CEMENTO PORTLAND IF-40 50 KG-MQL',
                'CEMENTO PORTLAND IP-30 PRO 50 KG-MQL',
                'CEMENTO PORTLAND TIPO CPII-C40 BIG BAG'
            )
        """)).scalar() or 0
        if excluded_cement > 0:
            logger.warning(
                "DESPACHO MES: %d material(es) con 'CEMENTO' fuera de la lista oficial del filtro IN; revisar si ingresó un SKU nuevo.",
                excluded_cement,
            )

    logger.info("DESPACHO MES generado exitosamente (dia_corte=%d): %d filas agregadas", resolved_dia, rows)
    return rows
