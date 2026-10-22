from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from itacamba_reportes.core.db.base import Base
from itacamba_reportes.core.db.connection import engine
import itacamba_reportes.inputs.referencias.models
import itacamba_reportes.inputs.cartera.models
import itacamba_reportes.inputs.query.models
import itacamba_reportes.inputs.proyeccion.models
import itacamba_reportes.inputs.gd20.models
import itacamba_reportes.outputs.ventas_bi.models
import itacamba_reportes.outputs.despacho_bi.models
import itacamba_reportes.outputs.despacho_mes.models
import itacamba_reportes.core.audit.tracker


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    raise RuntimeError("Modo offline no soportado. Usar migraciones online con engine real.")


def run_migrations_online() -> None:
    if engine is None:
        raise RuntimeError("Engine no inicializado. Verificar variables DB_* en .env")

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
