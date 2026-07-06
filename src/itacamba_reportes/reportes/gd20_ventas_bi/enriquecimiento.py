"""Enriquecimiento GD20 — orquesta catálogo declarativo + reglas Python.

Orden CALIBRADO (paridad byte a byte verificada contra el flujo
anterior normalize+business_rules en Fase 4 del plan 2026-07-06):

    1. columnas.yaml (ColumnEngine): cartera x3 llaves, material,
       equipo condicional, almacén, centro, tipo_embalaje, region_m
    2. Gd20CdZeRule: centro_distribucion + zona_entrega (stg_query)
    3. CentroOverridesRule: overrides por centro (config.yaml)
    4. NombreDestQueryRule: solo si config lo activa (OFF default)
    5. Gd20BusinessRulesUseCase: ingreso_bruto, fechas, volumen,
       bonificaciones, post_replaces
"""

from __future__ import annotations

import pandas as pd

from itacamba_reportes.reportes.gd20_ventas_bi import load_catalog
from itacamba_reportes.reportes.gd20_ventas_bi.reglas import (
    CentroOverridesRule,
    Gd20BusinessRulesUseCase,
    Gd20CdZeRule,
    NombreDestQueryRule,
)
from itacamba_reportes.transforms.column_engine import ColumnEngine


def enrich_gd20(
    df: pd.DataFrame,
    config: dict | None,
    *,
    cartera_df: pd.DataFrame,
    equipo_df: pd.DataFrame,
    almacen_df: pd.DataFrame,
    material_df: pd.DataFrame,
    centro_df: pd.DataFrame,
    query_df: pd.DataFrame,
    localidad_df: pd.DataFrame,
) -> pd.DataFrame:
    lookups = {
        "int_cartera": cartera_df,
        "int_ref_equipo": equipo_df,
        "int_ref_almacen": almacen_df,
        "int_ref_material": material_df,
        "int_ref_centro": centro_df,
        "int_ref_localidad": localidad_df,
    }
    df = ColumnEngine(lookups=lookups).apply(df, load_catalog())
    df = Gd20CdZeRule(query_df=query_df, centro_df=centro_df,
                      config=config).execute(df)
    df = CentroOverridesRule(config=config).execute(df)
    if (config or {}).get("override_nombre_dest_from_query", False):
        df = NombreDestQueryRule(query_df=query_df).execute(df)
    df = Gd20BusinessRulesUseCase(config=config).execute(df)
    return df
