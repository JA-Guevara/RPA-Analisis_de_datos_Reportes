from __future__ import annotations

import logging
from pathlib import Path
import pandas as pd

from itacamba_reportes.core.db.connection import engine
from itacamba_reportes.core.io.column_mappings import DESPACHO_BI_MAPPING, map_export_columns
from itacamba_reportes.core.io.exporter import ExcelReportExporter
from itacamba_reportes.core.settings import EnvConfig

logger = logging.getLogger(__name__)


def get_despacho_bi_dataframe() -> pd.DataFrame:
    query = """
    SELECT 
        centro_origen, centro_destino, cod_material, material,
        fecha_salida, nro_pedido, cod_destinatario, nom_destinatario,
        incoterm, cod_ruta, nom_ruta, despacho_t, traslados_t,
        dia, mes, anio, centro_distribucion, localidad, departamento,
        codigo_cliente, nombre_cliente, vendedor, desarrollador,
        equipo, gerencia, canal, localidad_im, semana
    FROM int_despacho_bi
    ORDER BY dia DESC, nro_pedido;
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)

    return map_export_columns(df, DESPACHO_BI_MAPPING)


def export_despacho_bi() -> Path:
    logger.info("Exportando DESPACHO BI a Excel...")
    df = get_despacho_bi_dataframe()
    exporter = ExcelReportExporter(EnvConfig.EXPORT_PATH)
    return exporter.export(df, "DESPACHO_BI")
