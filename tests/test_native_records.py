"""Equivalencia del fix de tipos nativos (optimización fast_executemany).

Verifica las DOS propiedades del cambio en coerce_dataframe_for_model y
dataframe_to_rows:

1. EQUIVALENCIA DE VALORES: los records tienen exactamente los mismos
   valores lógicos que producía el código anterior
   (df.astype(object).where(notna, None) / to_numpy + np.where).
2. TIPOS NATIVOS: ninguna celda es pd.Timestamp / np.int64 / np.float64 /
   np.bool_ — la condición para que pyodbc fast_executemany haga
   array-binding en un solo batch TDS.

Correr con: pytest tests/test_native_records.py -v
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import Column, DateTime, Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from itacamba_reportes.persistence.df_to_rows import dataframe_to_rows
from itacamba_reportes.persistence.type_coercion import (
    coerce_dataframe_for_model,
    dataframe_to_native_records,
)


class _Base(DeclarativeBase):
    ...


class _DemoModel(_Base):
    __tablename__ = "_demo_native"
    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(50))
    cantidad = Column(Numeric(18, 4))
    contador = Column(Integer)
    fecha = Column(DateTime)


def _dirty_df() -> pd.DataFrame:
    return pd.DataFrame({
        "nombre": [" Juan ", "#", None, "Ana", "N/A"],
        "cantidad": ["10,5", "x", None, "3.25", "7"],
        "contador": ["1", "2.0", "#", None, "5"],
        "fecha": ["01/02/2024", "#", None, "31/12/2023", "15/06/2025"],
        "columna_extra": ["a", "b", "c", "d", "e"],
    })


def _legacy_records(df: pd.DataFrame) -> list[dict]:
    """El patrón ANTERIOR (entregaba pd.Timestamp / np.int64)."""
    out = df.astype(object).where(pd.notna(df), None)
    return out.to_dict(orient="records")


NATIVE_OK = (str, int, float, bool, datetime, type(None))


def _assert_native(records: list[dict]) -> None:
    for i, rec in enumerate(records):
        for key, value in rec.items():
            assert type(value) in NATIVE_OK or (
                isinstance(value, datetime) and not isinstance(value, pd.Timestamp)
            ), f"fila {i} col {key}: tipo no nativo {type(value)} = {value!r}"
            assert not isinstance(value, pd.Timestamp), f"{key}: pd.Timestamp"
            assert not isinstance(value, (np.integer, np.floating, np.bool_)), (
                f"{key}: escalar numpy {type(value)}"
            )


def test_coerce_dataframe_native_and_equivalent():
    records = coerce_dataframe_for_model(_dirty_df(), _DemoModel)

    _assert_native(records)

    # columna_extra descartada (no está en el modelo)
    assert all("columna_extra" not in r for r in records)

    # equivalencia de valores con la semántica documentada
    assert [r["nombre"] for r in records] == ["Juan", None, None, "Ana", None]
    # NOTA: "10,5" (coma decimal) -> None es comportamiento PREEXISTENTE de la
    # versión vectorizada (pd.to_numeric no parsea coma); el reporte está
    # calibrado sobre esto. El fix de tipos nativos NO lo altera.
    assert [r["cantidad"] for r in records] == [None, None, None, 3.25, 7.0]
    assert [r["contador"] for r in records] == [1, 2, None, None, 5]
    assert [r["fecha"] for r in records] == [
        datetime(2024, 2, 1), None, None,
        datetime(2023, 12, 31), datetime(2025, 6, 15),
    ]


def test_dataframe_to_rows_native_and_equivalent():
    df = pd.DataFrame({
        "nombre": ["A", None, "C"],
        "contador": ["1", "2.6", None],          # int_col con float legitimo
        "cantidad": ["1.5", None, "2"],           # numeric col
        "fecha": ["02/03/2024", None, "#"],       # datetime col (dayfirst)
        "ignorada": ["x", "y", "z"],
    })
    rows = dataframe_to_rows(
        df, model=_DemoModel,
        int_cols=("contador",), datetime_cols=("fecha",), numeric_cols=("cantidad",),
    )

    _assert_native(rows)
    assert [r["contador"] for r in rows] == [1, 3, None]   # round() preservado
    assert [r["cantidad"] for r in rows] == [1.5, None, 2.0]
    assert rows[0]["fecha"] == datetime(2024, 3, 2)         # dayfirst preservado
    assert rows[1]["fecha"] is None and rows[2]["fecha"] is None
    assert all("ignorada" not in r for r in rows)


def test_native_records_equals_legacy_values():
    """Mismos VALORES que el patrón viejo, solo cambian los tipos Python."""
    df = pd.DataFrame({
        "s": pd.array(["a", None, "c"], dtype="string"),
        "i": pd.array([1, None, 3], dtype="Int64"),
        "f": pd.array([1.5, None, 2.5], dtype="Float64"),
        "d": pd.to_datetime(["2024-01-02", None, "2025-03-04"]),
        "o": ["x", np.nan, 7],
    })
    new = dataframe_to_native_records(df)
    old = _legacy_records(df)

    assert len(new) == len(old)
    for rn, ro in zip(new, old):
        for k in rn:
            vn, vo = rn[k], ro[k]
            if vo is None or vn is None:
                assert vn is None and vo is None, f"{k}: null mismatch {vn!r} {vo!r}"
            elif isinstance(vn, datetime):
                assert pd.Timestamp(vn) == pd.Timestamp(vo), k
            else:
                assert vn == vo, f"{k}: {vn!r} != {vo!r}"
    _assert_native(new)


def test_empty_df():
    assert dataframe_to_native_records(pd.DataFrame()) == []
    assert coerce_dataframe_for_model(pd.DataFrame(), _DemoModel) == []


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
