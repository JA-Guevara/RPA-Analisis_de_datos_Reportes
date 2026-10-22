from __future__ import annotations

import logging
from time import perf_counter

from itacamba_reportes.core.audit.tracker import record_execution
from itacamba_reportes.inputs.referencias.ingest import ingest_referencias

logger = logging.getLogger(__name__)


def run_pipeline() -> dict[str, int]:
    t0 = perf_counter()
    logger.info("=== Iniciando pipeline REFERENCIAS ===")
    try:
        results = ingest_referencias()
        duration = perf_counter() - t0
        total_rows = sum(results.values())
        record_execution("referencias", "SUCCESS", total_rows, duration, str(results))
        logger.info("=== Pipeline REFERENCIAS completado exitosamente: %d filas en %.2fs ===", total_rows, duration)
        return results
    except Exception as exc:
        duration = perf_counter() - t0
        record_execution("referencias", "FAILED", 0, duration, str(exc))
        logger.exception("Error en pipeline REFERENCIAS: %s", exc)
        raise
