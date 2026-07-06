"""Piezas compartidas de la capa de transformación.

- BusinessRule: contrato mínimo de una regla de negocio plugeable.
- apply_column_mapping: drop + rename declarativo (driver: YAML del dataset).
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


class BusinessRule(ABC):

    name: str = "unnamed_rule"

    @abstractmethod
    def apply(self, df: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
        ...


def apply_column_mapping(
    df: pd.DataFrame,
    *,
    rename: Mapping[str, str],
    drop: Sequence[str] = (),
    dataset: str = "",
) -> pd.DataFrame:
    """Drop + rename de columnas para llegar al schema int del dataset.

    Equivalente exacto del antiguo `CarteraMappingUseCase`:
    columnas de `drop` ausentes se ignoran; renames cuyas claves no
    están en el df se loggean como warning.
    """
    df = df.copy()

    cols = [c for c in drop if c in df.columns]
    if cols:
        df = df.drop(columns=cols)
        logger.info("%s mapping: %d cols dropped", dataset, len(cols))

    present = {k: v for k, v in rename.items() if k in df.columns}
    missing = set(rename) - set(present)
    if missing:
        logger.warning("%s mapping: cols missing en df = %s", dataset, missing)
    df = df.rename(columns=present)
    logger.info("%s mapping: %d cols renombradas", dataset, len(present))
    return df
