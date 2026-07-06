"""Pandera schema para int_cartera."""

from __future__ import annotations

import pandera.pandas as pa
from pandera.typing import Series


class CarteraIntContract(pa.DataFrameModel):

    cliente: Series[int] = pa.Field(ge=1)
    nombre_cliente: Series[str] = pa.Field(nullable=False, str_length={"min_value": 1})
    region: Series[str] = pa.Field(nullable=True, str_length={"max_value": 10})
    region_nombre: Series[str] = pa.Field(nullable=True)
    poblacion: Series[str] = pa.Field(nullable=True)
    nit: Series[str] = pa.Field(nullable=True)
    telefono: Series[str] = pa.Field(nullable=True)
    codigo_postal: Series[str] = pa.Field(nullable=True)

    class Config:
        strict = False
        coerce = True
        ordered = False
