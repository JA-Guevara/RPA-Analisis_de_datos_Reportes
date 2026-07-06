"""Tabla SQL int_gd20 — datos transformados con 27 cols calculadas.

Equivalente a la hoja BASE PANEL del Excel original (post Power Query +
macros + formulas). Combina 49 cols del SAP raw (renombradas con los
nombres del final post-bot) + 27 cols derivadas via lookups y calculos.
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


class Gd20IntModel(Base, TimestampsMixin):
    __tablename__ = "int_gd20"
    __table_args__ = (
        Index("ix_int_gd20_documento_comercial", "documento_comercial"),
        Index("ix_int_gd20_pagador", "pagador"),
        Index("ix_int_gd20_destinatario", "destinatario"),
        Index("ix_int_gd20_fe_contabilizacion", "fe_contabilizacion"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    # ─── 49 cols del SAP (con nombres del final post-bot) ───
    ejercicio                = Column(Integer)
    sociedad                 = Column(Integer)
    organizacion_ventas      = Column(Integer)
    centro                   = Column(String(10))
    division                 = Column(String(10))
    oficina_ventas           = Column(String(10))
    canal_distribucion       = Column(Integer)
    sector                   = Column(Integer)
    numero_cuenta            = Column(BigInteger)
    centro_beneficio         = Column(String(50))
    material                 = Column(BigInteger, index=True)
    unidad_medida_base       = Column(String(10))
    periodo_contable         = Column(Integer)
    clave_pais               = Column(String(5))
    region_sap               = Column(String(5))
    poblacion_sap            = Column(String(100))
    grupo_vendedores         = Column(String(10))

    pagador                  = Column(BigInteger)
    emisor_solicitante       = Column(BigInteger)
    customer_bill_to         = Column(BigInteger)
    destinatario             = Column(BigInteger)

    grupo_clientes_2         = Column(Integer)
    atributo_6               = Column(String(10))
    atributo_7               = Column(String(10))
    atributo_10              = Column(String(10))
    clase_factura            = Column(String(10))
    nombre_usuario           = Column(String(50))
    texto                    = Column(String(200))
    numero_documento         = Column(BigInteger)
    cantidad                 = Column(Numeric(18, 4))
    moneda_sociedad          = Column(Numeric(18, 4))
    fe_contabilizacion       = Column(DateTime)
    fecha_entrada            = Column(DateTime)
    fecha_valor              = Column(DateTime)
    documento_comercial      = Column(BigInteger)
    hora_entrada             = Column(String(20))
    moneda_transaccion       = Column(Numeric(18, 4))
    clave_moneda_transaccion = Column(String(10))
    moneda_fuerte            = Column(Numeric(18, 4))
    clave_moneda_fuerte      = Column(String(10))
    numero_doc_referencia    = Column(BigInteger)
    numero_documento_2       = Column(BigInteger)
    incoterms                = Column(String(10))
    incoterms_parte_2        = Column(String(50))
    clase_documento          = Column(String(10))
    cond_pago                = Column(String(10))
    dias_1                   = Column(Integer)
    numero_transporte        = Column(BigInteger)
    e                        = Column(String(10))

    # ─── 27 cols calculadas / derivadas ───

    # Cálculos sobre el RAW
    tipo_embalaje            = Column(String(20))
    nombre_producto          = Column(String(200))
    volumen_toneladas        = Column(Numeric(18, 4))

    # Lookups int_cartera
    nombre_pagador           = Column(String(500))
    nombre_solicitante       = Column(String(500))
    vendedor_sap             = Column(String(100))
    vendedor                 = Column(String(100))

    # Lookups int_ref_*
    vendedor_ok              = Column(String(100))
    gerencia                 = Column(String(100))
    equipo                   = Column(String(100))
    canal                    = Column(String(50))
    sub_canal                = Column(String(100))

    # Splits de fecha
    dia                      = Column(Integer)
    mes                      = Column(Integer)
    anio                     = Column(Integer)

    # Reglas de negocio
    tipo_venta               = Column(String(50))
    localidad                = Column(String(200))
    provincia                = Column(String(200))
    dpto                     = Column(String(100))
    region_m                 = Column(String(50))
    ingreso_bruto            = Column(Numeric(18, 4))
    dpto_pagador             = Column(String(100))
    localidad_pagador        = Column(String(200))
    codigo_cliente           = Column(BigInteger)
    bonificaciones           = Column(Numeric(18, 4))

    # Lookups stg_query
    centro_distribucion      = Column(String(50))
    zona_entrega             = Column(String(50))

    # Lookup cartera (debia estar desde el inicio pero quedo afuera; los
    # otros 'nombre_*' si lo tenian. int_ventas_bi tambien lo tiene, asi
    # que ahora el INSERT...SELECT del UPSERT propaga el valor correcto).
    nombre_destinatario      = Column(String(500))
