from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
)

from itacamba_reportes.core.db.base import Base, TimestampsMixin


class DispatchMonthIntModel(Base, TimestampsMixin):
    __tablename__ = "int_despacho_mes"
    __table_args__ = (
        Index("ix_int_despacho_mes_cliente", "codigo_cliente"),
        Index("ix_int_despacho_mes_fecha", "dia"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    gerencia = Column(String(150))
    equipo = Column(String(150))
    departamento = Column(String(100))
    localidad = Column(String(150))
    centro_distribucion = Column(String(150))
    producto = Column(String(200))
    incoterms = Column(String(20))
    dia = Column(Integer)
    codigo_cliente = Column(BigInteger)

    despacho_t = Column(Numeric(18, 4), default=0)
    rf = Column(Numeric(18, 4), default=0)
    rf_ajustado_im = Column(Numeric(18, 4), default=0)
    proyeccion = Column(Numeric(18, 4), default=0)

    nombre_cliente = Column(String(500))
    vendedor = Column(String(150))
    tipo_venta = Column(String(50))
    canal = Column(String(100))
    semana2 = Column(String(50))
