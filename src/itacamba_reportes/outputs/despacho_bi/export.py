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
        centro_origen, ds_centro_origen, cod_material, material,
        fecha_salida, nro_pedido, cod_destinatario, nom_destinatario,
        poblacion, incoterm, clase_doc_ventas, centro_destino,
        ds_centro_destino, atributo_7, departamento_facturacion,
        clase_expedicion, vc_embalaje, cod_transportista, transportista,
        nombre_transportista, telefono_1, tipo_servicio_transporte,
        placa, tipo_vehiculo, cod_ruta, nom_ruta, distancia_km,
        numero_transporte, distancia, cantidad, despacho_t,
        departamento, traslados_t, mes, anio, grupo_producto,
        tipo_traslado, producto, centro_distribucion, link,
        provincia, semana_anio, traslados, zona_descarga, cd,
        localidad, tipo_venta, vendedor, desarrollador,
        codigo_cliente, equipo, localidad_im, incoterms_im,
        gerencia, semana, dia
    FROM int_despacho_bi
    ORDER BY dia DESC, nro_pedido;
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)

    return map_export_columns(df, DESPACHO_BI_MAPPING)


def export_despacho_bi() -> Path:
    logger.info("Exportando DESPACHO BI a Excel (56 columnas oficiales)...")
    df = get_despacho_bi_dataframe()
    exporter = ExcelReportExporter(EnvConfig.EXPORT_PATH)
    return exporter.export(df, "DESPACHO_BI")
