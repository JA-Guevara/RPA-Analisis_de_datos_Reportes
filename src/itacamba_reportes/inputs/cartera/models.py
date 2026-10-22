from __future__ import annotations

from sqlalchemy import BigInteger, Column, Index, Integer, String
from itacamba_reportes.core.db.base import Base, TimestampsMixin


class CustomerStgModel(Base, TimestampsMixin):
    __tablename__ = "stg_cartera"
    __table_args__ = (
        Index("ix_stg_cartera_cliente", "cliente"),
        Index("ix_stg_cartera_orden", "orden_origen"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    orden_origen = Column(Integer, nullable=False, default=0)
    cliente = Column(BigInteger)
    nombre_cliente = Column(String(500))
    attribute_10 = Column(String(100))
    poblacion = Column(String(200))
    barrio = Column(String(200))
    attribute_7 = Column(String(100))
    attribute_6 = Column(String(100))
    region = Column(String(20))
    region_nombre = Column(String(100))
    grupo_cuentas = Column(String(20))
    sector = Column(String(20))
    sector_desc = Column(String(200))
    canal_distribucion = Column(String(20))
    canal_distribucion_desc = Column(String(200))
    organizacion_ventas = Column(String(20))
    oficina_ventas = Column(String(20))
    grupo_vendedores = Column(String(20))
    equipo = Column(String(100))
    vendedor = Column(String(150))
    coordinador = Column(String(150))
    canal = Column(String(100))
    condicion_pago = Column(String(50))


class CustomerIntModel(Base, TimestampsMixin):
    __tablename__ = "int_cartera"
    __table_args__ = (
        Index("ix_int_cartera_cliente", "cliente", unique=True),
        Index("ix_int_cartera_orden", "orden_origen"),
        Index("ix_int_cartera_vendedor", "vendedor"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    orden_origen = Column(Integer, nullable=False, default=0)
    cliente = Column(BigInteger)
    nombre_cliente = Column(String(500))
    attribute_10 = Column(String(100))
    poblacion = Column(String(200))
    barrio = Column(String(200))
    attribute_7 = Column(String(100))
    attribute_6 = Column(String(100))
    region = Column(String(20))
    region_nombre = Column(String(100))
    grupo_cuentas = Column(String(20))
    sector = Column(String(20))
    sector_desc = Column(String(200))
    canal_distribucion = Column(String(20))
    canal_distribucion_desc = Column(String(200))
    organizacion_ventas = Column(String(20))
    oficina_ventas = Column(String(20))
    grupo_vendedores = Column(String(20))
    equipo = Column(String(100))
    vendedor = Column(String(150))
    coordinador = Column(String(150))
    canal = Column(String(100))
    condicion_pago = Column(String(50))
