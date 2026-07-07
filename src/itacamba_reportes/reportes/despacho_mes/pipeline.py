"""Pipeline DESPACHO MES — int_despacho_bi -> agregación mensual -> export.

DB-a-DB. El filtro de mes objetivo (auto/current/explícito) y el
fallback al último mes con datos se preservan tal cual.

Los 5 VLOOKUP vivos de la hoja están declarados en columnas.yaml del
slice (ColumnEngine); las macros VBA portadas viven en reglas.py.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from time import perf_counter
from typing import Any

import pandas as pd

from itacamba_reportes.persistence.engine import engine as _engine
from itacamba_reportes.persistence.excel_report_exporter import ExcelReportExporter
from itacamba_reportes.persistence.lookups import load_lookup_df
from itacamba_reportes.persistence.models.int.cartera_model import CarteraIntModel
from itacamba_reportes.persistence.models.int.despacho_bi_model import (
    DespachoBiIntModel,
)
from itacamba_reportes.persistence.models.int.despacho_mes_model import (
    DespachoMesIntModel,
)
from itacamba_reportes.persistence.models.references.almacen_model import AlmacenIntModel
from itacamba_reportes.persistence.models.references.semana_model import SemanaIntModel
from itacamba_reportes.persistence.repositories.despacho_mes_repository_sql import (
    IntDespachoMesRepositoryImpl,
)
from itacamba_reportes.pipelines.runner import PipelineResult, log_summary
from itacamba_reportes.reportes.despacho_mes.agregacion import (
    DespachoMesAggregateUseCase,
)
from itacamba_reportes.reportes.despacho_mes.reglas import (
    DespachoMesBusinessRulesUseCase,
)
from itacamba_reportes.transforms.column_engine import ColumnEngine

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DespachoMesPipeline:

    despacho_mes_repo: IntDespachoMesRepositoryImpl
    column_catalog: dict[str, Any]
    config: dict[str, Any] | None = None
    exporter: ExcelReportExporter | None = None

    def run(self, force: bool = False) -> PipelineResult:
        t0 = perf_counter()
        logger.info("=== DESPACHO MES pipeline start (force=%s) ===", force)

        logger.info("Stage 1 - LOAD int_despacho_bi (filtrado mes objetivo)")
        t = perf_counter()
        df_bi = self._load_despacho_bi()
        source_rows = len(df_bi)
        logger.info("filtrado: %d filas (%.2fs)", source_rows, perf_counter() - t)
        if source_rows == 0:
            logger.warning("int_despacho_bi vacio para el mes objetivo.")
            return PipelineResult(
                rows={"int_despacho_bi": 0, "agregado": 0, "int_despacho_mes": 0},
                duration_seconds=perf_counter() - t0,
            )

        logger.info("Stage 2 - LOAD lookups")
        t = perf_counter()
        lk = self._load_lookups()
        logger.info("Lookups: %s (%.2fs)",
                    ", ".join(f"{tabla}={len(df)}" for tabla, df in lk.items()),
                    perf_counter() - t)

        logger.info("Stage 3 - AGGREGATE")
        t = perf_counter()
        df = DespachoMesAggregateUseCase(config=self.config).execute(df_bi)
        aggregated_rows = len(df)
        logger.info("Agregado: %d filas (%.2fs)", aggregated_rows, perf_counter() - t)

        logger.info("Stage 4 - ENRICH (catálogo de columnas)")
        t = perf_counter()
        df = ColumnEngine(lookups=lk).apply(df, self.column_catalog)
        logger.info("Enrich completo (%.2fs)", perf_counter() - t)

        logger.info("Stage 5 - RULES")
        t = perf_counter()
        df = DespachoMesBusinessRulesUseCase(config=self.config).execute(df)
        logger.info("Reglas: %d filas finales (%.2fs)", len(df), perf_counter() - t)

        logger.info("Stage 6 - INT LOAD")
        t = perf_counter()
        int_rows = self.despacho_mes_repo.bulk_replace_from_df(df)
        logger.info("INT load: %d filas (%.2fs)", int_rows, perf_counter() - t)

        from itacamba_reportes.shared.control_corrida import (
            registrar_en_bd,
            resumen_corrida,
        )
        control = resumen_corrida(
            df, (self.config or {}).get("control"), reporte="despacho_mes")
        registrar_en_bd("despacho_mes", control)

        export_path: str | None = None
        if self.exporter is not None:
            logger.info("Stage 7 - EXPORT int_despacho_mes -> Excel")
            t = perf_counter()
            try:
                path = self.exporter.export(
                    DespachoMesIntModel.__tablename__, "DESPACHO_MES",
                    control=control,
                    encabezados=(self.config or {}).get("encabezados"),
                )
                export_path = str(path)
                logger.info("Export OK: %s (%.2fs)", export_path, perf_counter() - t)
            except Exception:
                logger.exception("Export de DESPACHO_MES fallo (datos ya en BD)")

        result = PipelineResult(
            rows={
                "int_despacho_bi": source_rows,
                "agregado": aggregated_rows,
                "int_despacho_mes": int_rows,
            },
            duration_seconds=perf_counter() - t0,
            export_path=export_path,
        )
        log_summary("DESPACHO MES", result)
        return result

    # ── helpers (filtro de mes objetivo, intactos) ────────────────────

    def _load_despacho_bi(self) -> pd.DataFrame:
        if _engine is None:
            raise RuntimeError("Engine SQLAlchemy no inicializado")

        df = pd.read_sql_table(DespachoBiIntModel.__tablename__, _engine)
        if df.empty or "anio" not in df.columns or "mes" not in df.columns:
            return df

        anio_all = pd.to_numeric(df["anio"], errors="coerce")
        mes_all = pd.to_numeric(df["mes"], errors="coerce")
        dist = (
            pd.DataFrame({"anio": anio_all, "mes": mes_all})
            .dropna().astype({"anio": int, "mes": int})
            .value_counts()
            .to_dict()
        )
        dist_str = ", ".join(
            f"{a:04d}-{m:02d}={n}" for (a, m), n in sorted(dist.items())
        ) or "(vacio)"
        logger.info("int_despacho_bi distribucion -> %s", dist_str)

        target = self._resolve_target_month(df)
        if target is None:
            logger.info("Filtro mes deshabilitado, %d filas", len(df))
            return df

        anio_t, mes_t = target
        mask = (anio_all == anio_t) & (mes_all == mes_t)
        filtered = df.loc[mask].reset_index(drop=True)

        if filtered.empty and dist:
            last = max(dist.keys())
            logger.warning(
                "MES filtro %04d-%02d -> 0 filas. Fallback a ultimo %04d-%02d (%d filas)",
                anio_t, mes_t, last[0], last[1], dist[last],
            )
            anio_t, mes_t = last
            mask = (anio_all == anio_t) & (mes_all == mes_t)
            filtered = df.loc[mask].reset_index(drop=True)

        logger.info("MES filtro %04d-%02d -> %d filas", anio_t, mes_t, len(filtered))
        return filtered

    def _resolve_target_month(self, df: pd.DataFrame) -> tuple[int, int] | None:
        raw = (self.config or {}).get("mes_objetivo", "auto")
        if raw is None:
            return None
        if isinstance(raw, dict) and "anio" in raw and "mes" in raw:
            return int(raw["anio"]), int(raw["mes"])
        if raw == "auto":
            target = self._auto_detect(df)
            if target is None:
                now = datetime.now()
                logger.warning("auto: sin data, fallback a %04d-%02d", now.year, now.month)
                return now.year, now.month
            logger.info("auto detecto = %04d-%02d", target[0], target[1])
            return target
        if raw == "current":
            now = datetime.now()
            return now.year, now.month
        return self._auto_detect(df)

    @staticmethod
    def _auto_detect(df: pd.DataFrame) -> tuple[int, int] | None:
        if df.empty or "anio" not in df.columns or "mes" not in df.columns:
            return None
        pairs = (
            pd.DataFrame({
                "anio": pd.to_numeric(df["anio"], errors="coerce"),
                "mes":  pd.to_numeric(df["mes"],  errors="coerce"),
            })
            .dropna().astype({"anio": int, "mes": int})
        )
        if pairs.empty:
            return None
        last = pairs.sort_values(["anio", "mes"]).iloc[-1]
        return int(last["anio"]), int(last["mes"])

    @staticmethod
    def _load_lookups() -> dict[str, pd.DataFrame]:
        """Lookups indexados por nombre de tabla SQL (los que usa el catálogo)."""
        modelos = (CarteraIntModel, AlmacenIntModel, SemanaIntModel)
        return {m.__tablename__: load_lookup_df(m) for m in modelos}


def build_pipeline(exporter: ExcelReportExporter | None = None) -> DespachoMesPipeline:
    """Composition root del reporte: carga config + catalogo del slice."""
    from itacamba_reportes.reportes.despacho_mes import load_catalog, load_config

    return DespachoMesPipeline(
        despacho_mes_repo=IntDespachoMesRepositoryImpl(),
        column_catalog=load_catalog(),
        config=load_config(),
        exporter=exporter,
    )
