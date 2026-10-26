from __future__ import annotations

import logging
from time import perf_counter

from sqlalchemy import text

from itacamba_reportes.core.audit.tracker import record_execution
from itacamba_reportes.core.db.connection import engine
from itacamba_reportes.core.io.reader import FastExcelReader
from itacamba_reportes.core.settings import EnvConfig
from itacamba_reportes.core.state import has_file_changed, save_file_signature
from itacamba_reportes.inputs.cartera.ingest import CARTERA_SPEC, ingest_cartera
from itacamba_reportes.inputs.cartera.transform import transform_cartera

logger = logging.getLogger(__name__)


def run_pipeline(force: bool = False) -> dict[str, int]:
    t0 = perf_counter()
    logger.info("=== Iniciando pipeline CARTERA ===")
    try:
        reader = FastExcelReader(CARTERA_SPEC, EnvConfig.DATA_PATH)
        file_path = reader.resolve_path()

        if not force and not has_file_changed("cartera", file_path):
            with engine.connect() as conn:
                count = conn.execute(text("SELECT COUNT(*) FROM int_cartera")).scalar() or 0
            if count > 0:
                duration = perf_counter() - t0
                logger.info("CARTERA sin cambios detectados (%s, %d filas en BD). Omitiendo re-ingesta.", file_path.name, count)
                record_execution("cartera", "SUCCESS", count, duration, f"skipped_cache=True, rows={count}")
                return {"stg_cartera": 0, "int_cartera": count}

        stg_rows = ingest_cartera()
        int_rows = transform_cartera()
        save_file_signature("cartera", file_path)
        duration = perf_counter() - t0
        record_execution("cartera", "SUCCESS", int_rows, duration, f"stg={stg_rows}, int={int_rows}")
        logger.info("=== Pipeline CARTERA completado: %d filas en %.2fs ===", int_rows, duration)
        return {"stg_cartera": stg_rows, "int_cartera": int_rows}
    except Exception as exc:
        duration = perf_counter() - t0
        record_execution("cartera", "FAILED", 0, duration, str(exc))
        logger.exception("Error en pipeline CARTERA: %s", exc)
        raise
