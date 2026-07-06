"""Impl SQL repo int_cartera."""

from __future__ import annotations

import logging
from collections.abc import Callable
from time import perf_counter

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from itacamba_reportes.persistence.df_to_rows import (
    dataframe_to_rows,
)
from itacamba_reportes.persistence.bulk_insert import bulk_replace
from itacamba_reportes.persistence.engine import SessionLocal
from itacamba_reportes.persistence.models.int.cartera_model import (
    CarteraIntModel,
)
from itacamba_reportes.persistence.session import get_session

logger = logging.getLogger(__name__)


_INT_COLUMNS: tuple[str, ...] = ("cliente", "contador")
_DATETIME_COLUMNS: tuple[str, ...] = ("fecha_inclusion",)


def _truncate_sql(model: type) -> str:
    return f"TRUNCATE TABLE [{model.__tablename__}]"


class CarteraIntRepositoryImpl:

    def __init__(self, session_factory: Callable[[], Session] | None = None) -> None:
        self.session_factory = session_factory or SessionLocal

    def count(self) -> int:
        with get_session(self.session_factory) as session:
            return session.query(CarteraIntModel).count()

    def clean_all(self) -> int:
        with get_session(self.session_factory) as session:
            session.execute(text(_truncate_sql(CarteraIntModel)))
        logger.info("Cartera clean_all: TRUNCATE %s", CarteraIntModel.__tablename__)
        return -1

    def bulk_replace_from_df(self, df: pd.DataFrame) -> int:
        t0 = perf_counter()
        rows = self._dataframe_to_rows(df)
        prep_seconds = perf_counter() - t0

        # TRUNCATE + INSERT atomicos por cursor pyodbc crudo
        # (fast_executemany real, sin limite de 2.100 parametros).
        t_ins = perf_counter()
        bulk_replace(CarteraIntModel, rows)
        insert_seconds = perf_counter() - t_ins

        logger.info(
            "Cartera bulk_replace_from_df: rows=%d, df->rows=%.2fs, "
            "replace_raw=%.2fs, total=%.2fs",
            len(rows), prep_seconds, insert_seconds, perf_counter() - t0,
        )
        return len(rows)

    @staticmethod
    def _dataframe_to_rows(df: pd.DataFrame) -> list[dict]:
        return dataframe_to_rows(
            df,
            model=CarteraIntModel,
            int_cols=_INT_COLUMNS,
            datetime_cols=_DATETIME_COLUMNS,
        )
