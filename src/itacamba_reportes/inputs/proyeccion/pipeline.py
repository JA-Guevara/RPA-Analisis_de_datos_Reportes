from __future__ import annotations

import logging
from time import perf_counter

from itacamba_reportes.core.audit.tracker import record_execution
from itacamba_reportes.inputs.proyeccion.ingest import ingest_proyeccion

logger = logging.getLogger(__name__)


def run_pipeline() -> dict[str, int]:
    t0 = perf_counter()
    logger.info("=== Iniciando pipeline PROYECCIÓN ===")
    try:
        stg_rows = ingest_proyeccion()
        duration = perf_counter() - t0
        record_execution("proyeccion", "SUCCESS", stg_rows, duration, f"stg_proyeccion={stg_rows}")
        logger.info("=== Pipeline PROYECCIÓN completado: %d filas en %.2fs ===", stg_rows, duration)
        return {"stg_proyeccion": stg_rows}
    except Exception as exc:
        duration = perf_counter() - t0
        record_execution("proyeccion", "FAILED", 0, duration, str(exc))
        logger.exception("Error en pipeline PROYECCIÓN: %s", exc)
        raise
