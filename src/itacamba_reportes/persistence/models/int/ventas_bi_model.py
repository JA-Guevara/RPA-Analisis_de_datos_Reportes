"""Tabla SQL int_ventas_bi — historico consolidado de ventas (BI).

Mismo schema que int_gd20 (49 raw + 26 derivadas) + indices para reportes BI.

Granularidad: 1 fila por LINEA de documento (cada material es una fila).
Un mismo documento_comercial puede tener N filas (N materiales/productos).

UPSERT: borra TODAS las lineas de (documento_comercial, ejercicio) coincidentes
en int_gd20, luego re-inserta TODAS las lineas nuevas.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
)

from itacamba_reportes.persistence.base import Base
from itacamba_reportes.persistence.mixins import TimestampsMixin


class VentasBiIntModel(Base, TimestampsMixin):
    __tablename__ = "int_ventas_bi"
    __table_args__ = (
        # Index compuesto NO-unique: documento+ejercicio tiene N lineas
        Index("ix_int_ventas_bi_doc_ejercicio",
              "documento_comercial", "ejercicio"),
        # Indices para reportes BI
        Index("ix_int_ventas_bi_fe_contabilizacion", "fe_contabilizacion"),
        Index("ix_int_ventas_bi_anio_mes", "anio", "mes"),
        Index("ix_int_ventas_bi_pagador", "pagador"),
        Index("ix_int_ventas_bi_destinatario", "destinatario"),
        Index("ix_int_ventas_bi_vendedor_ok", "vendedor_ok"),
        Index("ix_int_ventas_bi_material", "material"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    # ─── 49 cols del SAP raw (post-rename a INT) ───
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
    material                 = Column(BigInteger)
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

    # ─── 26 cols derivadas ───
    tipo_embalaje            = Column(String(20))
    nombre_producto          = Column(String(200))
    volumen_toneladas        = Column(Numeric(18, 4))

    nombre_pagador           = Column(String(500))
    nombre_solicitante       = Column(String(500))
    vendedor_sap             = Column(String(100))
    vendedor                 = Column(String(100))
    vendedor_ok              = Column(String(100))
    gerencia                 = Column(String(100))
    equipo                   = Column(String(100))
    canal                    = Column(String(50))
    sub_canal                = Column(String(100))

    dia                      = Column(Integer)
    mes                      = Column(Integer)
    anio                     = Column(Integer)

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

    centro_distribucion      = Column(String(50))
    zona_entrega             = Column(String(50))

    nombre_destinatario      = Column(String(500))

    # ─── METADATOS SCD2 + AUDITORÍA ─────────────────────────────────────
    # Patron Slowly Changing Dimension Type 2 driven by hash:
    # cada fila representa UNA VERSION de un (documento_comercial, numero_documento,
    # ejercicio, material). Si SAP corrige, se cierra la version actual y se inserta
    # una nueva. Si solo cambian derivados (lookups), aplica logica "sticky semántico".

    # Versionado y vigencia
    version              = Column(Integer, nullable=False, default=1)
    is_current           = Column(Boolean, nullable=False, default=True)
    valid_from           = Column(DateTime, nullable=False)
    valid_to             = Column(DateTime, nullable=True)

    # Hashes — detección O(1) de cambios
    source_hash          = Column(String(64), nullable=True)   # SAP raw → versiona
    derived_hash         = Column(String(64), nullable=True)   # lookups → rescate
    full_row_hash        = Column(String(64), nullable=True)   # toda la fila

    # Estado semántico de CD/ZE
    # PENDING: CD='OTROS', puede rescatarse en futuras corridas
    # RESOLVED: CD!=OTROS, calculado por el bot. Cambia solo si SAP corrige.
    # LOCKED: CD asignado manualmente o bloqueado por admin. No se toca.
    cd_status            = Column(String(15), nullable=False, default="PENDING")

    # Flags de calidad (JSON) — futuras alertas: missing_query, malformed_dpto, etc.
    quality_flags        = Column(String(500), nullable=True)

    # Trazabilidad: cada fila apunta a la corrida que la creó/actualizó
    source_execution_id  = Column(String(36), nullable=True)

    # Sticky CD/ZE (legacy: cuándo CD pasó a estado RESOLVED/LOCKED)
    cd_locked_at         = Column(DateTime, nullable=True)
