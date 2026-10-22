from __future__ import annotations

from sqlalchemy import BigInteger, Column, DateTime, Index, Integer, Numeric, String
from itacamba_reportes.core.db.base import Base, TimestampsMixin


class QueryStgModel(Base, TimestampsMixin):
    __tablename__ = "stg_query"
    __table_args__ = (
        Index("ix_stg_query_pedido", "nro_pedido"),
        Index("ix_stg_query_destinatario", "cod_destinatario"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    fecha_salida = Column(DateTime, nullable=True)
    fecha_creacion_entrega = Column(DateTime, nullable=True)
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
    cantidad_ton = Column(Numeric(18, 4))
    precio_pedido = Column(Numeric(18, 4))
    unidad_entrega = Column(String(20))
    nom_centro_origen = Column(String(200))
    nom_centro_destino = Column(String(200))
    fecha_facturacion = Column(DateTime, nullable=True)
    nro_factura = Column(BigInteger, nullable=True)
    tipo_pos_pedido = Column(String(50))
    documento_referencia = Column(String(50))
    codigo_ferretero = Column(String(50))


class QueryIntModel(Base, TimestampsMixin):
    __tablename__ = "int_query"
    __table_args__ = (
        Index("ix_int_query_pedido", "nro_pedido"),
        Index("ix_int_query_destinatario", "cod_destinatario"),
        Index("ix_int_query_fecha", "dia"),
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
