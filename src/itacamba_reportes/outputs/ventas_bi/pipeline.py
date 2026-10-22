from __future__ import annotations

import logging
from time import perf_counter

from itacamba_reportes.core.audit.tracker import record_execution
from itacamba_reportes.outputs.ventas_bi.transform import upsert_ventas_bi_scd2
from itacamba_reportes.outputs.ventas_bi.export import export_ventas_bi

logger = logging.getLogger(__name__)


def run_pipeline(force_rebuild: bool = False, do_export: bool = True) -> dict[str, int]:
    t0 = perf_counter()
    logger.info("=== Iniciando pipeline VENTAS BI (Histórico SCD2) ===")
    try:
        affected_rows = upsert_ventas_bi_scd2(force_rebuild=force_rebuild)
        export_file = export_ventas_bi() if do_export else None
        duration = perf_counter() - t0
        record_execution("ventas_bi", "SUCCESS", affected_rows, duration, f"affected={affected_rows}, export={export_file}")
        logger.info("=== Pipeline VENTAS BI completado exitosamente: %d filas en %.2fs ===", affected_rows, duration)
        return {"int_ventas_bi": affected_rows}
    except Exception as exc:
        duration = perf_counter() - t0
        record_execution("ventas_bi", "FAILED", 0, duration, str(exc))
        logger.exception("Error en pipeline VENTAS BI: %s", exc)
        raise
