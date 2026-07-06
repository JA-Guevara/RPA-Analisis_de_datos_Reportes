"""Tabla SQL stg_query — snapshot crudo del Excel SAP QUERY (Hoja1).

Persiste solo las primeras 57 cols estables del SAP. Las cols 58-71 del
Excel (anotaciones manuales tipo "pedidos enero", "PNC FOSA FEBRERO",
etc.) se ignoran porque cambian de nombre cada mes.

stg_query NO se normaliza por ahora. La logica de int_query vendra en
fase 2 cuando se compongan los otros 3 archivos del area de ventas.

GD20 hace JOIN contra esta tabla por destinatario_mcia para resolver
centro_distribucion y zona_descarga.
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


class StgQueryModel(Base, TimestampsMixin):
    __tablename__ = "stg_query"
    __table_args__ = (
        Index("ix_stg_query_destinatario_mcia", "destinatario_mcia"),
        Index("ix_stg_query_documento_venta", "documento_venta"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    centro_proveedor              = Column(String(20))
    sucursal                      = Column(String(50))
    material                      = Column(BigInteger)
    nombre_material               = Column(String(200))
    dia_natural                   = Column(String(20))
    documento_venta               = Column(BigInteger)
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
    cantidad                      = Column(Numeric(18, 4))
    xx                            = Column(String(50))
    xx2                           = Column(String(50))
    xx3                           = Column(String(50))
    xx4                           = Column(String(50))
    fecha                         = Column(DateTime)
    despacho_t                    = Column(Numeric(18, 4))
    departamento                  = Column(String(50))
    traslados_t                   = Column(Numeric(18, 4))
    dia                           = Column(Integer)
    mes                           = Column(Integer)
    anio                          = Column(Integer)
    grupo_producto                = Column(String(100))
    tipo_traslado                 = Column(String(50))
    producto                      = Column(String(200))
    centro_distribucion           = Column(String(100))
    link                          = Column(String(200))
    provincia                     = Column(String(100))
    semana_anio                   = Column(Integer)
    traslados                     = Column(Numeric(18, 4))
    zona_descarga                 = Column(String(50))
    cd                            = Column(String(20))
    localidad                     = Column(String(100))
    distancia_km                  = Column(Integer)
    tipo_venta_2                  = Column(String(50))
    vendedor                      = Column(String(100))
    desarrollador                 = Column(String(100))
