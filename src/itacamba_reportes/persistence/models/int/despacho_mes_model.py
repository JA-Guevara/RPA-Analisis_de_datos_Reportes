"""Tabla SQL int_despacho_mes — agregado mensual del despacho.

1 fila por combinación de 11 dimensiones (group by). Equivale a la
hoja DESPACHO_MES del basepanel.xlsm.

Modo de carga: TRUNCATE + INSERT por corrida.

Las cols rf / rf_ajustado_im / proyeccion quedan NULL hasta que negocio
defina la fuente de carga (entrada manual o pipeline externo).
"""

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

from itacamba_reportes.persistence.base import Base
from itacamba_reportes.persistence.mixins import TimestampsMixin


class DespachoMesIntModel(Base, TimestampsMixin):
    __tablename__ = "int_despacho_mes"
    __table_args__ = (
        Index("ix_int_despacho_mes_codigo_cliente", "codigo_cliente"),
        Index("ix_int_despacho_mes_fecha", "fecha"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Dimensiones
    gerencia            = Column(String(100))
    equipo              = Column(String(100))
    departamento        = Column(String(50))
    localidad           = Column(String(100))
    centro_distribucion = Column(String(100))
    producto            = Column(String(200))
    incoterms           = Column(String(10))
    fecha               = Column(DateTime)
    mes                 = Column(Integer)
    dia                 = Column(Integer)
    codigo_cliente      = Column(BigInteger)

    # Métricas
    despacho_t      = Column(Numeric(18, 4))
    rf              = Column(Numeric(18, 4))
    rf_ajustado_im  = Column(Numeric(18, 4))
    proyeccion      = Column(Numeric(18, 4))

    # Lookups vivos
    nombre_cliente  = Column(String(500))
    vendedor        = Column(String(100))
    tipo_venta      = Column(String(50))
    canal           = Column(String(100))
    semana2         = Column(String(20))
