"""Reglas del reporte QUERY — las 2 macros VBA del basepanel.

Movidas verbatim en Fase 5 del plan 2026-07-06:

  QueryNormalizeUseCase      macro ModificarCentro (centro_receptor '#'->0)
  QueryBusinessRulesUseCase  macro EliminarMeses (filtro de mes objetivo,
                             modos auto/current/explicito/null con fallback)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

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


_DEFAULT_MES_OBJETIVO: str = "auto"


@dataclass(slots=True)
class QueryBusinessRulesUseCase:

    config: dict | None = None
    now_provider: Any = datetime.now  # inyectable para tests

    def execute(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self._filter_by_target_month(df)
        return df

    def _filter_by_target_month(self, df: pd.DataFrame) -> pd.DataFrame:
        target = self._resolve_target(df)
        if target is None:
            logger.info(
                "Query rules: filtro de mes deshabilitado (corrida completa, %d filas)",
                len(df),
            )
            return df

        if "anio" not in df.columns or "mes" not in df.columns:
            logger.warning(
                "Query rules skipped: faltan cols 'anio'/'mes' para filtrar",
            )
            return df

        anio_target, mes_target = target
        anio = pd.to_numeric(df["anio"], errors="coerce")
        mes = pd.to_numeric(df["mes"], errors="coerce")

        # Distribucion de meses en el dataset (diagnostico)
        dist = self._month_distribution(anio, mes)
        logger.info(
            "Query rules: distribucion de meses en Excel -> %s",
            self._format_distribution(dist),
        )

        mask = (anio == anio_target) & (mes == mes_target)
        n_before, n_after = len(df), int(mask.sum())

        # FALLBACK: si el target dejaria 0 filas, usar el ULTIMO mes con datos
        if n_after == 0 and len(dist) > 0:
            last_yyyymm = max(dist.keys())
            last_anio, last_mes = last_yyyymm
            logger.warning(
                "Query rules: filtro %04d-%02d resulta en 0 filas. "
                "Fallback automatico al ultimo mes con datos: %04d-%02d (%d filas).",
                anio_target, mes_target, last_anio, last_mes, dist[last_yyyymm],
            )
            anio_target, mes_target = last_anio, last_mes
            mask = (anio == anio_target) & (mes == mes_target)
            n_after = int(mask.sum())

        logger.info(
            "Query rules: filtro mes %04d-%02d aplicado (%d -> %d filas)",
            anio_target, mes_target, n_before, n_after,
        )
        return df.loc[mask].reset_index(drop=True)

    # ────────────────────────────────────────────────────────────────────
    # Resolucion del target — soporta "auto", "current", dict, null
    # ────────────────────────────────────────────────────────────────────
    def _resolve_target(self, df: pd.DataFrame) -> tuple[int, int] | None:
        raw = (self.config or {}).get("mes_objetivo", _DEFAULT_MES_OBJETIVO)

        if raw is None:
            return None

        if isinstance(raw, dict) and "anio" in raw and "mes" in raw:
            return int(raw["anio"]), int(raw["mes"])

        if raw == "auto":
            target = self._auto_detect_target(df)
            if target is None:
                # Sin cols anio/mes -> fallback a current (no podemos autodetectar)
                now = self.now_provider()
                logger.warning(
                    "Query rules: 'auto' no pudo detectar mes (sin data); "
                    "fallback a mes corriente %04d-%02d",
                    now.year, now.month,
                )
                return now.year, now.month
            logger.info(
                "Query rules: 'auto' detecto ultimo mes con datos = %04d-%02d",
                target[0], target[1],
            )
            return target

        if raw == "current":
            now = self.now_provider()
            return now.year, now.month

        logger.warning(
            "Query rules: valor 'mes_objetivo'=%r no reconocido; usa 'auto'",
            raw,
        )
        return self._auto_detect_target(df) or (
            self.now_provider().year, self.now_provider().month
        )

    # ────────────────────────────────────────────────────────────────────
    # Helpers
    # ────────────────────────────────────────────────────────────────────
    @staticmethod
    def _auto_detect_target(df: pd.DataFrame) -> tuple[int, int] | None:
        """Devuelve (anio, mes) con MAS filas en el dataset. None si no hay cols."""
        if "anio" not in df.columns or "mes" not in df.columns or df.empty:
            return None
        anio = pd.to_numeric(df["anio"], errors="coerce")
        mes = pd.to_numeric(df["mes"], errors="coerce")
        # ULTIMO mes (yyyy-mm mas reciente) con al menos 1 fila
        pairs = (
            pd.DataFrame({"anio": anio, "mes": mes})
            .dropna()
            .astype({"anio": int, "mes": int})
        )
        if pairs.empty:
            return None
        # Tomamos el mas reciente, no el mas frecuente — operativo
        last = pairs.sort_values(["anio", "mes"]).iloc[-1]
        return int(last["anio"]), int(last["mes"])

    @staticmethod
    def _month_distribution(anio: pd.Series, mes: pd.Series) -> dict[tuple[int, int], int]:
        pairs = (
            pd.DataFrame({"anio": anio, "mes": mes})
            .dropna()
            .astype({"anio": int, "mes": int})
        )
        counts = pairs.value_counts().to_dict()
        return {(a, m): n for (a, m), n in counts.items()}

    @staticmethod
    def _format_distribution(dist: dict[tuple[int, int], int]) -> str:
        if not dist:
            return "(sin datos validos)"
        items = sorted(dist.items())
        # Mostrar todos los meses (compacto)
        return ", ".join(f"{a:04d}-{m:02d}={n}" for (a, m), n in items)
