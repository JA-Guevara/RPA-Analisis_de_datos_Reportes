"""Despacho BI Mapping — selecciona el subset de int_query que viaja a INT.

int_query trae las cols heredadas de stg_query. Para Despacho BI usamos
solo las cols de negocio (descartando las técnicas tipo `telefono_1`,
`forwagent_accnt_g`, `placa`, etc.). El subset se define en
config["source_columns"] o cae al hardcoded.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


_DEFAULT_SOURCE_COLUMNS: tuple[str, ...] = (
    "centro_proveedor", "sucursal", "material", "nombre_material",
    "dia_natural", "documento_venta", "destinatario_mcia",
    "nombre_centro_destinatario", "poblacion", "incoterms",
    "clase_doc_ventas", "tipo_venta", "centro_receptor",
    "nombre_centro_receptor", "clase_expedicion", "vc_embalaje",
    "transportista", "nombre_transportista", "ruta", "nombre_ruta",
    "distancia", "cantidad", "fecha", "despacho_t", "departamento",
    "traslados_t", "dia", "mes", "anio", "grupo_producto",
    "tipo_traslado", "producto", "centro_distribucion", "provincia",
    "semana_anio", "zona_descarga", "cd", "localidad", "tipo_venta_2",
)
# NOTA: 'vendedor' y 'desarrollador' NO se heredan de int_query: en el
# QUERY raw actual (49 cols) no existen y en int_query van siempre NULL.
# En el cliente son formulas (AX/AY) que aca calcula el normalize
# (vendedor_cartera / desarrollador via lookups cartera + int_ref_equipo).


def apply_despacho_bi_mapping(df: pd.DataFrame, config: dict | None = None) -> pd.DataFrame:
    if config is None:
        cols: tuple[str, ...] = _DEFAULT_SOURCE_COLUMNS
    else:
        cfg = config.get("source_columns")
        cols = tuple(cfg) if cfg else _DEFAULT_SOURCE_COLUMNS

    keep = [c for c in cols if c in df.columns]
    missing = [c for c in cols if c not in df.columns]
    if missing:
        logger.warning(
            "Despacho BI mapping: faltan %d cols en int_query: %s",
            len(missing), missing,
        )
    logger.info("Despacho BI mapping: %d cols conservadas de int_query", len(keep))
    return df[keep].copy()
