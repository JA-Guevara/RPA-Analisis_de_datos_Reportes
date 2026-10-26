from __future__ import annotations

import logging
import urllib.parse
from contextlib import contextmanager
from typing import Any, Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from itacamba_reportes.core.settings import EnvConfig

logger = logging.getLogger(__name__)

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def build_sqlserver_url() -> str | None:
    if EnvConfig.DATABASE_URL and "{" not in EnvConfig.DATABASE_URL:
        return EnvConfig.DATABASE_URL

    if not all([EnvConfig.DB_SERVER, EnvConfig.DB_NAME]):
        return None

    driver_name = (EnvConfig.DB_DRIVER or "SQL Server").strip("{}")
    server_str = str(EnvConfig.DB_SERVER)
    if EnvConfig.DB_PORT and "," not in server_str and "\\" not in server_str:
        server_str = f"{server_str},{EnvConfig.DB_PORT}"

    odbc_parts = [
        f"DRIVER={{{driver_name}}}",
        f"SERVER={server_str}",
        f"DATABASE={EnvConfig.DB_NAME}",
    ]
    if EnvConfig.DB_USER and EnvConfig.DB_PASSWORD:
        odbc_parts.append(f"UID={EnvConfig.DB_USER}")
        odbc_parts.append(f"PWD={EnvConfig.DB_PASSWORD}")
    else:
        # Autenticacion integrada de Windows si no se configuran usuario y clave
        odbc_parts.append("Trusted_Connection=yes")

    if any(k in driver_name for k in ("ODBC Driver", "Native Client")):
        trust_cert = "yes" if EnvConfig.DB_TRUST_CERT else "no"
        odbc_parts.append(f"TrustServerCertificate={trust_cert}")
        odbc_parts.append("Connection Timeout=5")
    params = urllib.parse.quote_plus(";".join(odbc_parts) + ";")
    return f"mssql+pyodbc:///?odbc_connect={params}"


def create_app_engine() -> Engine:
    sqlserver_url = build_sqlserver_url()
    if not sqlserver_url:
        raise ValueError("Configuración de SQL Server incompleta en .env (se requiere al menos DB_SERVER y DB_NAME)")

    try:
        eng = create_engine(sqlserver_url, pool_pre_ping=True, fast_executemany=True)
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Conectado exitosamente a SQL Server: %s (%s)", EnvConfig.DB_NAME, EnvConfig.DB_SERVER)
        return eng
    except Exception as exc:
        logger.error("No se pudo conectar a SQL Server en %s:%s/%s: %s", EnvConfig.DB_SERVER, EnvConfig.DB_PORT, EnvConfig.DB_NAME, exc)
        raise ConnectionError(
            f"Fallo de conexión a SQL Server ({EnvConfig.DB_SERVER}:{EnvConfig.DB_PORT}/{EnvConfig.DB_NAME}). "
            "Verifique que la VPN esté activa y que el servidor sea accesible."
        ) from exc


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_app_engine()
    return _engine


def set_engine(eng: Engine | None) -> None:
    global _engine, _session_factory
    _engine = eng
    _session_factory = None


class _LazyEngine:
    def __getattr__(self, name: str) -> Any:
        return getattr(get_engine(), name)


engine: Engine = _LazyEngine()  # type: ignore


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
    return _session_factory


@contextmanager
def get_session() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def is_sql_server() -> bool:
    return get_engine().dialect.name == "mssql"
