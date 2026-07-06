"""Helper compartido para convertir DataFrame -> list[dict] para insert bulk.

Centraliza la coercion de tipos antes de pyodbc.fast_executemany para
evitar bugs como el 22003 (Numeric value out of range) que ocurre cuando
np.nan / pd.NaT / pd.Timestamp se cuelan donde se espera Python None /
datetime.

Uso tipico desde un repo:

    from itacamba_reportes.persistence.df_to_rows import (
        dataframe_to_rows,
    )

    rows = dataframe_to_rows(
        df,
        model=CarteraIntModel,
        int_cols=("cliente", "contador"),
        datetime_cols=("fecha_inclusion",),
        numeric_cols=(),
    )

Funcion auxiliar `df_to_records_nullable` sin coercion de tipos (para
persistencia raw a STG donde la tabla no tiene constraints estrictos).
"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from itacamba_reportes.persistence.type_coercion import (
    dataframe_to_native_records,
)


def dataframe_to_rows(
    df: pd.DataFrame,
    *,
    model: type,
    int_cols: Iterable[str] = (),
    datetime_cols: Iterable[str] = (),
    numeric_cols: Iterable[str] = (),
) -> list[dict]:
    """Convierte DataFrame a list[dict] listo para insert bulk.

    1. Filtra solo cols que existen en `model.__table__.columns`.
    2. Coerciona int_cols a Int64 (nullable int de pandas).
    3. Coerciona datetime_cols a datetime64 (con `dayfirst=True`).
    4. Coerciona numeric_cols a float64.
    5. Reemplaza NaN/NaT por Python None explicito (evita bug pyodbc 22003).
    6. Devuelve list[dict] con keys = nombres de columnas.
    """
    valid_cols = {c.name for c in model.__table__.columns}
    df = df[[c for c in df.columns if c in valid_cols]].copy()

    for col in int_cols:
        if col in df.columns:
            # round() antes del astype para tolerar valores float legitimos
            # (ej. distancia_km '8.5'). Sin esto pandas 2.x lanza
            # 'cannot safely cast non-equivalent float64 to int64' cuando
            # la columna trae decimales. Si la col tiene NaN, los conserva.
            df[col] = (
                pd.to_numeric(df[col], errors="coerce")
                .round()
                .astype("Int64")
            )

    for col in datetime_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Tipos Python nativos por celda: pd.Timestamp/np.int64 rompen el
    # array-binding de fast_executemany (medido: int_gd20 137 filas/s con
    # 3 columnas datetime; ver type_coercion.dataframe_to_native_records).
    return dataframe_to_native_records(df)


def df_to_records_nullable(df: pd.DataFrame) -> list[dict]:
    """Convierte DataFrame -> list[dict] reemplazando NaN/NaT por None.

    Sin coercion de tipos. Util para persistencia raw a STG (cuando
    la tabla no tiene constraints estrictos de tipo).

    Reemplaza el patron literal:
        df.astype(object).where(df.notna(), None).to_dict(orient="records")
    que aparecia en cartera_pipeline, gd20_pipeline y query_pipeline.
    """
    return df.astype(object).where(df.notna(), None).to_dict(orient="records")
