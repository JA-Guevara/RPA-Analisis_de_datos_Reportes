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


class DispatchBiIntModel(Base, TimestampsMixin):
    __tablename__ = "int_despacho_bi"
    __table_args__ = (
        Index("ix_int_despacho_bi_pedido", "nro_pedido"),
        Index("ix_int_despacho_bi_destinatario", "cod_destinatario"),
        Index("ix_int_despacho_bi_cliente", "codigo_cliente"),
        Index("ix_int_despacho_bi_fecha", "dia"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    fecha_salida = Column(DateTime, nullable=True)
    # Columna dia: dia del mes como entero (1-31) alineado al modelo dimensional
    dia = Column(Integer)
    mes = Column(Integer)
    anio = Column(Integer)
    nro_pedido = Column(BigInteger)
    incoterm = Column(String(20))
    centro_origen = Column(String(20))
    centro_destino = Column(String(20))
    cod_material = Column(BigInteger)
    material = Column(String(200))
    cod_ruta = Column(String(50))
    nom_ruta = Column(String(200))
    cod_destinatario = Column(BigInteger)
    nom_destinatario = Column(String(200))
    cod_pagador = Column(BigInteger)
    pagador = Column(String(200))
    despacho_t = Column(Numeric(18, 4))
    traslados_t = Column(Numeric(18, 4))
    centro_distribucion = Column(String(100))
    localidad = Column(String(100))
    departamento = Column(String(100))

    # Columnas enriquecidas para BI
    codigo_cliente = Column(BigInteger)
    nombre_cliente = Column(String(500))
    vendedor = Column(String(150))
    desarrollador = Column(String(150))
    equipo = Column(String(150))
    gerencia = Column(String(150))
    canal = Column(String(100))
    localidad_im = Column(String(150))
    semana = Column(String(50))
