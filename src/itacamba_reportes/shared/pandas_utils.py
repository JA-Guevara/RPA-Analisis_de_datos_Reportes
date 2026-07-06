"""Helpers compartidos de pandas para la capa de transform.

Centralizan patrones repetidos (coerce a Int64, rename por posicion)
que aparecian replicados literalmente en gd20_normalize, cartera_pipeline
y cartera_normalize. UNA sola fuente de verdad por patron.
"""

from __future__ import annotations

import logging
from typing import Mapping

import pandas as pd

logger = logging.getLogger(__name__)


def to_int64(series: pd.Series) -> pd.Series:
    """Coerce robusto a pandas Int64 (nullable).

    Reemplaza el patron `pd.to_numeric(s, errors="coerce").astype("Int64")`
    que se repetia ~10 veces en gd20_normalize.
    """
    return pd.to_numeric(series, errors="coerce").astype("Int64")


def apply_rename_by_position(
    df: pd.DataFrame,
    mapping: Mapping[int, str] | None,
) -> pd.DataFrame:
    """Renombra columnas por posicion (0-indexed).

    Idempotente: aplicar dos veces no cambia el resultado, porque
    despues del primer rename la posicion ya tiene el nombre destino.

    Si `mapping` esta vacio o None, devuelve el df sin cambios.
    Posiciones fuera de rango se loggean como warning y se ignoran.
    """
    if not mapping:
        return df
    new_cols = list(df.columns)
    for pos, name in mapping.items():
        if 0 <= pos < len(new_cols):
            new_cols[pos] = name
        else:
            logger.warning("rename_by_position: pos=%d fuera de rango", pos)
    df.columns = new_cols
    return df
