from __future__ import annotations

from sqlalchemy import BigInteger, Column, Integer, String

from itacamba_reportes.persistence.base import Base
from itacamba_reportes.persistence.mixins import TimestampsMixin


class MaterialIntModel(Base, TimestampsMixin):

    __tablename__ = "int_ref_material"

    id = Column(Integer, primary_key=True, autoincrement=True)

    codigo = Column(BigInteger, unique=True, index=True, nullable=False)
    descripcion = Column(String(300))
