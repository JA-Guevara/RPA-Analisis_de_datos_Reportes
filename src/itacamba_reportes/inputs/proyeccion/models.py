from __future__ import annotations

from sqlalchemy import BigInteger, Column, Index, Integer, Numeric, String
from itacamba_reportes.core.db.base import Base, TimestampsMixin


class ProyeccionStgModel(Base, TimestampsMixin):
    __tablename__ = "stg_proyeccion"
    __table_args__ = (
        Index("ix_stg_proy_cliente", "codigo_cliente"),
        Index("ix_stg_proy_dia", "dia"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    gerencia = Column(String(100))
    equipo = Column(String(100))
    departamento = Column(String(100))
    incoterms = Column(String(20))
    centro_distribucion = Column(String(100))
    material = Column(String(200))
    localidad_im = Column(String(100))
    codigo_cliente = Column(BigInteger, default=0)
    dia = Column(Integer)
    rf = Column(Numeric(18, 4), default=0)
    rf_ajustado_im = Column(Numeric(18, 4), default=0)
