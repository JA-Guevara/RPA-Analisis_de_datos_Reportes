from __future__ import annotations

from contextlib import contextmanager
from typing import Callable, Iterator

from sqlalchemy.orm import Session

from itacamba_reportes.persistence.engine import SessionLocal


@contextmanager
def get_session(
    session_factory: Callable[[], Session] | None = None,
) -> Iterator[Session]:
    factory = session_factory or SessionLocal
    if factory is None:
        raise RuntimeError(
            "SessionLocal no esta configurado; revisar variables DB_* en .env"
        )

    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
