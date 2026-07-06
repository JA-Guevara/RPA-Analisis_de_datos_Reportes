"""GD20 Mapping — renombre de columnas STG (raw SAP) a INT (lenguaje de negocio).

El SAP usa headers confusos: lo que llama "Cliente" es en realidad el
pagador, "Customer number (rebate reci..." es el destinatario, etc.

Los renames se cargan desde gd20.yaml:renames_stg_to_int. Si el archivo
o la sección no existen, usa los defaults hardcoded.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


_DEFAULT_RENAMES: dict[str, str] = {
    "cliente":           "pagador",
    "emisor_orden":      "emisor_solicitante",
    "customer_rebate":   "destinatario",
    "region":            "region_sap",
    "poblacion":         "poblacion_sap",
    "clave_pais_region": "clave_pais",
}


def apply_gd20_mapping(df: pd.DataFrame, config: dict | None = None) -> pd.DataFrame:
    if config is None:
        renames = _DEFAULT_RENAMES
    else:
        renames = config.get("renames_stg_to_int", _DEFAULT_RENAMES)
    applied = {k: v for k, v in renames.items() if k in df.columns}
    if applied:
        logger.info("GD20 mapping: %d cols renombradas STG->INT", len(applied))
    return df.rename(columns=renames)
