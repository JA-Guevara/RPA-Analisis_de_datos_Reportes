from __future__ import annotations

from datetime import date
import logging
from time import perf_counter

from itacamba_reportes.core.audit.tracker import record_execution
from itacamba_reportes.core.db.connection import engine
from itacamba_reportes.core.io.reader import FastExcelReader
from itacamba_reportes.core.settings import EnvConfig
from itacamba_reportes.core.state import cached_table_rows_if_unchanged, save_file_signature
from itacamba_reportes.inputs.query.ingest import QUERY_SPEC, ingest_query
from itacamba_reportes.inputs.query.transform import transform_query

logger = logging.getLogger(__name__)


def run_pipeline(
    target_month: tuple[int, int] | None = None,
    corte_fecha: date | str | None = None,
    is_fin_de_mes: bool = False,
    incluir_hasta: bool = False,
    force: bool = False,
) -> dict[str, int]:
    t0 = perf_counter()
    logger.info("=== Iniciando pipeline QUERY (ZVCSD381) ===")
    try:
        try:
            file_path = FastExcelReader(QUERY_SPEC, EnvConfig.require_dynamic_inputs_path()).resolve_path()
        except FileNotFoundError:
            file_path = None

        cached_stg = cached_table_rows_if_unchanged("query", file_path, "stg_query", engine, force=force)
        if cached_stg is not None and file_path is not None:
            logger.info("QUERY sin cambios detectados (%s, %d filas en stg_query); ejecutando solo cruce SQL.", file_path.name, cached_stg)
            stg_rows = 0
        else:
            stg_rows = ingest_query()
            if file_path is not None:
                save_file_signature("query", file_path)

        int_rows = transform_query(
            target_month=target_month,
            corte_fecha=corte_fecha,
            is_fin_de_mes=is_fin_de_mes,
            incluir_hasta=incluir_hasta,
        )
        duration = perf_counter() - t0
        record_execution("query", "SUCCESS", int_rows, duration, f"stg={stg_rows}, int={int_rows}")
        logger.info("=== Pipeline QUERY completado: %d filas en %.2fs ===", int_rows, duration)
        return {"stg_query": stg_rows, "int_query": int_rows}
    except Exception as exc:
        duration = perf_counter() - t0
        record_execution("query", "FAILED", 0, duration, str(exc))
        logger.exception("Error en pipeline QUERY: %s", exc)
        raise
