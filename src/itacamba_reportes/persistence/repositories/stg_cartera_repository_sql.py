"""Impl SQL repo STG cartera."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from datetime import datetime

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from itacamba_reportes.persistence.bulk_insert import bulk_insert
from itacamba_reportes.persistence.engine import SessionLocal
from itacamba_reportes.persistence.models.stg.stg_cartera_model import (
    StgCarteraModel,
)
from itacamba_reportes.persistence.session import get_session

logger = logging.getLogger(__name__)


_HEADER_TO_COL: dict[str, str] = {
    "Cliente": "cliente",
    "Column2": "column2",
    "Attribute 10": "attribute_10",
    "Población": "poblacion",
    "Barrio": "barrio",
    "Attribute 7": "attribute_7",
    "Attribute 6": "attribute_6",
    "Región": "region",
    "Column9": "column9",
    "Grupo de cuentas": "grupo_de_cuentas",
    "Column11": "column11",
    "Teléfono": "telefono",
    "N.I.F 1": "nif_1",
    "Código postal": "codigo_postal",
    "GCD: CódEmplazFiscal": "gcd_codemplazfiscal",
    "Calle": "calle",
    "Inclusion date": "inclusion_date",
    "Tipo de operación": "tipo_de_operacion",
    "ZEMAILADD": "zemailadd",
    "ZVCRISK": "zvcrisk",
    "Vía de pago": "via_de_pago",
    "Sector": "sector",
    "Column23": "column23",
    "Canal Distribución": "canal_distribucion",
    "Column25": "column25",
    "Organización de Ventas": "organizacion_de_ventas",
    "Column27": "column27",
    "Oficina de Ventas": "oficina_de_ventas",
    "Column29": "column29",
    "Grupo de vendedores": "grupo_de_vendedores",
    "Equipo": "equipo",
    "Representante ventas": "representante_ventas",
    "Vendedor": "vendedor",
    "Coordinador Ventas": "coordinador_ventas",
    "Coordinador": "coordinador",
    "Trilha": "trilha",
    "Canal": "canal",
    "Condición pago": "condicion_pago",
    "Contador": "contador",
}


class StgCarteraIntRepositoryImpl:

    def __init__(self, session_factory: Callable[[], Session] | None = None) -> None:
        self.session_factory = session_factory or SessionLocal

    def clean_all(self) -> int:
        with get_session(self.session_factory) as session:
            session.execute(text(f"TRUNCATE TABLE [{StgCarteraModel.__tablename__}]"))
        logger.info("STG cartera clean_all: TRUNCATE %s", StgCarteraModel.__tablename__)
        return -1

    def bulk_insert(self, rows: Iterable[dict[str, str]], run_id: datetime) -> int:
        rows_list = list(rows)
        if not rows_list:
            logger.info("STG cartera insert: 0 filas (run_id=%s)", run_id)
            return 0

        # Vectorizado: pd.DataFrame para rename masivo y stringify por columna,
        # con None explicito en celdas nulas (evita NaN -> pyodbc bug 22003).
        df = pd.DataFrame(rows_list)
        valid_headers = [h for h in df.columns if h in _HEADER_TO_COL]
        df = df[valid_headers].rename(columns=_HEADER_TO_COL)

        for col in df.columns:
            s = df[col]
            nulls = s.isna()
            new = s.astype(object)
            if (~nulls).any():
                new.loc[~nulls] = s.loc[~nulls].astype(str)
            new.loc[nulls] = None
            df[col] = new

        data_records = df.to_dict(orient="records")
        mappings = [
            {"run_id": run_id, "row_index": i, **rec}
            for i, rec in enumerate(data_records)
        ]

        bulk_insert(StgCarteraModel, mappings)
        logger.info("STG cartera insert: %d filas (run_id=%s)", len(mappings), run_id)
        return len(mappings)

    def count(self) -> int:
        with get_session(self.session_factory) as session:
            return session.query(StgCarteraModel).count()
