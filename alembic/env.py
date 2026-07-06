"""Alembic environment.

Importa TODOS los modelos del proyecto para que `Base.metadata` quede
poblada antes de correr `target_metadata = Base.metadata`. Si olvidas un
import, Alembic no detecta la tabla y `--autogenerate` la dropea.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from itacamba_reportes.persistence.base import Base  # noqa: E402
from itacamba_reportes.persistence.engine import engine  # noqa: E402

from itacamba_reportes.persistence.models.stg.stg_cartera_model import StgCarteraModel  # noqa: E402,F401
from itacamba_reportes.persistence.models.stg.stg_gd20_model import StgGd20Model  # noqa: E402,F401
from itacamba_reportes.persistence.models.stg.stg_query_model import StgQueryModel  # noqa: E402,F401

from itacamba_reportes.persistence.models.int.cartera_model import CarteraIntModel  # noqa: E402,F401
from itacamba_reportes.persistence.models.int.gd20_model import Gd20IntModel  # noqa: E402,F401
from itacamba_reportes.persistence.models.int.query_model import IntQueryModel  # noqa: E402,F401
from itacamba_reportes.persistence.models.int.ventas_bi_model import VentasBiIntModel  # noqa: E402,F401
from itacamba_reportes.persistence.models.int.despacho_bi_model import DespachoBiIntModel  # noqa: E402,F401
from itacamba_reportes.persistence.models.int.despacho_mes_model import DespachoMesIntModel  # noqa: E402,F401

from itacamba_reportes.persistence.models.references.almacen_model import AlmacenIntModel  # noqa: E402,F401
from itacamba_reportes.persistence.models.references.centro_model import CentroIntModel  # noqa: E402,F401
from itacamba_reportes.persistence.models.references.equipo_model import EquipoIntModel  # noqa: E402,F401
from itacamba_reportes.persistence.models.references.localidad_model import LocalidadIntModel  # noqa: E402,F401
from itacamba_reportes.persistence.models.references.material_model import MaterialIntModel  # noqa: E402,F401
from itacamba_reportes.persistence.models.references.semana_model import SemanaIntModel  # noqa: E402,F401

from itacamba_reportes.persistence.models.pipeline_execution_model import PipelineExecutionModel  # noqa: E402,F401


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
