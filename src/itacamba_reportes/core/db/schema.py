from __future__ import annotations

import logging

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from itacamba_reportes.core.db.base import Base
from itacamba_reportes.core.db.connection import engine
from itacamba_reportes.core.settings import EnvConfig
from itacamba_reportes.core.audit.tracker import PipelineExecutionModel
from itacamba_reportes.inputs.referencias.models import (
    CenterRefModel,
    ChannelRefModel,
    LocalityRefModel,
    MaterialRefModel,
    SalesTeamRefModel,
    WeekRefModel,
)
from itacamba_reportes.inputs.cartera.models import CustomerStgModel, CustomerIntModel
from itacamba_reportes.inputs.query.models import QueryStgModel, QueryIntModel
from itacamba_reportes.inputs.proyeccion.models import ProyeccionStgModel
from itacamba_reportes.inputs.gd20.models import Gd20StgModel, Gd20IntModel
from itacamba_reportes.outputs.ventas_bi.models import SalesBiIntModel
from itacamba_reportes.outputs.despacho_bi.models import DispatchBiIntModel
from itacamba_reportes.outputs.despacho_mes.models import DispatchMonthIntModel

logger = logging.getLogger(__name__)


def _alembic_config() -> Config:
    cfg = Config(str(EnvConfig.PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(EnvConfig.PROJECT_ROOT / "alembic"))
    return cfg


def head_revision() -> str | None:
    return ScriptDirectory.from_config(_alembic_config()).get_current_head()


def current_revision() -> str | None:
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def upgrade_db() -> None:
    logger.info("Aplicando migraciones Alembic en %s...", engine.url.database)
    command.upgrade(_alembic_config(), "head")
    logger.info("Base de Datos en la version %s", head_revision())


def ensure_schema_current() -> None:
    head = head_revision()
    current = current_revision()
    if current != head:
        raise RuntimeError(
            f"La Base de Datos esta en la version '{current or 'sin migrar'}' y el codigo espera '{head}'. "
            "Ejecute: python main.py init-db"
        )
