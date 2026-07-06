"""Hashing columnar segmentado para detección O(1) de cambios.

Tres tipos de hash:
  - source_hash:  SHA256 de campos del SAP raw (49 cols). Cambia → SAP corrigió.
  - derived_hash: SHA256 de derivados volátiles (lookups). Cambia → QUERY/CARTERA cambió.
  - full_row_hash: SHA256 de toda la fila. Detecta cualquier diferencia.

Normalización aplicada:
  - None / NaN → token '\\0' (estable cross-Python)
  - float → redondeo a 4 decimales (evita drift por precisión)
  - string → strip + upper (insensitive a case y espacios)
  - datetime → ISO string truncado a segundos

El hash es DETERMINISTA: misma fila → mismo hash siempre. Compatible con
pandas Series, dicts y filas SQLAlchemy.
"""

from __future__ import annotations

import hashlib
import math
from datetime import date, datetime
from typing import Any, Mapping

import pandas as pd


# ─────────────────────────────────────────────────────────────────────────
# COLUMNAS QUE COMPONEN CADA HASH
# ─────────────────────────────────────────────────────────────────────────

# Campos del SAP raw. Si cualquiera cambia, SAP corrigió → SCD2 (nueva versión).
SOURCE_COLS: tuple[str, ...] = (
    "ejercicio", "sociedad", "organizacion_ventas",
    "centro", "division", "oficina_ventas",
    "canal_distribucion", "sector",
    "numero_cuenta", "centro_beneficio",
    "material", "unidad_medida_base", "periodo_contable",
    "clave_pais", "region_sap", "poblacion_sap",
    "grupo_vendedores",
    "pagador", "emisor_solicitante", "customer_bill_to", "destinatario",
    "grupo_clientes_2",
    "atributo_6", "atributo_7", "atributo_10",
    "clase_factura", "nombre_usuario", "texto",
    "numero_documento", "cantidad", "moneda_sociedad",
    "fe_contabilizacion", "fecha_entrada", "fecha_valor",
    "documento_comercial", "hora_entrada",
    "moneda_transaccion", "clave_moneda_transaccion",
    "moneda_fuerte", "clave_moneda_fuerte",
    "numero_doc_referencia", "numero_documento_2",
    "incoterms", "incoterms_parte_2", "clase_documento",
    "cond_pago", "dias_1", "numero_transporte", "e",
)

# Derivados volátiles. Dependen de QUERY/CARTERA/REFERENCIAS.
# Cambios acá → revisar sticky/rescue (NO versionar la fila).
DERIVED_COLS: tuple[str, ...] = (
    "tipo_embalaje", "nombre_producto", "volumen_toneladas",
    "nombre_pagador", "nombre_solicitante", "nombre_destinatario",
    "vendedor_sap", "vendedor", "vendedor_ok",
    "equipo", "gerencia",
    "canal", "sub_canal",
    "tipo_venta",
    "localidad", "provincia", "dpto", "region_m",
    "ingreso_bruto", "bonificaciones",
    "dpto_pagador", "localidad_pagador",
    "codigo_cliente",
    "centro_distribucion", "zona_entrega",
)


# ─────────────────────────────────────────────────────────────────────────
# NORMALIZACIÓN
# ─────────────────────────────────────────────────────────────────────────

_NULL_TOKEN = "\0"
_SEPARATOR = "|"


def _normalize(value: Any) -> str:
    """Convierte un valor en string determinístico, estable cross-tipo."""
    if value is None:
        return _NULL_TOKEN
    # NaN check (works for float, np.float64)
    if isinstance(value, float):
        if math.isnan(value):
            return _NULL_TOKEN
        # Redondeo a 4 decimales para evitar drift de precisión
        return f"{value:.4f}"
    # pd.NA, pd.NaT
    try:
        if pd.isna(value):
            return _NULL_TOKEN
    except (TypeError, ValueError):
        pass
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, (datetime, date, pd.Timestamp)):
        # Truncar a segundos para evitar diferencias por microsegundos
        if isinstance(value, pd.Timestamp):
            value = value.to_pydatetime()
        if isinstance(value, datetime):
            return value.replace(microsecond=0).isoformat()
        return value.isoformat()
    # Default: string normalizado (strip + upper)
    s = str(value).strip().upper()
    return s if s else _NULL_TOKEN


def _hash(values: list[str]) -> str:
    """SHA256 hexdigest de los valores ya normalizados."""
    joined = _SEPARATOR.join(values)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


# ─────────────────────────────────────────────────────────────────────────
# API PÚBLICA
# ─────────────────────────────────────────────────────────────────────────

def hash_columns(row: Mapping[str, Any], cols: tuple[str, ...]) -> str:
    """Computa el hash SHA256 de un subconjunto de columnas de una fila."""
    return _hash([_normalize(row.get(c)) for c in cols])


def hash_source(row: Mapping[str, Any]) -> str:
    """Hash de los campos SAP raw (49 cols). Cambio → SCD2 versiona."""
    return hash_columns(row, SOURCE_COLS)


def hash_derived(row: Mapping[str, Any]) -> str:
    """Hash de los campos derivados (lookups). Cambio → revisar sticky."""
    return hash_columns(row, DERIVED_COLS)


def hash_full(row: Mapping[str, Any]) -> str:
    """Hash de SAP + derivados combinados. Útil para chequeos de igualdad total."""
    all_cols = SOURCE_COLS + DERIVED_COLS
    return hash_columns(row, all_cols)


def add_hashes_to_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega 3 cols hash al DataFrame (source_hash, derived_hash, full_row_hash).

    Operación vectorizada: usa .apply con axis=1 (cada fila → 3 hashes).
    Para DataFrames grandes (>50k rows), considerar usar pandas .agg con groupby
    o procesar en chunks. Acá lo dejamos simple porque el volumen es ≈2k/mes.
    """
    df = df.copy()
    df["source_hash"]   = df.apply(lambda r: hash_source(r.to_dict()), axis=1)
    df["derived_hash"]  = df.apply(lambda r: hash_derived(r.to_dict()), axis=1)
    df["full_row_hash"] = df.apply(lambda r: hash_full(r.to_dict()), axis=1)
    return df
