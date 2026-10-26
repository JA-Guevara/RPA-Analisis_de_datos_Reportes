from __future__ import annotations

import logging
from pathlib import Path
import shutil

from itacamba_reportes.core.io.exporter import ExcelReportExporter
from itacamba_reportes.core.settings import EnvConfig
from itacamba_reportes.outputs.ventas_bi.export import get_ventas_bi_dataframe
from itacamba_reportes.outputs.despacho_bi.export import get_despacho_bi_dataframe

logger = logging.getLogger(__name__)


def export_historial_ventas(
    df_ventas: pd.DataFrame | None = None,
    df_despachos: pd.DataFrame | None = None,
    target_dir: Path | None = None,
    file_name: str = "HISTORIAL VENTAS.xlsx",
) -> Path:
    logger.info("Exportando HISTORIAL VENTAS consolidado (hojas VENTAS y DESPACHOS) para Power BI...")
    if df_ventas is None:
        df_ventas = get_ventas_bi_dataframe()
    else:
        logger.info("Reutilizando DataFrame de VENTAS BI en memoria (0 consultas duplicadas a BD)")

    if df_despachos is None:
        df_despachos = get_despacho_bi_dataframe()
    else:
        logger.info("Reutilizando DataFrame de DESPACHO BI en memoria (0 consultas duplicadas a BD)")

    out_dir = target_dir or EnvConfig.EXPORT_PATH
    exporter = ExcelReportExporter(out_dir)
    target = exporter.export_multi_sheet(
        sheets={
            "VENTAS": df_ventas,
            "DESPACHOS": df_despachos,
        },
        file_name=file_name,
        timestamped=False,
    )

    # Si existe una carpeta de fijos en DATA_PATH, actualizar tambien alli para mantener Power BI conectado
    fijos_dir = EnvConfig.DATA_PATH / "fijos"
    if fijos_dir.exists():
        fijos_target = fijos_dir / file_name
        try:
            if fijos_target.resolve() != target.resolve():
                shutil.copy2(target, fijos_target)
                logger.info("Copia sincronizada de HISTORIAL VENTAS en fijos: %s", fijos_target)
        except Exception as exc:
            logger.warning("No se pudo sincronizar copia en fijos (%s): %s", fijos_target, exc)

    return target
