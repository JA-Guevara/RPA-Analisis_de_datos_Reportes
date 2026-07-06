"""RunAllOrchestrator — ejecución secuencial fail-fast de todos los pipelines.

DAG de dependencias:

    references ─┐
                │
    cartera ────┼──► gd20  (lee int_cartera, int_ref_*, stg_query)
                │      │
    query ──────┤      └──► UPSERT int_ventas_bi  (REPORTE VENTAS BI)
                │
                ├──► despacho_bi  (lee int_query + lookups)
                │           │
                │           └──► despacho_mes     (REPORTE DESPACHOS)

Secuencial y fail-fast: si un pipeline lanza excepción, sube al CLI y
no corren los siguientes (gd20 no debe correr con catálogos inválidos).
Cada pipeline mantiene su propia change-detection.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from time import perf_counter

from itacamba_reportes.persistence.lookups import clear_lookup_cache
from itacamba_reportes.pipelines.cartera import CarteraPipeline
from itacamba_reportes.reportes.despacho_bi.pipeline import DespachoBiPipeline
from itacamba_reportes.reportes.despacho_mes.pipeline import DespachoMesPipeline
from itacamba_reportes.pipelines.gd20 import Gd20Pipeline
from itacamba_reportes.pipelines.query import QueryPipeline
from itacamba_reportes.pipelines.references import ReferencesPipeline
from itacamba_reportes.pipelines.runner import PipelineResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RunAllResult:
    results: dict[str, PipelineResult]   # nombre -> resultado, en orden de corrida
    total_seconds: float

    @property
    def skipped(self) -> bool:
        return all(r.skipped for r in self.results.values())


@dataclass(slots=True)
class RunAllOrchestrator:

    references_pipeline: ReferencesPipeline
    cartera_pipeline: CarteraPipeline
    query_pipeline: QueryPipeline
    gd20_pipeline: Gd20Pipeline
    despacho_bi_pipeline: DespachoBiPipeline
    despacho_mes_pipeline: DespachoMesPipeline

    def run(
        self,
        *,
        run_id: datetime | None = None,
        force: bool = False,
    ) -> RunAllResult:
        run_id = run_id or datetime.now()
        t0 = perf_counter()
        clear_lookup_cache()

        sep = "=" * 80
        logger.info(sep)
        logger.info("RUN-ALL pipeline start (sequential, fail-fast, force=%s)", force)
        logger.info("Run ID: %s", run_id.isoformat())
        logger.info(sep)

        results: dict[str, PipelineResult] = {}

        logger.info(">>> Stage 1/6: REFERENCES")
        results["references"] = self.references_pipeline.run(force=force)
        self._log_stage_done("REFERENCES", results["references"])

        logger.info(">>> Stage 2/6: CARTERA")
        results["cartera"] = self.cartera_pipeline.run(run_id=run_id, force=force)
        self._log_stage_done("CARTERA", results["cartera"])

        logger.info(">>> Stage 3/6: QUERY (stg_query + int_query)")
        results["query"] = self.query_pipeline.run(force=force)
        self._log_stage_done("QUERY", results["query"])

        logger.info(">>> Stage 4/6: GD20 (+ UPSERT int_ventas_bi) [VENTAS BI]")
        results["gd20"] = self.gd20_pipeline.run(force=force)
        self._log_stage_done("GD20", results["gd20"])

        logger.info(">>> Stage 5/6: DESPACHO BI (int_query -> int_despacho_bi)")
        results["despacho_bi"] = self.despacho_bi_pipeline.run(force=force)
        self._log_stage_done("DESPACHO BI", results["despacho_bi"])

        logger.info(">>> Stage 6/6: DESPACHO MES (int_despacho_bi -> int_despacho_mes)")
        results["despacho_mes"] = self.despacho_mes_pipeline.run(force=force)
        self._log_stage_done("DESPACHO MES", results["despacho_mes"])

        duration = perf_counter() - t0
        result = RunAllResult(results=results, total_seconds=duration)
        self._log_summary(result)
        return result

    @staticmethod
    def _log_stage_done(name: str, result: PipelineResult) -> None:
        status = "SKIPPED" if result.skipped else "OK"
        logger.info("    %s: %s (%.2fs)", name, status, result.duration_seconds)

    @staticmethod
    def _log_summary(result: RunAllResult) -> None:
        sep = "=" * 80
        logger.info(sep)
        logger.info("RUN-ALL RESUMEN CONSOLIDADO")
        logger.info(sep)
        for name, res in result.results.items():
            status = "SKIPPED" if res.skipped else "OK"
            rows = ", ".join(f"{k}={v}" for k, v in res.rows.items()) or "-"
            logger.info("  %-14s %-8s %s  (%.2fs)", name, status, rows,
                        res.duration_seconds)
        logger.info("  " + "-" * 76)
        logger.info("  %-14s %38.2fs", "TOTAL", result.total_seconds)
        logger.info(sep)
