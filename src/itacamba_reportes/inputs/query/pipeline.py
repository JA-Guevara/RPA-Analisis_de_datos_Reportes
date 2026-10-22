from __future__ import annotations

import logging
from time import perf_counter

from itacamba_reportes.core.audit.tracker import record_execution
from itacamba_reportes.inputs.query.ingest import ingest_query
from itacamba_reportes.inputs.query.transform import transform_query

logger = logging.getLogger(__name__)


def run_pipeline() -> dict[str, int]:
    t0 = perf_counter()
    logger.info("=== Iniciando pipeline QUERY (ZBCS) ===")
    try:
        stg_rows = ingest_query()
        int_rows = transform_query()
        duration = perf_counter() - t0
        record_execution("query", "SUCCESS", int_rows, duration, f"stg={stg_rows}, int={int_rows}")
        logger.info("=== Pipeline QUERY completado: %d filas en %.2fs ===", int_rows, duration)
        return {"stg_query": stg_rows, "int_query": int_rows}
    except Exception as exc:
        duration = perf_counter() - t0
        record_execution("query", "FAILED", 0, duration, str(exc))
        logger.exception("Error en pipeline QUERY: %s", exc)
        raise
