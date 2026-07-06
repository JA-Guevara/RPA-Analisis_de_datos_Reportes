from __future__ import annotations

from sqlalchemy import Column, Integer, String

from itacamba_reportes.persistence.base import Base
from itacamba_reportes.persistence.mixins import TimestampsMixin


class LocalidadIntModel(Base, TimestampsMixin):

    __tablename__ = "int_ref_localidad"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Key de lookup (case-sensitive en BD, normalizamos en Python al hacer merge)
    localidad_despacho = Column(String(200), unique=True, index=True, nullable=False)

    # = REGION M destino ("SANTA CRUZ CUIDAD" / "RESTO SANTA CRUZ" / etc.)
    localidad_im = Column(String(100))
