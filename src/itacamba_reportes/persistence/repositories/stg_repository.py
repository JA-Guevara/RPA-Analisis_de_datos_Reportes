"""Repositorio STG genérico — TRUNCATE + bulk insert vectorizado.

stg_gd20 y stg_query comparten exactamente el mismo comportamiento;
la única variación es el modelo destino. Instanciar con el modelo:

    StgRepository(StgGd20Model)
    StgRepository(StgQueryModel)

(stg_cartera mantiene su repo propio: audita run_id + row_index.)
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from itacamba_reportes.persistence.base import Base
from itacamba_reportes.persistence.bulk_insert import bulk_insert
from itacamba_reportes.persistence.engine import SessionLocal
from itacamba_reportes.persistence.session import get_session
from itacamba_reportes.persistence.type_coercion import coerce_dataframe_for_model

logger = logging.getLogger(__name__)


class StgRepository:

    def __init__(
        self,
        model_cls: type[Base],
        session_factory: Callable[[], Session] | None = None,
    ) -> None:
        self.model_cls = model_cls
        self.session_factory = session_factory or SessionLocal

    def clean_all(self) -> int:
        with get_session(self.session_factory) as session:
            session.execute(text(f"TRUNCATE TABLE [{self.model_cls.__tablename__}]"))
        logger.info("STG clean_all: TRUNCATE %s", self.model_cls.__tablename__)
        return -1

    def bulk_insert(self, df: pd.DataFrame) -> int:
        if df.empty:
            logger.info("STG %s insert: 0 filas", self.model_cls.__tablename__)
            return 0
        # Coerción vectorizada a tipos nativos + insert raw fast_executemany
        records = coerce_dataframe_for_model(df, self.model_cls)
        bulk_insert(self.model_cls, records)
        logger.info("STG %s insert: %d filas", self.model_cls.__tablename__, len(records))
        return len(records)

    def count(self) -> int:
        with get_session(self.session_factory) as session:
            return session.query(self.model_cls).count()
