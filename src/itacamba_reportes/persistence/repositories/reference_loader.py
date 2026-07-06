"""Carga data-driven de los catálogos de referencia (int_ref_*).

Un catálogo = 1 modelo SQLAlchemy + 1 entrada en references.yaml.
Agregar un catálogo nuevo: crear el modelo, sumarlo a CATALOGS y
declarar su hoja/renames en references.yaml. Nada más.

La limpieza por celda replica EXACTAMENTE la del antiguo
BaseMapper._clean (strip + NULL_TOKENS→None + NaN→None), verificada
por tests de caracterización (tests/characterization).
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pandas as pd
from sqlalchemy import insert, text
from sqlalchemy.orm import Session

from itacamba_reportes.persistence.base import Base
from itacamba_reportes.persistence.engine import SessionLocal
from itacamba_reportes.persistence.session import get_session
from itacamba_reportes.persistence.models.references.almacen_model import AlmacenIntModel
from itacamba_reportes.persistence.models.references.centro_model import CentroIntModel
from itacamba_reportes.persistence.models.references.equipo_model import EquipoIntModel
from itacamba_reportes.persistence.models.references.localidad_model import LocalidadIntModel
from itacamba_reportes.persistence.models.references.material_model import MaterialIntModel
from itacamba_reportes.persistence.models.references.semana_model import SemanaIntModel
from itacamba_reportes.shared.null_tokens import NULL_TOKENS

logger = logging.getLogger(__name__)

_AUDIT_COLUMNS = frozenset({"id", "created_at", "updated_at"})


@dataclass(frozen=True, slots=True)
class ReferenceCatalog:
    key: str               # clave en references.yaml:catalogs y en rows_loaded
    model: type[Base]


# Registro de catálogos — el orden define el orden de carga.
CATALOGS: tuple[ReferenceCatalog, ...] = (
    ReferenceCatalog("almacen", AlmacenIntModel),
    ReferenceCatalog("centro", CentroIntModel),
    ReferenceCatalog("equipo", EquipoIntModel),
    ReferenceCatalog("material", MaterialIntModel),
    ReferenceCatalog("localidad", LocalidadIntModel),
    ReferenceCatalog("semana", SemanaIntModel),
)


def model_business_fields(model: type[Base]) -> tuple[str, ...]:
    return tuple(
        c.name for c in model.__table__.columns if c.name not in _AUDIT_COLUMNS
    )


def clean_value(value: Any) -> Any:
    """Réplica exacta de BaseMapper._clean (no cambiar sin recalibrar goldens)."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if stripped in NULL_TOKENS:
            return None
        return stripped
    return value


def df_to_clean_rows(df: pd.DataFrame, model: type[Base]) -> list[dict[str, Any]]:
    fields = model_business_fields(model)
    records = df.to_dict(orient="records")
    return [
        {f: clean_value(record.get(f)) for f in fields}
        for record in records
    ]


class ReferenceLoader:
    """TRUNCATE + INSERT atómico por catálogo (sesión corta, commit al éxito).

    Las tablas int_ref_* no tienen FKs apuntando a ellas, por lo que el
    TRUNCATE (con reset de IDENTITY) es seguro.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session] | None = None,
    ) -> None:
        self.session_factory = session_factory or SessionLocal

    def replace_all(self, model: type[Base], rows: list[dict[str, Any]]) -> int:
        with get_session(self.session_factory) as session:
            session.execute(text(f"TRUNCATE TABLE [{model.__tablename__}]"))
            if rows:
                session.execute(insert(model), rows)
        logger.info("%s replace_all: %d registros", model.__tablename__, len(rows))
        return len(rows)
