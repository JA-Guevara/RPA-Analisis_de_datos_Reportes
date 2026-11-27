from __future__ import annotations

import logging
from time import perf_counter

from itacamba_reportes.core.audit.tracker import record_execution
from itacamba_reportes.core.db.connection import engine
from itacamba_reportes.core.state import cached_table_rows_if_unchanged, save_file_signature
from itacamba_reportes.inputs.referencias.ingest import ingest_referencias, resolve_referencias_path

logger = logging.getLogger(__name__)


def run_pipeline(force: bool = False) -> dict[str, int]:
    t0 = perf_counter()
    logger.info("=== Iniciando pipeline REFERENCIAS ===")
    try:
        try:
            file_path = resolve_referencias_path()
        except FileNotFoundError:
            file_path = None

        cached_count = cached_table_rows_if_unchanged("referencias", file_path, "int_ref_material", engine, force=force)
        if cached_count is not None and file_path is not None:
            duration = perf_counter() - t0
            logger.info("REFERENCIAS sin cambios detectados (%s). Omitiendo re-ingesta.", file_path.name)
            record_execution("referencias", "SUCCESS", cached_count, duration, f"skipped_cache=True, rows={cached_count}")
            return {"int_ref_material": cached_count}

        results = ingest_referencias()
        if file_path is not None:
            save_file_signature("referencias", file_path)
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
