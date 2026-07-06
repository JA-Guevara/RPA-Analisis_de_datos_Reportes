"""Carga de tablas lookup con cache por proceso.

En `run-all`, gd20 / despacho_bi / despacho_mes cargaban las MISMAS
tablas de BD por separado (int_cartera de 48k filas se leía 3 veces:
~7s y ~80 MB repetidos por corrida). Esta cache evita la re-lectura
dentro de un mismo proceso.

SEGURIDAD DE LA CACHE — por qué no puede quedar stale:
- Solo se cachean tablas que ningún pipeline modifica DESPUÉS de su
  carga inicial en el DAG de run-all: int_cartera, int_ref_*, stg_query.
  (Las tablas de flujo principal — int_query, int_despacho_bi — NO
  pasan por aquí: se leen directo, como siempre.)
- El orquestador limpia la cache al inicio de cada run-all.
- Cada comando CLI es un proceso nuevo → cache vacía al arrancar.
"""

from __future__ import annotations

import logging

import pandas as pd

from itacamba_reportes.persistence.base import Base
from itacamba_reportes.persistence.engine import engine as _engine

logger = logging.getLogger(__name__)

_CACHE: dict[str, pd.DataFrame] = {}


def load_lookup_df(model: type[Base]) -> pd.DataFrame:
    """Tabla completa como DataFrame, cacheada por proceso."""
    if _engine is None:
        raise RuntimeError("Engine SQLAlchemy no inicializado (verificar .env)")
    table = model.__tablename__
    cached = _CACHE.get(table)
    if cached is not None:
        logger.info("Lookup %s: cache hit (%d filas)", table, len(cached))
        return cached
    df = pd.read_sql_table(table, _engine)
    _CACHE[table] = df
    return df


def clear_lookup_cache() -> None:
    if _CACHE:
        logger.info("Lookup cache limpiada (%d tablas)", len(_CACHE))
    _CACHE.clear()
