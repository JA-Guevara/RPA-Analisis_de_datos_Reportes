from __future__ import annotations

import logging
from time import perf_counter
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from itacamba_reportes.core.db.base import Base
from itacamba_reportes.core.db.connection import get_engine

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 10_000


def bulk_insert_df(
    model: type[Base],
    df: pd.DataFrame,
    *,
    truncate_first: bool = False,
    engine: Engine | None = None,
) -> int:
    eng = engine if engine is not None else get_engine()
    table = model.__tablename__

    if df.empty and not truncate_first:
        return 0

    t0 = perf_counter()
    with eng.begin() as conn:
        if truncate_first:
            try:
                conn.execute(text(f"TRUNCATE TABLE [{table}]"))
            except Exception:
                conn.execute(text(f"DELETE FROM [{table}]"))

        if not df.empty:
            clean_df = df.where(pd.notnull(df), None)
            clean_df.to_sql(
                table,
                conn,
                if_exists="append",
                index=False,
                chunksize=DEFAULT_CHUNK_SIZE,
                method=None,
            )

    rows = len(df)
    logger.info("Bulk insert %s: %d filas en %.2fs", table, rows, perf_counter() - t0)
    return rows
