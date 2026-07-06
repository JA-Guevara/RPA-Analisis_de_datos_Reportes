"""Coercion de tipos Python para inserts bulk con pyodbc fast_executemany.

pyodbc activa la ruta rapida (un unico batch TDS) solo cuando todas las filas
del executemany llegan con tipos Python uniformes y compatibles con la columna
SQL declarada. Si una columna mezcla str/int/None, o llega `pandas.Timestamp`
en una columna DATETIME, fast_executemany cae a inserts fila por fila.

Este modulo introspecciona el modelo SQLAlchemy y normaliza cada dict a:
    int, str, datetime.datetime, None.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from datetime import date, datetime
from re import escape as re_escape
from typing import Any

import pandas as pd
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    Numeric,
    SmallInteger,
    String,
)

from itacamba_reportes.shared.null_tokens import NULL_TOKENS


_INT_TYPES: tuple[type, ...] = (Integer, BigInteger, SmallInteger)
_FLOAT_TYPES: tuple[type, ...] = (Float, Numeric)
_DATE_TYPES: tuple[type, ...] = (DateTime, Date)


def _is_null(value: Any) -> bool:
    """True si value es null o un token SAP de null ('#', 'N/A', etc.)."""
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if value is pd.NaT:
        return True
    if isinstance(value, str) and value.strip() in NULL_TOKENS:
        return True
    return False


def _to_int(value: Any) -> int | None:
    if _is_null(value):
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        try:
            return int(float(text))
        except ValueError:
            return None


def _to_str(value: Any) -> str | None:
    if _is_null(value):
        return None
    text = str(value).strip()
    return text or None


def _to_datetime(value: Any) -> datetime | None:
    if _is_null(value):
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    ts = pd.to_datetime(value, errors="coerce", dayfirst=True)
    if pd.isna(ts):
        return None
    return ts.to_pydatetime()


def _to_float(value: Any) -> float | None:
    if _is_null(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _to_bool(value: Any) -> bool | None:
    if _is_null(value):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y", "si", "sí"}:
        return True
    if text in {"0", "false", "f", "no", "n"}:
        return False
    return None


def _coerce_value(value: Any, column_type: Any) -> Any:
    if isinstance(column_type, _INT_TYPES):
        return _to_int(value)
    if isinstance(column_type, _DATE_TYPES):
        return _to_datetime(value)
    if isinstance(column_type, _FLOAT_TYPES):
        return _to_float(value)
    if isinstance(column_type, Boolean):
        return _to_bool(value)
    if isinstance(column_type, String):
        return _to_str(value)
    return None if _is_null(value) else value


def coerce_rows_for_model(
    rows: Iterable[dict[str, Any]],
    model: type,
) -> list[dict[str, Any]]:
    """Normaliza tipos Python de cada dict segun la metadata del modelo SQLAlchemy.

    Las claves no presentes en `model.__table__.columns` se descartan.

    NOTA: Para volumenes >5k filas usar `coerce_dataframe_for_model` que es
    50-100x mas rapido (vectorizado en pandas vs loop Python con isinstance).
    """
    columns = {col.name: col.type for col in model.__table__.columns}
    coerced: list[dict[str, Any]] = []
    for row in rows:
        out: dict[str, Any] = {}
        for key, value in row.items():
            col_type = columns.get(key)
            if col_type is None:
                continue
            out[key] = _coerce_value(value, col_type)
        coerced.append(out)
    return coerced


def coerce_dataframe_for_model(
    df: pd.DataFrame,
    model: type,
) -> list[dict[str, Any]]:
    """Version vectorizada de coerce_rows_for_model. Misma semantica, 50-100x mas rapida.

    Aplica la coercion a NIVEL DE COLUMNA con operaciones pandas/numpy (sin
    iterar fila por fila en Python puro). Las cols que no existen en el modelo
    se descartan. NaN/NaT se convierten a Python None explicito (evita el
    bug pyodbc 22003).

    Tipos manejados:
      - Integer/BigInteger/SmallInteger -> pd.to_numeric(.round().Int64) -> int|None
      - Numeric/Float                   -> pd.to_numeric() -> float|None
      - DateTime/Date                   -> pd.to_datetime(dayfirst=True) -> datetime|None
      - String                          -> str(...).strip() o None
      - Boolean                         -> True/False/None

    Returns: list[dict] listo para session.execute(insert(Model), out).
    """
    if df.empty:
        return []

    columns = {col.name: col.type for col in model.__table__.columns}

    # Filtrar cols que existen en el modelo (descarta extras del Excel)
    keep_cols = [c for c in df.columns if c in columns]
    if not keep_cols:
        return []
    df = df[keep_cols].copy()

    # Normalizar tokens SAP de null ('#', 'N/A', 'NULL', '') -> NaN
    # antes de la coercion de tipos, para que pd.to_numeric/datetime los maneje.
    null_pat = "|".join(re_escape(t) for t in NULL_TOKENS if isinstance(t, str))
    if null_pat:
        for c in df.columns:
            if df[c].dtype == object or pd.api.types.is_string_dtype(df[c]):
                s = df[c].astype("string")
                s = s.str.strip()
                # Pasar tokens null y string vacio a NA
                s = s.mask(s.str.fullmatch(null_pat, na=False))
                s = s.mask(s == "")
                df[c] = s

    for col_name in df.columns:
        col_type = columns[col_name]
        s = df[col_name]

        if isinstance(col_type, _INT_TYPES):
            df[col_name] = (
                pd.to_numeric(s, errors="coerce")
                .round()
                .astype("Int64")
            )
        elif isinstance(col_type, _FLOAT_TYPES):
            df[col_name] = pd.to_numeric(s, errors="coerce").astype("Float64")
        elif isinstance(col_type, _DATE_TYPES):
            df[col_name] = pd.to_datetime(s, errors="coerce", dayfirst=True)
        elif isinstance(col_type, Boolean):
            # Map vectorizado de strings a bool nullable
            mapped = (
                s.astype("string").str.strip().str.lower()
                .map({
                    "1": True, "true": True, "t": True, "yes": True, "y": True,
                    "si": True, "sí": True,
                    "0": False, "false": False, "f": False, "no": False, "n": False,
                })
            )
            df[col_name] = mapped.astype("boolean")
        elif isinstance(col_type, String):
            df[col_name] = s.astype("string").str.strip()
        # otros tipos: dejar tal cual

    # Tipos Python NATIVOS por celda (datetime, int, float, str, None).
    # CRITICO para rendimiento: pd.Timestamp / np.int64 / np.float64 rompen
    # el array-binding de pyodbc fast_executemany y degradan el insert a
    # fila-por-fila (medido: stg_query 437 filas/s vs ~3.800 con nativos).
    return dataframe_to_native_records(df)

# ──────────────────────────────────────────────────────────────────────
# Conversión a tipos Python nativos (la condición de fast_executemany)
# ──────────────────────────────────────────────────────────────────────

def _series_to_native(s: pd.Series) -> list[Any]:
    """Serie -> lista de escalares Python nativos (None para nulls).

    Garantiza que pyodbc reciba datetime/int/float/str/bool puros:
    - datetime64[ns] -> datetime.datetime (no pd.Timestamp)
    - Int64/int64    -> int               (no np.int64)
    - Float64/float64-> float             (no np.float64)
    - boolean/bool   -> bool              (no np.bool_)
    - string/object  -> str / valor original

    VECTORIZADO: la máscara de nulls se calcula una sola vez en C
    (s.isna()) y las conversiones van por numpy — nada de pd.isna()
    por celda (con ~3M de celdas eso costaba segundos de CPU).
    """
    dtype = s.dtype
    mask = s.isna().to_numpy()

    if pd.api.types.is_datetime64_any_dtype(dtype):
        # datetime64[ns] -> datetime64[us] -> datetime.datetime nativo.
        # .item() de datetime64[us] devuelve datetime puro (API estable
        # en numpy/pandas 2.x y 3.x, sin pasar por pd.Timestamp).
        arr = s.to_numpy(dtype="datetime64[us]")
        return [None if m else v.item() for m, v in zip(mask, arr)]

    if pd.api.types.is_integer_dtype(dtype):
        arr = s.to_numpy(dtype="float64", na_value=float("nan"))
        return [None if m else int(v) for m, v in zip(mask, arr)]

    if pd.api.types.is_float_dtype(dtype):
        arr = s.to_numpy(dtype="float64", na_value=float("nan"))
        return [None if m else float(v) for m, v in zip(mask, arr)]

    if pd.api.types.is_bool_dtype(dtype):
        arr = s.to_numpy(dtype=object)
        return [None if m else bool(v) for m, v in zip(mask, arr)]

    if pd.api.types.is_string_dtype(dtype) and not pd.api.types.is_object_dtype(dtype):
        arr = s.to_numpy(dtype=object)
        return [None if m else str(v) for m, v in zip(mask, arr)]

    # object / mixto: preservar el valor, nativizando escalares conocidos
    arr = s.to_numpy(dtype=object)
    out: list[Any] = []
    for m, v in zip(mask, arr):
        if m or v is None:
            out.append(None)
        elif isinstance(v, pd.Timestamp):
            out.append(v.to_pydatetime())
        elif isinstance(v, float):
            out.append(float(v))
        elif isinstance(v, bool):
            out.append(bool(v))
        elif isinstance(v, int):
            out.append(int(v))
        else:
            out.append(v)
    return out


def dataframe_to_native_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """DataFrame -> list[dict] con escalares Python nativos y None en nulls.

    Reemplaza el patrón `df.astype(object).where(pd.notna(df), None)
    .to_dict("records")`, que entregaba pd.Timestamp/np.int64 y rompía
    la ruta rápida de pyodbc (ver docstring del módulo).
    """
    if df.empty:
        return []
    cols = list(df.columns)
    native = [_series_to_native(df[c]) for c in cols]
    return [dict(zip(cols, row)) for row in zip(*native)]
