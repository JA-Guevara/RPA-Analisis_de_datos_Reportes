from __future__ import annotations

import logging
from time import perf_counter

from itacamba_reportes.core.audit.tracker import record_execution
from itacamba_reportes.core.db.connection import engine
from itacamba_reportes.core.state import cached_table_rows_if_unchanged, save_file_signature
from itacamba_reportes.inputs.proyeccion.ingest import ingest_proyeccion, resolve_proyeccion_path

logger = logging.getLogger(__name__)


def run_pipeline(force: bool = False) -> dict[str, int]:
    t0 = perf_counter()
    logger.info("=== Iniciando pipeline PROYECCIÓN ===")
    try:
        try:
            file_path = resolve_proyeccion_path()
        except FileNotFoundError:
            file_path = None

        cached_count = cached_table_rows_if_unchanged("proyeccion", file_path, "stg_proyeccion", engine, force=force)
        if cached_count is not None and file_path is not None:
            duration = perf_counter() - t0
            logger.info("PROYECCIÓN sin cambios detectados (%s, %d filas en BD). Omitiendo re-ingesta.", file_path.name, cached_count)
            record_execution("proyeccion", "SUCCESS", cached_count, duration, f"skipped_cache=True, rows={cached_count}")
            return {"stg_proyeccion": cached_count}

        stg_rows = ingest_proyeccion()
        if file_path is not None:
            save_file_signature("proyeccion", file_path)
        duration = perf_counter() - t0
        record_execution("proyeccion", "SUCCESS", stg_rows, duration, f"stg_proyeccion={stg_rows}")
        logger.info("=== Pipeline PROYECCIÓN completado: %d filas en %.2fs ===", stg_rows, duration)
        return {"stg_proyeccion": stg_rows}
    except Exception as exc:
        duration = perf_counter() - t0
        record_execution("proyeccion", "FAILED", 0, duration, str(exc))
        logger.exception("Error en pipeline PROYECCIÓN: %s", exc)
        raise
