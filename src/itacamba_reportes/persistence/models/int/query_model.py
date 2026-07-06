"""Tabla SQL int_query — QUERY normalizado del mes objetivo.

Mismo esqueleto que stg_query pero:
  - sin cols scratch (xx, xx2, xx3, xx4),
  - centro_receptor sin "#" (ya convertido a 0),
  - filtrado al mes objetivo del reporte.

Es el insumo del pipeline DESPACHO BI (alimenta los joins por
destinatario_mcia, documento_venta y centro_receptor).
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


class IntQueryModel(Base, TimestampsMixin):
    __tablename__ = "int_query"
    __table_args__ = (
        Index("ix_int_query_destinatario_mcia", "destinatario_mcia"),
        Index("ix_int_query_documento_venta", "documento_venta"),
        Index("ix_int_query_centro_receptor", "centro_receptor"),
        Index("ix_int_query_anio_mes", "anio", "mes"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Identificación y origen
    centro_proveedor              = Column(String(20))
    sucursal                      = Column(String(50))

    # Material
    material                      = Column(BigInteger)
    nombre_material               = Column(String(200))

    # Documento de venta
    dia_natural                   = Column(String(20))
    documento_venta               = Column(BigInteger)

    # Destinatario / receptor
    destinatario_mcia             = Column(BigInteger)
    nombre_centro_destinatario    = Column(String(200))
    poblacion                     = Column(String(100))
    incoterms                     = Column(String(10))
    clase_doc_ventas              = Column(String(10))
    tipo_venta                    = Column(String(50))
    centro_receptor               = Column(String(20))
    nombre_centro_receptor        = Column(String(200))
    ship_to_zkatr7                = Column(String(50))
    ship_to_region                = Column(String(50))

    # ── 5 cols agregadas tras auditoria basepanel ────────────────────────
    atributo_7                    = Column(String(20))
    departamento_facturacion      = Column(String(100))
    nombre_transportista_persona  = Column(String(200))
    telefono_1                    = Column(String(50))
    tipo_servicio_transporte      = Column(String(100))

    # Expedición / transporte
    clase_expedicion              = Column(String(50))
    vc_embalaje                   = Column(String(20))
    transportista                 = Column(BigInteger)
    nombre_transportista          = Column(String(200))
    nombre                        = Column(String(200))
    telefono_1                    = Column(String(50))
    forwagent_accnt_g             = Column(String(100))
    placa                         = Column(String(50))
    tp_vehiculo                   = Column(String(100))
    ruta                          = Column(String(20))
    nombre_ruta                   = Column(String(200))
    punto_entrega                 = Column(String(100))
    numero_transporte             = Column(BigInteger)
    distancia                     = Column(Numeric(10, 2))

    # Cantidades y métricas
    cantidad                      = Column(Numeric(18, 4))
    fecha                         = Column(DateTime)
    despacho_t                    = Column(Numeric(18, 4))
    departamento                  = Column(String(50))
    traslados_t                   = Column(Numeric(18, 4))

    # Splits de fecha (usados por EliminarMeses + Despacho BI)
    dia                           = Column(Integer)
    mes                           = Column(Integer)
    anio                          = Column(Integer)

    # Producto / categorización
    grupo_producto                = Column(String(100))
    tipo_traslado                 = Column(String(50))
    producto                      = Column(String(200))
    centro_distribucion           = Column(String(100))

    # Ubicación
    provincia                     = Column(String(100))
    semana_anio                   = Column(Integer)
    traslados                     = Column(Numeric(18, 4))
    zona_descarga                 = Column(String(50))
    cd                            = Column(String(20))
    localidad                     = Column(String(100))
    distancia_km                  = Column(Integer)

    # Comercial
    tipo_venta_2                  = Column(String(50))
    vendedor                      = Column(String(100))
    desarrollador                 = Column(String(100))
