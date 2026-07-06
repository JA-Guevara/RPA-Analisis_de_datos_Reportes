"""Test del helper bulk_insert/bulk_replace contra una BD real (SQLite).

Valida con una base de datos de verdad (no mocks) que el camino raw:
- inserta exactamente los mismos datos que entrega dataframe_to_native_records,
- bulk_replace es atómico (TRUNCATE/DELETE + INSERT) y reemplaza lo anterior,
- el chunking no pierde ni duplica filas,
- los None viajan como NULL.

En SQLite no hay fast_executemany (el helper lo activa solo si existe) —
el camino de código es el mismo que en producción salvo esa línea.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import Column, DateTime, Integer, Numeric, String, create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from itacamba_reportes.persistence.base import Base
from itacamba_reportes.persistence.bulk_insert import bulk_insert, bulk_replace
from itacamba_reportes.persistence.type_coercion import dataframe_to_native_records


class _BulkDemo(Base):
    __tablename__ = "_bulk_demo"
    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(50))
    cantidad = Column(Numeric(18, 4))
    fecha = Column(DateTime)


@pytest.fixture()
def engine(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/bulk.db")
    _BulkDemo.__table__.create(eng)
    return eng


def _records(n: int) -> list[dict]:
    df = pd.DataFrame({
        "nombre": [f"item {i}" if i % 5 else None for i in range(n)],
        "cantidad": pd.array([i * 1.25 if i % 3 else None for i in range(n)], dtype="Float64"),
        "fecha": pd.to_datetime(pd.Series(["2026-01-15"] * n).mask(pd.Series(range(n)) % 7 == 0)),
    })
    return dataframe_to_native_records(df)


def _fetch_all(engine) -> list[tuple]:
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT nombre, cantidad, fecha FROM _bulk_demo ORDER BY id"
        )).all()
    return [tuple(r) for r in rows]


def test_bulk_insert_inserts_exact_data(engine):
    recs = _records(50)
    assert bulk_insert(_BulkDemo, recs, engine=engine) == 50

    fetched = _fetch_all(engine)
    assert len(fetched) == 50
    assert fetched[0][0] is None                # i=0: nombre None -> NULL
    nombre, cantidad, fecha = fetched[1]
    assert (nombre, cantidad) == ("item 1", 1.25)
    assert str(fecha).startswith("2026-01-15 00:00:00")
    nulls_fecha = sum(1 for r in fetched if r[2] is None)
    assert nulls_fecha == len([i for i in range(50) if i % 7 == 0])


def test_bulk_replace_is_replacement_not_append(engine):
    bulk_insert(_BulkDemo, _records(30), engine=engine)
    assert len(_fetch_all(engine)) == 30

    assert bulk_replace(_BulkDemo, _records(12), engine=engine) == 12
    assert len(_fetch_all(engine)) == 12        # reemplazo, no acumulación


def test_chunking_preserves_all_rows(engine):
    recs = _records(105)
    bulk_insert(_BulkDemo, recs, engine=engine, chunk_size=10)  # 11 chunks
    fetched = _fetch_all(engine)
    assert len(fetched) == 105
    # mismo contenido que sin chunking (orden por id = orden de insert)
    nombres = [r[0] for r in fetched]
    assert nombres == [r["nombre"] for r in recs]


def test_empty_records(engine):
    assert bulk_insert(_BulkDemo, [], engine=engine) == 0
    bulk_insert(_BulkDemo, _records(5), engine=engine)
    assert bulk_replace(_BulkDemo, [], engine=engine) == 0
    assert len(_fetch_all(engine)) == 0         # truncate_first con 0 filas vacía


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
