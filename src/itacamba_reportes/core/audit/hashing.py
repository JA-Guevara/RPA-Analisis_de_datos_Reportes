from __future__ import annotations

import hashlib
from typing import Any, Mapping
import pandas as pd


def compute_row_hash(row: Mapping[str, Any] | pd.Series, columns: tuple[str, ...]) -> str:
    tokens = []
    for c in columns:
        v = row.get(c) if isinstance(row, dict) else row[c]
        if v is None or pd.isna(v):
            tokens.append("")
        elif isinstance(v, float):
            tokens.append(f"{v:.4f}")
        else:
            tokens.append(str(v).strip())
    raw = "|".join(tokens)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def add_hashes_to_df(df: pd.DataFrame, source_cols: tuple[str, ...], derived_cols: tuple[str, ...]) -> pd.DataFrame:
    valid_source = tuple(c for c in source_cols if c in df.columns)
    valid_derived = tuple(c for c in derived_cols if c in df.columns)

    df["source_hash"] = df.apply(lambda r: compute_row_hash(r, valid_source), axis=1)
    df["derived_hash"] = df.apply(lambda r: compute_row_hash(r, valid_derived), axis=1)
    df["full_hash"] = df.apply(lambda r: compute_row_hash(r, valid_source + valid_derived), axis=1)
    return df
