from __future__ import annotations

from sqlalchemy import Column, Integer, String

from itacamba_reportes.persistence.base import Base
from itacamba_reportes.persistence.mixins import TimestampsMixin


class EquipoIntModel(Base, TimestampsMixin):

    __tablename__ = "int_ref_equipo"

    id = Column(Integer, primary_key=True, autoincrement=True)

    grupo_vendedores = Column(String(10),  index=True, nullable=True)
    vendedor_sap     = Column(String(200), nullable=True)
    vendedor          = Column(String(200), nullable=True)
    vendedor_ok      = Column(String(100), index=True, nullable=True)
    equipo           = Column(String(100), nullable=True)
    gerencia         = Column(String(100), nullable=True)
