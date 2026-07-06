"""Bulk insert por cursor pyodbc crudo — la ruta rápida REAL.

Por qué existe: `session.execute(insert(Model), records)` deja que
SQLAlchemy elija la estrategia y en mssql+pyodbc termina en
"insertmanyvalues": statements multi-VALUES limitados por los 2.100
parámetros de SQL Server (~42 filas/lote con 49 columnas). Medido en
este proyecto: stg_query a 437 filas/s, int_gd20 a 137 filas/s.

Este helper ejecuta UN prepared statement con array-binding TDS
(`cursor.fast_executemany = True`) sin límite de parámetros, en chunks
para acotar memoria. Requiere escalares Python NATIVOS (datetime, int,
float, str, None) — garantizados por `dataframe_to_native_records`.

Garantías:
- `bulk_replace`: TRUNCATE + INSERT en LA MISMA transacción (atómico,
  igual que el comportamiento anterior de los repos int).
- Si fast_executemany falla (caso borde de inferencia de tipos con
  chunks 100% NULL), se reintenta el chunk en modo clásico: la corrida
  no se cae, solo se loggea el downgrade.
- Compatible con cualquier DBAPI (tests usan SQLite): TRUNCATE cae a
  DELETE fuera de mssql y fast_executemany se activa solo si existe.
"""

from __future__ import annotations

import logging
from time import perf_counter
from typing import Any

from sqlalchemy.engine import Engine

from itacamba_reportes.persistence.base import Base
from itacamba_reportes.persistence.engine import engine as _default_engine

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 20_000


def _insert_sql(table: str, columns: list[str]) -> str:
    cols = ", ".join(f"[{c}]" for c in columns)
    marks = ", ".join("?" for _ in columns)
    return f"INSERT INTO [{table}] ({cols}) VALUES ({marks})"


def _records_to_tuples(records: list[dict[str, Any]], columns: list[str]) -> list[tuple]:
    return [tuple(r.get(c) for c in columns) for r in records]


def _executemany_chunked(cursor, sql: str, rows: list[tuple], chunk_size: int,
                         table: str) -> None:
    use_fast = hasattr(cursor, "fast_executemany")
    if use_fast:
        cursor.fast_executemany = True
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i:i + chunk_size]
        try:
            cursor.executemany(sql, chunk)
        except Exception:
            if not use_fast:
                raise
            # Caso borde de fast_executemany (p. ej. inferencia de tipos
            # con un chunk 100% NULL): reintentar el chunk en modo clásico.
            logger.warning(
                "%s: fast_executemany fallo en chunk %d-%d, reintentando "
                "en modo clasico (mas lento, mismos datos)",
                table, i, i + len(chunk),
            )
            cursor.fast_executemany = False
            cursor.executemany(sql, chunk)
            cursor.fast_executemany = True


def bulk_insert(
    model: type[Base],
    records: list[dict[str, Any]],
    *,
    truncate_first: bool = False,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    engine: Engine | None = None,
) -> int:
    """INSERT masivo (opcionalmente precedido de TRUNCATE atómico).

    Returns: filas insertadas.
    """
    eng = engine if engine is not None else _default_engine
    if eng is None:
        raise RuntimeError("Engine SQLAlchemy no inicializado (verificar .env)")

    table = model.__tablename__
    if not records and not truncate_first:
        return 0

    raw = eng.raw_connection()
    try:
        cursor = raw.cursor()
        if truncate_first:
            if eng.dialect.name == "mssql":
                cursor.execute(f"TRUNCATE TABLE [{table}]")
            else:  # SQLite y otros (tests)
                cursor.execute(f"DELETE FROM [{table}]")

        if records:
            columns = list(records[0].keys())
            t0 = perf_counter()
            rows = _records_to_tuples(records, columns)
            sql = _insert_sql(table, columns)
            _executemany_chunked(cursor, sql, rows, chunk_size, table)
            logger.info(
                "%s bulk_insert (raw fast_executemany): %d filas x %d cols "
                "en %.2fs (%.0f filas/s)",
                table, len(rows), len(columns), perf_counter() - t0,
                len(rows) / max(perf_counter() - t0, 1e-9),
            )
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()
    return len(records)


def bulk_replace(
    model: type[Base],
    records: list[dict[str, Any]],
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    engine: Engine | None = None,
) -> int:
    """TRUNCATE + INSERT atómicos (misma transacción), como los repos int."""
    return bulk_insert(
        model, records,
        truncate_first=True, chunk_size=chunk_size, engine=engine,
    )
