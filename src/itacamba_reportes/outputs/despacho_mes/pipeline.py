from __future__ import annotations

import logging
from time import perf_counter

from itacamba_reportes.core.audit.tracker import record_execution
from itacamba_reportes.outputs.despacho_mes.transform import transform_despacho_mes
from itacamba_reportes.outputs.despacho_mes.export import export_despacho_mes

logger = logging.getLogger(__name__)


def run_pipeline(dia_corte: int | None = None, do_export: bool = True) -> dict[str, int]:
    t0 = perf_counter()
    logger.info("=== Iniciando pipeline DESPACHO MES (Resumen + Proyección) ===")
    try:
        affected_rows = transform_despacho_mes(dia_corte=dia_corte)
        export_file = export_despacho_mes() if do_export else None
        duration = perf_counter() - t0
        record_execution("despacho_mes", "SUCCESS", affected_rows, duration, f"affected={affected_rows}, export={export_file}")
        logger.info("=== Pipeline DESPACHO MES completado exitosamente: %d filas en %.2fs ===", affected_rows, duration)
        return {"int_despacho_mes": affected_rows}
    except Exception as exc:
        duration = perf_counter() - t0
        record_execution("despacho_mes", "FAILED", 0, duration, str(exc))
        logger.exception("Error en pipeline DESPACHO MES: %s", exc)
        raise
