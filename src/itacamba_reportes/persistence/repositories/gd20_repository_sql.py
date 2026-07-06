"""Impl SQL repo int_gd20."""

from __future__ import annotations

import logging
from collections.abc import Callable
from time import perf_counter

import pandas as pd
from sqlalchemy.orm import Session

from itacamba_reportes.persistence.df_to_rows import (
    dataframe_to_rows,
)
from itacamba_reportes.persistence.bulk_insert import bulk_replace
from itacamba_reportes.persistence.engine import SessionLocal
from itacamba_reportes.persistence.models.int.gd20_model import (
    Gd20IntModel,
)

logger = logging.getLogger(__name__)


_INT_COLUMNS: tuple[str, ...] = (
    "ejercicio", "sociedad", "organizacion_ventas", "canal_distribucion",
    "sector", "numero_cuenta", "material",
    "periodo_contable", "grupo_clientes_2", "pagador", "emisor_solicitante",
    "customer_bill_to", "destinatario", "numero_documento",
    "documento_comercial", "numero_doc_referencia", "numero_documento_2",
    "dias_1", "numero_transporte", "dia", "mes", "anio", "codigo_cliente",
)
# NOTA: centro_beneficio es String(50) en el model (ej: '31ITGCI002'),
# NO es Int. Estaba mal clasificado en _INT_COLUMNS — el coerce lo
# convertia a NaN y se insertaba como NULL.
_DATETIME_COLUMNS: tuple[str, ...] = (
    "fe_contabilizacion", "fecha_entrada", "fecha_valor",
)
_NUMERIC_COLUMNS: tuple[str, ...] = (
    "cantidad", "moneda_sociedad", "moneda_transaccion", "moneda_fuerte",
    "volumen_toneladas", "ingreso_bruto", "bonificaciones",
)


class Gd20IntRepositoryImpl:

    def __init__(self, session_factory: Callable[[], Session] | None = None) -> None:
        self.session_factory = session_factory or SessionLocal

    def count(self) -> int:
        from itacamba_reportes.persistence.session import get_session
        with get_session(self.session_factory) as session:
            return session.query(Gd20IntModel).count()

    def bulk_replace_from_df(self, df: pd.DataFrame) -> int:
        t0 = perf_counter()
        rows = self._dataframe_to_rows(df)
        prep_seconds = perf_counter() - t0

        # TRUNCATE + INSERT atomicos por cursor pyodbc crudo
        # (fast_executemany real, sin limite de 2.100 parametros).
        t_ins = perf_counter()
        bulk_replace(Gd20IntModel, rows)
        insert_seconds = perf_counter() - t_ins

        logger.info(
            "GD20 bulk_replace_from_df: rows=%d, df->rows=%.2fs, "
            "replace_raw=%.2fs, total=%.2fs",
            len(rows), prep_seconds, insert_seconds, perf_counter() - t0,
        )
        return len(rows)

    @staticmethod
    def _dataframe_to_rows(df: pd.DataFrame) -> list[dict]:
        return dataframe_to_rows(
            df,
            model=Gd20IntModel,
            int_cols=_INT_COLUMNS,
            datetime_cols=_DATETIME_COLUMNS,
            numeric_cols=_NUMERIC_COLUMNS,
        )
