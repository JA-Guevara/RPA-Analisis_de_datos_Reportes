"""Tabla SQL stg_gd20 — snapshot crudo del Excel SAP GD20."""

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


class StgGd20Model(Base, TimestampsMixin):
    __tablename__ = "stg_gd20"
    __table_args__ = (
        Index("ix_stg_gd20_documento_comercial", "documento_comercial"),
        Index("ix_stg_gd20_cliente", "cliente"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Identificacion organizacional
    ejercicio                = Column(String(10))
    sociedad                 = Column(String(10))
    organizacion_ventas      = Column(String(10))
    centro                   = Column(String(10))
    division                 = Column(String(10))
    oficina_ventas           = Column(String(10))
    canal_distribucion       = Column(String(10))
    sector                   = Column(String(10))
    numero_cuenta            = Column(BigInteger)
    centro_beneficio         = Column(String(50))

    # Producto
    material                 = Column(BigInteger)
    unidad_medida_base       = Column(String(10))
    periodo_contable         = Column(String(10))

    # Geografia
    clave_pais_region        = Column(String(10))
    region                   = Column(String(10))
    poblacion                = Column(String(100))
    grupo_vendedores         = Column(String(10))

    # Codigos cliente
    cliente                  = Column(BigInteger)
    emisor_orden             = Column(BigInteger)
    customer_bill_to         = Column(BigInteger)
    customer_rebate          = Column(BigInteger)
    grupo_clientes_2         = Column(String(10))

    # Atributos / clasificacion
    atributo_6               = Column(String(10))
    atributo_7               = Column(String(10))
    atributo_10              = Column(String(10))
    clase_factura            = Column(String(10))

    # Usuario / texto
    nombre_usuario           = Column(String(50))
    texto                    = Column(String(200))

    # Documento + montos
    numero_documento         = Column(BigInteger)
    cantidad                 = Column(Numeric(18, 4))
    moneda_sociedad          = Column(Numeric(18, 4))

    # Fechas
    fe_contabilizacion       = Column(DateTime)
    fecha_entrada            = Column(DateTime)
    fecha_valor              = Column(DateTime)

    documento_comercial      = Column(BigInteger)
    hora_entrada             = Column(String(20))

    # Monedas
    moneda_transaccion       = Column(Numeric(18, 4))
    clave_moneda_transaccion = Column(String(10))
    moneda_fuerte            = Column(Numeric(18, 4))
    clave_moneda_fuerte      = Column(String(10))

    # Referencias
    numero_doc_referencia    = Column(BigInteger)
    numero_documento_2       = Column(BigInteger)

    # Incoterms / pago
    incoterms                = Column(String(10))
    incoterms_parte_2        = Column(String(50))
    clase_documento          = Column(String(10))
    cond_pago                = Column(String(10))
    dias_1                   = Column(Integer)
    numero_transporte        = Column(BigInteger)
