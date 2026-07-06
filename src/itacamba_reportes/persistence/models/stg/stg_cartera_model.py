"""Tabla SQL stg_cartera — snapshot crudo del Excel SAP."""

from __future__ import annotations

from sqlalchemy import Column, DateTime, Index, Integer, String

from itacamba_reportes.persistence.base import Base
from itacamba_reportes.persistence.mixins import TimestampsMixin


class StgCarteraModel(Base, TimestampsMixin):
    __tablename__ = "stg_cartera"
    __table_args__ = (
        Index("ix_stg_cartera_run_id", "run_id"),
        Index("ix_stg_cartera_cliente", "cliente"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(DateTime, nullable=False)
    row_index = Column(Integer, nullable=False)

    cliente = Column(String(50))
    column2 = Column(String(500))
    attribute_10 = Column(String(100))
    poblacion = Column(String(200))
    barrio = Column(String(200))
    attribute_7 = Column(String(100))
    attribute_6 = Column(String(100))
    region = Column(String(10))
    column9 = Column(String(100))
    grupo_de_cuentas = Column(String(20))
    column11 = Column(String(200))
    telefono = Column(String(50))
    nif_1 = Column(String(50))
    codigo_postal = Column(String(20))
    gcd_codemplazfiscal = Column(String(50))
    calle = Column(String(500))
    inclusion_date = Column(String(50))
    tipo_de_operacion = Column(String(50))
    zemailadd = Column(String(100))
    zvcrisk = Column(String(50))
    via_de_pago = Column(String(50))
    sector = Column(String(50))
    column23 = Column(String(200))
    canal_distribucion = Column(String(50))
    column25 = Column(String(200))
    organizacion_de_ventas = Column(String(50))
    column27 = Column(String(200))
    oficina_de_ventas = Column(String(50))
    column29 = Column(String(200))
    grupo_de_vendedores = Column(String(50))
    equipo = Column(String(100))
    representante_ventas = Column(String(100))
    vendedor = Column(String(100))
    coordinador_ventas = Column(String(100))
    coordinador = Column(String(100))
    trilha = Column(String(50))
    canal = Column(String(100))
    condicion_pago = Column(String(50))
    contador = Column(String(50))
