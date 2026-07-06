"""QUERY Normalize — limpieza de valores raw.

Equivale a la macro VBA `ModificarCentro` del basepanel.xlsm:

    Sub ModificarCentro()
        ' En QUERY col M (centro_receptor):
        ' reemplazar "#" por 0
    End Sub

El "#" en QUERY.centro_receptor representa "Sin asignar" en el SAP.
Para que los lookups posteriores no rompan, lo convertimos a 0 (consistente
con cómo GD20 trata clientes sin asignar).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

logger = logging.getLogger(__name__)


_HASH_SENTINEL: str = "#"
_HASH_REPLACEMENT: str = "0"


@dataclass(slots=True)
class QueryNormalizeUseCase:

    config: dict | None = None

    def execute(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self._centro_receptor_hash_to_zero(df)
        return df

    def _centro_receptor_hash_to_zero(self, df: pd.DataFrame) -> pd.DataFrame:
        sentinel = (self.config or {}).get("hash_sentinel", _HASH_SENTINEL)
        replacement = (self.config or {}).get("hash_replacement", _HASH_REPLACEMENT)

        if "centro_receptor" not in df.columns:
            logger.warning("Query normalize skipped: falta col 'centro_receptor'")
            return df

        mask = df["centro_receptor"].astype("string") == sentinel
        n = int(mask.sum())
        if n == 0:
            return df

        df.loc[mask, "centro_receptor"] = replacement
        logger.info(
            "Query normalize: centro_receptor '%s' -> '%s' en %d filas",
            sentinel, replacement, n,
        )
        return df
