from __future__ import annotations

import logging
import math
from time import perf_counter
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from itacamba_reportes.core.db.base import Base
from itacamba_reportes.core.db.connection import get_engine

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 10_000


def _normalize_dbapi_val(v: Any) -> Any:
    if v is None or v is pd.NA or v is pd.NaT:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, pd.Timestamp):
        return None if pd.isna(v) else v.to_pydatetime()
    if hasattr(v, "item"):
        return v.item()
    return v


def _fast_executemany_mssql(conn: Connection, table: str, df: pd.DataFrame, chunk_size: int) -> bool:
    raw_conn = getattr(conn, "connection", None)
    dbapi_conn = getattr(raw_conn, "driver_connection", None) or getattr(raw_conn, "connection", None) or raw_conn
    if dbapi_conn is None or not hasattr(dbapi_conn, "cursor"):
        return False

    cols = list(df.columns)
    col_sql = ", ".join(f"[{c}]" for c in cols)
    placeholders = ", ".join("?" for _ in cols)
    sql = f"INSERT INTO [{table}] ({col_sql}) VALUES ({placeholders})"

    cursor = dbapi_conn.cursor()
    try:
        if hasattr(cursor, "fast_executemany"):
            cursor.fast_executemany = True
        norm = _normalize_dbapi_val
        total = len(df)
        for start in range(0, total, chunk_size):
            batch_df = df.iloc[start:start + chunk_size]
            params = [tuple(norm(v) for v in row) for row in batch_df.itertuples(index=False, name=None)]
            cursor.executemany(sql, params)
        return True
    finally:
        cursor.close()


def _insert_into_conn(conn: Connection, eng: Engine, table: str, df: pd.DataFrame) -> None:
    if eng.dialect.name == "mssql" and _fast_executemany_mssql(conn, table, df, DEFAULT_CHUNK_SIZE):
        return
    clean_df = df.where(pd.notnull(df), None)
    clean_df.to_sql(
        table,
        conn,
        if_exists="append",
        index=False,
        chunksize=DEFAULT_CHUNK_SIZE,
        method=None,
    )


def bulk_insert_df(
    model: type[Base],
    df: pd.DataFrame,
    *,
    truncate_first: bool = False,
    engine: Engine | None = None,
    conn: Connection | None = None,
) -> int:
    eng = engine if engine is not None else (conn.engine if conn is not None else get_engine())
    table = model.__tablename__

    if df.empty and not truncate_first:
        return 0

    t0 = perf_counter()

    def _run(active_conn: Connection) -> None:
        if truncate_first:
            try:
                active_conn.execute(text(f"TRUNCATE TABLE [{table}]"))
            except Exception:
                active_conn.execute(text(f"DELETE FROM [{table}]"))
        if not df.empty:
            _insert_into_conn(active_conn, eng, table, df)

    if conn is not None:
        _run(conn)
    else:
        with eng.begin() as owned_conn:
            _run(owned_conn)

    rows = len(df)
    logger.info("Bulk insert %s: %d filas en %.2fs", table, rows, perf_counter() - t0)
    return rows
