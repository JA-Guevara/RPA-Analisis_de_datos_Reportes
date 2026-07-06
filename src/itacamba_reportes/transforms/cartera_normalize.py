"""Normalize CARTERA - driven by YAML."""

from __future__ import annotations

import logging
from typing import Callable

import pandas as pd

from itacamba_reportes.config.dataset_spec import (
    DatasetSpec,
    DtypeSpec,
    TransformSpec,
)
from itacamba_reportes.shared.pandas_utils import (
    apply_rename_by_position,
)

logger = logging.getLogger(__name__)


_DTYPE_COERCERS: dict[str, Callable[[pd.Series], pd.Series]] = {
    "Int64":   lambda s: pd.to_numeric(s, errors="coerce").astype("Int64"),
    "float64": lambda s: pd.to_numeric(s, errors="coerce").astype("float64"),
    "string":  lambda s: s.astype("string"),
}


def _coerce_datetime(series: pd.Series, *, dayfirst: bool = True) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", dayfirst=dayfirst)


_TRANSFORM_OPS: dict[str, Callable[[pd.Series, TransformSpec], pd.Series]] = {
    "uppercase": lambda s, _t: s.astype("string").str.upper(),
    "lowercase": lambda s, _t: s.astype("string").str.lower(),
    "strip":     lambda s, _t: s.astype("string").str.strip(),
    "replace":   lambda s, t:  s.replace(t.map) if t.map else s,
}


class NormalizeCarteraFromSpec:

    def __init__(self, spec: DatasetSpec) -> None:
        self._spec = spec

    def execute(self, df: pd.DataFrame) -> pd.DataFrame:
        logger.info("Normalize %s start: %d filas x %d cols",
                    self._spec.dataset, len(df), len(df.columns))
        df = df.copy()
        df = apply_rename_by_position(df, self._spec.rename_by_position)
        df = self._cast_types(df)
        df = self._apply_transforms(df)
        logger.info("Normalize %s end: %d filas x %d cols",
                    self._spec.dataset, len(df), len(df.columns))
        return df

    def _cast_types(self, df: pd.DataFrame) -> pd.DataFrame:
        for col, dtype in self._spec.dtypes.items():
            if col not in df.columns:
                logger.warning("Col '%s' no existe, skip cast", col)
                continue
            df[col] = self._coerce(df[col], dtype)
        return df

    @staticmethod
    def _coerce(series: pd.Series, dtype: str | DtypeSpec) -> pd.Series:
        if isinstance(dtype, DtypeSpec):
            if dtype.type == "datetime":
                return _coerce_datetime(series, dayfirst=dtype.dayfirst)
            return NormalizeCarteraFromSpec._coerce_simple(series, dtype.type)
        return NormalizeCarteraFromSpec._coerce_simple(series, dtype)

    @staticmethod
    def _coerce_simple(series: pd.Series, dtype: str) -> pd.Series:
        coercer = _DTYPE_COERCERS.get(dtype)
        if coercer is not None:
            return coercer(series)
        if dtype.startswith("datetime"):
            return _coerce_datetime(series)
        return series.astype(dtype, errors="ignore")

    def _apply_transforms(self, df: pd.DataFrame) -> pd.DataFrame:
        for t in self._spec.transforms:
            df = self._apply_one(df, t)
        return df

    @staticmethod
    def _apply_one(df: pd.DataFrame, t: TransformSpec) -> pd.DataFrame:
        if t.column not in df.columns:
            logger.warning("Col '%s' no existe, skip op=%s", t.column, t.op)
            return df
        op_fn = _TRANSFORM_OPS.get(t.op)
        if op_fn is None:
            return df
        df[t.column] = op_fn(df[t.column], t)
        return df
