from __future__ import annotations

import logging
from time import perf_counter

from itacamba_reportes.core.audit.tracker import record_execution
from itacamba_reportes.inputs.cartera.ingest import ingest_cartera
from itacamba_reportes.inputs.cartera.transform import transform_cartera

logger = logging.getLogger(__name__)


def run_pipeline() -> dict[str, int]:
    t0 = perf_counter()
    logger.info("=== Iniciando pipeline CARTERA ===")
    try:
        stg_rows = ingest_cartera()
        int_rows = transform_cartera()
        duration = perf_counter() - t0
        record_execution("cartera", "SUCCESS", int_rows, duration, f"stg={stg_rows}, int={int_rows}")
        logger.info("=== Pipeline CARTERA completado: %d filas en %.2fs ===", int_rows, duration)
        return {"stg_cartera": stg_rows, "int_cartera": int_rows}
    except Exception as exc:
        duration = perf_counter() - t0
        record_execution("cartera", "FAILED", 0, duration, str(exc))
        logger.exception("Error en pipeline CARTERA: %s", exc)
        raise
