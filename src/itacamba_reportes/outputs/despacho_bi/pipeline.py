from __future__ import annotations

import logging
from time import perf_counter
from typing import Any

from itacamba_reportes.core.audit.tracker import record_execution
from itacamba_reportes.outputs.despacho_bi.transform import transform_despacho_bi
from itacamba_reportes.outputs.despacho_bi.export import export_despacho_bi

logger = logging.getLogger(__name__)


def run_pipeline(do_export: bool = True, return_df: bool = False) -> dict[str, Any]:
    t0 = perf_counter()
    logger.info("=== Iniciando pipeline DESPACHO BI ===")
    try:
        affected_rows = transform_despacho_bi()
        export_file = None
        df = None
        if do_export:
            if return_df:
                export_file, df = export_despacho_bi(return_df=True)
            else:
                export_file = export_despacho_bi()
        duration = perf_counter() - t0
        record_execution("despacho_bi", "SUCCESS", affected_rows, duration, f"affected={affected_rows}, export={export_file}")
        logger.info("=== Pipeline DESPACHO BI completado exitosamente: %d filas en %.2fs ===", affected_rows, duration)
        res = {"int_despacho_bi": affected_rows}
        if return_df:
            res["df"] = df
        return res
    except Exception as exc:
        duration = perf_counter() - t0
        record_execution("despacho_bi", "FAILED", 0, duration, str(exc))
        logger.exception("Error en pipeline DESPACHO BI: %s", exc)
        raise
