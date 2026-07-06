"""Despacho Mes Business Rules — cleanup + reset proyección.

Equivale a 2 macros VBA del basepanel:

  1. EliminarFilasDespacho:
     Drop filas donde codigo_cliente, rf, despacho_t, rf_ajustado_im
     están TODOS vacíos o cero.

  2. EliminarRFajustado:
     Si dia < dia_actual AND proyeccion >= 0 AND proyeccion no nulo
     → resetear rf_ajustado_im = NULL.

Cleanup orden importante: PRIMERO se borran filas vacías; después se
ajusta proyección sobre las filas que sobreviven.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


_CLEANUP_COLUMNS: tuple[str, ...] = (
    "codigo_cliente", "rf", "despacho_t", "rf_ajustado_im",
)


@dataclass(slots=True)
class DespachoMesBusinessRulesUseCase:

    config: dict | None = None
    now_provider: Any = datetime.now

    def execute(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self._drop_empty_metric_rows(df)
        df = self._reset_rf_ajustado_past_days(df)
        return df

    # ───────────────────────────────────────────────────────────────────
    # REGLA 1: EliminarFilasDespacho
    # ───────────────────────────────────────────────────────────────────
    def _drop_empty_metric_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        rule = (self.config or {}).get("cleanup_empty_rows", {})
        if rule and not rule.get("enabled", True):
            return df

        cols = rule.get("columns") or _CLEANUP_COLUMNS
        present = [c for c in cols if c in df.columns]
        if not present:
            logger.warning(
                "Despacho Mes cleanup skipped: ninguna col de %s presente",
                cols,
            )
            return df

        is_empty_or_zero = (
            df[present]
            .apply(lambda s: pd.to_numeric(s, errors="coerce").fillna(0) == 0)
            .all(axis=1)
        )
        n_before = len(df)
        df = df.loc[~is_empty_or_zero].reset_index(drop=True)
        n_after = len(df)
        logger.info(
            "Despacho Mes cleanup: %d filas eliminadas (cols %s todas vacias/cero)",
            n_before - n_after, present,
        )
        return df

    # ───────────────────────────────────────────────────────────────────
    # REGLA 2: EliminarRFajustado
    # ───────────────────────────────────────────────────────────────────
    def _reset_rf_ajustado_past_days(self, df: pd.DataFrame) -> pd.DataFrame:
        rule = (self.config or {}).get("reset_rf_ajustado_past_days", {})
        if rule and not rule.get("enabled", True):
            return df

        target_col = rule.get("target_col", "rf_ajustado_im")
        proyeccion_col = rule.get("proyeccion_col", "proyeccion")
        dia_col = rule.get("dia_col", "dia")

        if any(c not in df.columns for c in (target_col, proyeccion_col, dia_col)):
            logger.warning(
                "Despacho Mes reset_rf_ajustado skipped: faltan cols (%s, %s, %s)",
                target_col, proyeccion_col, dia_col,
            )
            return df

        now = self.now_provider()
        dia_actual = now.day

        dia = pd.to_numeric(df[dia_col], errors="coerce")
        proy = pd.to_numeric(df[proyeccion_col], errors="coerce")

        mask = (dia < dia_actual) & proy.notna() & (proy >= 0)
        n = int(mask.sum())
        if n == 0:
            return df

        df.loc[mask, target_col] = pd.NA
        logger.info(
            "Despacho Mes reset_rf_ajustado: %d filas reseteadas "
            "(dia < %d AND proyeccion >= 0)",
            n, dia_actual,
        )
        return df
