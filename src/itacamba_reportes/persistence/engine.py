from __future__ import annotations

import logging
import urllib.parse

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from itacamba_reportes.config.env_config import (
    EnvConfig,
    validate_data_paths,
    validate_db_config,
)

logger = logging.getLogger(__name__)


def _resolve_url_placeholders(url_template: str) -> str:
    """Resuelve placeholders {DB_*} dentro de DATABASE_URL con los valores del entorno.

    Cada valor se URL-encodea (quote_plus) para tolerar caracteres especiales
    en el password (p. ej. '*') o espacios en el nombre del driver ODBC.
    Si la URL no trae placeholders, se devuelve sin cambios.
    """
    if "{" not in url_template:
        return url_template

    values = {
        "DB_USER":       EnvConfig.DB_USER or "",
        "DB_PASSWORD":   EnvConfig.DB_PASSWORD or "",
        "DB_SERVER":     EnvConfig.DB_SERVER or "",
        "DB_PORT":       EnvConfig.DB_PORT,
        "DB_NAME":       EnvConfig.DB_NAME or "",
        "DB_DRIVER":     EnvConfig.DB_DRIVER or "",
        "DB_TRUST_CERT": "yes" if EnvConfig.DB_TRUST_CERT else "no",
    }
    encoded = {key: urllib.parse.quote_plus(str(value)) for key, value in values.items()}
    try:
        return url_template.format_map(encoded)
    except (KeyError, IndexError) as exc:
        logger.warning("Placeholder no reconocido en DATABASE_URL: %s", exc)
        return url_template


def build_connection_url() -> str | None:
    # 1) DATABASE_URL explícita tiene prioridad sobre las variables sueltas.
    if EnvConfig.DATABASE_URL:
        logger.info("Conexión configurada vía DATABASE_URL explícita")
        return _resolve_url_placeholders(EnvConfig.DATABASE_URL)

    # 2) Fallback: armar la URL desde las variables DB_* (formato odbc_connect,
    #    robusto frente a caracteres especiales y espacios en el driver).
    required = {
        "DB_DRIVER":   EnvConfig.DB_DRIVER,
        "DB_SERVER":   EnvConfig.DB_SERVER,
        "DB_NAME":     EnvConfig.DB_NAME,
        "DB_USER":     EnvConfig.DB_USER,
        "DB_PASSWORD": EnvConfig.DB_PASSWORD,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        logger.warning("Faltan vars de DB: %s", ", ".join(missing))
        return None

    trust_cert = "yes" if EnvConfig.DB_TRUST_CERT else "no"
    params = urllib.parse.quote_plus(
        f"DRIVER={EnvConfig.DB_DRIVER};"
        f"SERVER={EnvConfig.DB_SERVER},{EnvConfig.DB_PORT};"
        f"DATABASE={EnvConfig.DB_NAME};"
        f"UID={EnvConfig.DB_USER};"
        f"PWD={EnvConfig.DB_PASSWORD};"
        f"TrustServerCertificate={trust_cert};"
        f"Packet Size=32767;"
    )
    return f"mssql+pyodbc:///?odbc_connect={params}"


DATABASE_URL: str | None = build_connection_url()

engine: Engine | None = None
SessionLocal = None

if DATABASE_URL:
    try:
        engine = create_engine(
            DATABASE_URL,
            echo=False,
            poolclass=NullPool,
            future=True,
            fast_executemany=True,
        )

        @event.listens_for(engine, "before_cursor_execute")
        def _force_fast_executemany(conn, cursor, statement, params, context, executemany):
            if executemany:
                cursor.fast_executemany = True

        SessionLocal = sessionmaker(
            bind=engine,
            autocommit=False,
            autoflush=False,
        )
        logger.info("SQLAlchemy engine inicializado (fast_executemany hook activo)")
    except Exception as exc:
        logger.error("Error creando engine: %s", exc)


