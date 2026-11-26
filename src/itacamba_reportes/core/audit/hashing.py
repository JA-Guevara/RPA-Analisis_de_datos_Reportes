from __future__ import annotations

import hashlib
from typing import Any, Mapping
import pandas as pd


def _format_hash_value(v: Any) -> str:
    if v is None or pd.isna(v):
        return ""
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v).strip()


def _format_series_tokens(series: pd.Series) -> list[str]:
    if pd.api.types.is_float_dtype(series.dtype):
        return ["" if pd.isna(v) else f"{float(v):.4f}" for v in series.tolist()]
    return [_format_hash_value(v) for v in series.tolist()]


def _hash_joined_rows(col_lists: list[list[str]], row_count: int) -> list[str]:
    if row_count == 0:
        return []
    if not col_lists:
        empty_digest = hashlib.sha256(b"").hexdigest()
        return [empty_digest] * row_count
    sha256 = hashlib.sha256
    return [sha256("|".join(parts).encode("utf-8")).hexdigest() for parts in zip(*col_lists)]


def compute_row_hash(row: Mapping[str, Any] | pd.Series, columns: tuple[str, ...]) -> str:
    tokens = [
        _format_hash_value(row.get(c) if isinstance(row, dict) else row[c])
        for c in columns
    ]
    return hashlib.sha256("|".join(tokens).encode("utf-8")).hexdigest()


def add_hashes_to_df(df: pd.DataFrame, source_cols: tuple[str, ...], derived_cols: tuple[str, ...]) -> pd.DataFrame:
    valid_source = tuple(c for c in source_cols if c in df.columns)
    valid_derived = tuple(c for c in derived_cols if c in df.columns)
    row_count = len(df)

    # Formatear cada columna una sola vez por columnas unicas evita O(rows * cols) con df.apply
    formatted_cache: dict[str, list[str]] = {}
    for col in dict.fromkeys(valid_source + valid_derived):
        formatted_cache[col] = _format_series_tokens(df[col])

    src_lists = [formatted_cache[c] for c in valid_source]
    der_lists = [formatted_cache[c] for c in valid_derived]
    full_lists = src_lists + der_lists

    df["source_hash"] = _hash_joined_rows(src_lists, row_count)
    df["derived_hash"] = _hash_joined_rows(der_lists, row_count)
    df["full_hash"] = _hash_joined_rows(full_lists, row_count)
    return df
