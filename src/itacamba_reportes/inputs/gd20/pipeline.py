from __future__ import annotations

import logging
from datetime import date
from time import perf_counter

from itacamba_reportes.core.audit.tracker import record_execution
from itacamba_reportes.inputs.gd20.ingest import ingest_gd20
from itacamba_reportes.inputs.gd20.transform import transform_gd20

logger = logging.getLogger(__name__)


def run_pipeline(corte_fecha: date | str | None = None, is_fin_de_mes: bool = False) -> dict[str, int]:
    t0 = perf_counter()
    logger.info("=== Iniciando pipeline GD20 (BASE PANEL) ===")
    try:
        stg_rows = ingest_gd20()
        int_rows = transform_gd20(corte_fecha=corte_fecha, is_fin_de_mes=is_fin_de_mes)
        duration = perf_counter() - t0
        record_execution("gd20", "SUCCESS", int_rows, duration, f"stg={stg_rows}, int={int_rows}")
        logger.info("=== Pipeline GD20 completado exitosamente: %d filas en %.2fs ===", int_rows, duration)
        return {"stg_gd20": stg_rows, "int_gd20": int_rows}
    except Exception as exc:
        duration = perf_counter() - t0
        record_execution("gd20", "FAILED", 0, duration, str(exc))
        logger.exception("Error en pipeline GD20: %s", exc)
        raise
