"""QUERY Mapping — selecciona las cols estables STG y descarta scratch.

A diferencia de GD20 (donde los nombres SAP son confusos y hay que
renombrar), el source de QUERY ya viene con nombres snake_case correctos.

  1. Descarta cols scratch (xx, xx2, xx3, xx4 — las "Unnamed" que pandas
     crea cuando el Excel SAP trae columnas sin header al final).
  2. Aplica renames opcionales vía config["renames_stg_to_int"].
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


# Columnas scratch del Excel QUERY que se descartan al pasar a INT.
_STG_ONLY_COLUMNS: frozenset[str] = frozenset({
    "xx", "xx2", "xx3", "xx4",
})


def apply_query_mapping(df: pd.DataFrame, config: dict | None = None) -> pd.DataFrame:
    to_drop = [c for c in df.columns if c in _STG_ONLY_COLUMNS]
    if to_drop:
        logger.info("Query mapping: descartadas cols scratch %s", to_drop)
        df = df.drop(columns=to_drop)

    renames = (config or {}).get("renames_stg_to_int", {})
    if not renames:
        return df
    applied = {k: v for k, v in renames.items() if k in df.columns}
    if applied:
        logger.info("Query mapping: %d cols renombradas STG->INT", len(applied))
    return df.rename(columns=renames)
