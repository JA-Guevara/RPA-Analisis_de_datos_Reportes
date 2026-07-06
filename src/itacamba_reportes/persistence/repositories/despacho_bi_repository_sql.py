"""Impl SQL del repositorio int_despacho_bi."""

from __future__ import annotations

import logging
from collections.abc import Callable
from time import perf_counter

import pandas as pd
from sqlalchemy.orm import Session

from itacamba_reportes.persistence.df_to_rows import dataframe_to_rows
from itacamba_reportes.persistence.bulk_insert import bulk_replace
from itacamba_reportes.persistence.engine import SessionLocal
from itacamba_reportes.persistence.models.int.despacho_bi_model import (
    DespachoBiIntModel,
)

logger = logging.getLogger(__name__)


_INT_COLUMNS: tuple[str, ...] = (
    "material",
    "documento_venta",
    "destinatario_mcia",
    "transportista",
    "dia",
    "mes",
    "anio",
    "semana_anio",
    "codigo_cliente",
    "x",
)

_DATETIME_COLUMNS: tuple[str, ...] = (
    "fecha",
)

_NUMERIC_COLUMNS: tuple[str, ...] = (
    "distancia",
    "cantidad",
    "despacho_t",
    "traslados_t",
)


class IntDespachoBiRepositoryImpl:

    def __init__(self, session_factory: Callable[[], Session] | None = None) -> None:
        self.session_factory = session_factory or SessionLocal

    def count(self) -> int:
        from itacamba_reportes.persistence.session import get_session
        with get_session(self.session_factory) as session:
            return session.query(DespachoBiIntModel).count()

    def bulk_replace_from_df(self, df: pd.DataFrame) -> int:
        t0 = perf_counter()
        rows = self._dataframe_to_rows(df)
        prep_seconds = perf_counter() - t0

        # TRUNCATE + INSERT atomicos por cursor pyodbc crudo
        # (fast_executemany real, sin limite de 2.100 parametros).
        t_ins = perf_counter()
        bulk_replace(DespachoBiIntModel, rows)
        insert_seconds = perf_counter() - t_ins

        logger.info(
            "DespachoBi bulk_replace_from_df: rows=%d, df->rows=%.2fs, "
            "replace_raw=%.2fs, total=%.2fs",
            len(rows), prep_seconds, insert_seconds, perf_counter() - t0,
        )
        return len(rows)

    @staticmethod
    def _dataframe_to_rows(df: pd.DataFrame) -> list[dict]:
        return dataframe_to_rows(
            df,
            model=DespachoBiIntModel,
            int_cols=_INT_COLUMNS,
            datetime_cols=_DATETIME_COLUMNS,
            numeric_cols=_NUMERIC_COLUMNS,
        )
