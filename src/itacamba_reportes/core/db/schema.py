from __future__ import annotations

import logging

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from itacamba_reportes.core.db.base import Base
from itacamba_reportes.core.db.connection import get_engine
from itacamba_reportes.core.settings import EnvConfig
from itacamba_reportes.core.audit.tracker import PipelineExecutionModel
from itacamba_reportes.inputs.referencias.models import (
    CenterRefModel,
    ChannelRefModel,
    LocalityRefModel,
    MaterialRefModel,
    SalesTeamRefModel,
    RouteRefModel,
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
    with get_engine().connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def sync_table_columns() -> None:
    from sqlalchemy import inspect, text
    from itacamba_reportes.outputs.despacho_bi.models import DispatchBiIntModel

    eng = get_engine()
    insp = inspect(eng)
    if not insp.has_table("int_despacho_bi"):
        return

    existing_cols = {col["name"].lower() for col in insp.get_columns("int_despacho_bi")}
    with eng.begin() as conn:
        for col in DispatchBiIntModel.__table__.columns:
            if col.name.lower() not in existing_cols:
                col_type = col.type.compile(eng.dialect)
                logger.info("Sincronizando esquema: anadiendo columna %s (%s) a int_despacho_bi", col.name, col_type)
                if eng.dialect.name == "sqlite":
                    stmt = f"ALTER TABLE [int_despacho_bi] ADD COLUMN [{col.name}] {col_type}"
                else:
                    stmt = f"ALTER TABLE [int_despacho_bi] ADD [{col.name}] {col_type} NULL"
                conn.execute(text(stmt))


def ensure_all_tables_exist() -> None:
    from sqlalchemy import inspect
    eng = get_engine()
    insp = inspect(eng)
    missing = [name for name in Base.metadata.tables if not insp.has_table(name)]
    if missing:
        logger.info("Detectadas tablas faltantes en BD: %s. Creandolas automaticamente...", missing)
        Base.metadata.create_all(eng, checkfirst=True)
        logger.info("Tablas creadas exitosamente.")
    sync_table_columns()


def upgrade_db(reset_alembic: bool = False) -> None:
    eng = get_engine()
    logger.info("Aplicando migraciones Alembic en %s...", eng.url.database)
    from sqlalchemy import text
    if reset_alembic:
        try:
            with eng.begin() as conn:
                conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
            logger.info("Tabla alembic_version reiniciada para ejecucion limpia desde cero.")
        except Exception as exc:
            logger.warning("No se pudo reiniciar alembic_version: %s", exc)

    try:
        command.upgrade(_alembic_config(), "head")
    except Exception as exc:
        logger.warning("Alembic upgrade aviso: %s", exc)

    ensure_all_tables_exist()
    logger.info("Base de Datos en la version %s con todas las tablas sincronizadas", head_revision())


def ensure_schema_current() -> None:
    head = head_revision()
    current = current_revision()
    if current != head:
        logger.warning(
            "La Base de Datos esta en la version '%s' (esperada: '%s'). Aplicando migraciones automaticamente...",
            current or "sin migrar",
            head,
        )
        upgrade_db()
    ensure_all_tables_exist()
