from __future__ import annotations

from sqlalchemy import Column, Integer, String

from itacamba_reportes.persistence.base import Base
from itacamba_reportes.persistence.mixins import TimestampsMixin


class AlmacenIntModel(Base, TimestampsMixin):

    __tablename__ = "int_ref_almacen"

    id = Column(Integer, primary_key=True, autoincrement=True)

    descripcion_sap = Column(String(100), unique=True, index=True, nullable=False)
    segmento = Column(String(200))
    canal = Column(String(50))
