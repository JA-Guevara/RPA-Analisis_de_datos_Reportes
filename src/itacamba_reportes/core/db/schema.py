from __future__ import annotations

import logging
from itacamba_reportes.core.db.base import Base
from itacamba_reportes.core.db.connection import engine
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


def init_db() -> None:
    logger.info("Inicializando esquemas de Base de Datos en %s...", engine.url.database or "local")
    Base.metadata.create_all(bind=engine)
    logger.info("Todos los esquemas de Base de Datos han sido inicializados correctamente.")
