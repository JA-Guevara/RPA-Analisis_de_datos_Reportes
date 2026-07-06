"""Despacho Mes Aggregate — GROUP BY + SUM sobre int_despacho_bi.

Resume el detalle de despachos en 1 fila por combinación de dimensiones:
    gerencia + equipo + departamento + localidad_im + centro_distribucion
    + producto + incoterms + fecha + codigo_cliente

Métricas sumadas:
    despacho_t  (desde int_despacho_bi)
    rf, rf_ajustado_im, proyeccion: quedan NULL hasta que negocio
        confirme la fuente de carga.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

logger = logging.getLogger(__name__)


_DEFAULT_GROUP_BY: tuple[str, ...] = (
    "gerencia",
    "equipo",
    "departamento",
    "localidad_im",      # localidad ajustada (no la raw)
    "centro_distribucion",
    "producto",
    "incoterms",
    "fecha",
    "mes",
    "dia",
    "codigo_cliente",
)

_DEFAULT_SUM_COLUMNS: tuple[str, ...] = (
    "despacho_t",
)


@dataclass(slots=True)
class DespachoMesAggregateUseCase:

    config: dict | None = None

    def execute(self, df: pd.DataFrame) -> pd.DataFrame:
        group_by = self._group_by(df)
        sum_cols = self._sum_columns(df)

        if not group_by:
            logger.warning("Despacho Mes aggregate skipped: sin cols para group by")
            return df.copy()

        agg = (
            df.groupby(group_by, dropna=False, as_index=False)[list(sum_cols)]
            .sum(min_count=1)
        )
        logger.info(
            "Despacho Mes aggregate: %d filas detalle -> %d filas agregadas "
            "(group by %d dimensiones)",
            len(df), len(agg), len(group_by),
        )

        # rf, rf_ajustado_im, proyeccion: placeholders (fuente externa TBD)
        for col in ("rf", "rf_ajustado_im", "proyeccion"):
            if col not in agg.columns:
                agg[col] = pd.NA

        # renombrar localidad_im -> localidad para mantener el header del Excel
        if "localidad_im" in agg.columns and "localidad" not in agg.columns:
            agg = agg.rename(columns={"localidad_im": "localidad"})

        return agg

    def _group_by(self, df: pd.DataFrame) -> list[str]:
        cols = (self.config or {}).get("group_by") or _DEFAULT_GROUP_BY
        return [c for c in cols if c in df.columns]

    def _sum_columns(self, df: pd.DataFrame) -> list[str]:
        cols = (self.config or {}).get("sum_columns") or _DEFAULT_SUM_COLUMNS
        return [c for c in cols if c in df.columns]
