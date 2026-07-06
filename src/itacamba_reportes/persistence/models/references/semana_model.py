from __future__ import annotations

from sqlalchemy import Column, Integer, String

from itacamba_reportes.persistence.base import Base
from itacamba_reportes.persistence.mixins import TimestampsMixin


class SemanaIntModel(Base, TimestampsMixin):

    __tablename__ = "int_ref_semana"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Key de lookup: dia del mes (1-31)
    dia = Column(Integer, unique=True, index=True, nullable=False)

    # = etiqueta semana ('SEMANA 1' .. 'SEMANA 5')
    semana = Column(String(20))
