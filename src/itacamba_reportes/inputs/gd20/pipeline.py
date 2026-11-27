from __future__ import annotations

import logging
from datetime import date
from time import perf_counter

from itacamba_reportes.core.audit.tracker import record_execution
from itacamba_reportes.core.db.connection import engine
from itacamba_reportes.core.io.reader import FastExcelReader
from itacamba_reportes.core.settings import EnvConfig
from itacamba_reportes.core.state import cached_table_rows_if_unchanged, save_file_signature
from itacamba_reportes.inputs.gd20.ingest import GD20_SPEC, ingest_gd20
from itacamba_reportes.inputs.gd20.transform import transform_gd20

logger = logging.getLogger(__name__)


def run_pipeline(
    corte_fecha: date | str | None = None,
    is_fin_de_mes: bool = False,
    fecha_desde: date | str | None = None,
    incluir_hasta: bool = False,
    force: bool = False,
) -> dict[str, int]:
    t0 = perf_counter()
    logger.info("=== Iniciando pipeline GD20 (BASE PANEL) ===")
    try:
        try:
            file_path = FastExcelReader(GD20_SPEC, EnvConfig.require_dynamic_inputs_path()).resolve_path()
        except FileNotFoundError:
            file_path = None

        cached_stg = cached_table_rows_if_unchanged("gd20", file_path, "stg_gd20", engine, force=force)
        if cached_stg is not None and file_path is not None:
            logger.info("GD20 sin cambios detectados (%s, %d filas en stg_gd20); ejecutando solo cruce SQL.", file_path.name, cached_stg)
            stg_rows = 0
        else:
            stg_rows = ingest_gd20()
            if file_path is not None:
                save_file_signature("gd20", file_path)

        int_rows = transform_gd20(
            corte_fecha=corte_fecha,
            is_fin_de_mes=is_fin_de_mes,
            fecha_desde=fecha_desde,
            incluir_hasta=incluir_hasta,
        )
        duration = perf_counter() - t0
        record_execution("gd20", "SUCCESS", int_rows, duration, f"stg={stg_rows}, int={int_rows}")
        logger.info("=== Pipeline GD20 completado exitosamente: %d filas en %.2fs ===", int_rows, duration)
        return {"stg_gd20": stg_rows, "int_gd20": int_rows}
    except Exception as exc:
        duration = perf_counter() - t0
        record_execution("gd20", "FAILED", 0, duration, str(exc))
        logger.exception("Error en pipeline GD20: %s", exc)
        raise
