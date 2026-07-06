"""Tabla SQL int_despacho_bi — detalle BI de despachos.

41 cols heredadas de int_query + 10 cols enriquecidas en Fase 2.
Equivale a la hoja DESPACHOS BI del basepanel.xlsm.

Modo de carga: TRUNCATE + INSERT por corrida (idéntico a int_gd20).
Si en el futuro se necesita histórico SCD2 estilo int_ventas_bi, se
agrega entonces; por ahora int_despacho_bi refleja el último estado
de int_query.
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


class DespachoBiIntModel(Base, TimestampsMixin):
    __tablename__ = "int_despacho_bi"
    __table_args__ = (
        Index("ix_int_despacho_bi_documento_venta", "documento_venta"),
        Index("ix_int_despacho_bi_destinatario_mcia", "destinatario_mcia"),
        Index("ix_int_despacho_bi_codigo_cliente", "codigo_cliente"),
        Index("ix_int_despacho_bi_anio_mes", "anio", "mes"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    # ─── Subset raw copiado desde int_query ──────────────────────────────
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
    # ── 5 cols agregadas tras auditoria basepanel ───────────────────────
    atributo_7                    = Column(String(20))
    departamento_facturacion      = Column(String(100))
    nombre_transportista_persona  = Column(String(200))
    telefono_1                    = Column(String(50))
    tipo_servicio_transporte      = Column(String(100))
    # ────────────────────────────────────────────────────────────────────
    clase_expedicion              = Column(String(50))
    vc_embalaje                   = Column(String(20))
    transportista                 = Column(BigInteger)
    nombre_transportista          = Column(String(200))
    placa                         = Column(String(50))
    tp_vehiculo                   = Column(String(100))
    ruta                          = Column(String(20))
    nombre_ruta                   = Column(String(200))
    distancia_km                  = Column(Integer)
    distancia                     = Column(Numeric(10, 2))
    cantidad                      = Column(Numeric(18, 4))
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
    link                          = Column(String(500))     # = concat 5 cols (col AN del cliente)
    provincia                     = Column(String(100))
    semana_anio                   = Column(Integer)
    traslados                     = Column(Numeric(18, 4))
    zona_descarga                 = Column(String(50))
    cd                            = Column(String(20))     # etiqueta "CD" literal del cliente
    localidad                     = Column(String(100))
    tipo_venta_2                  = Column(String(50))
    vendedor                      = Column(String(100))
    desarrollador                 = Column(String(100))

    # ─── Enriquecidas (cols AV:BD del cliente en DESPACHOS BI) ──────────
    # Mapeo a fórmulas del basepanel:
    # AV VENDEDOR        = VLOOKUP(codigo_cliente, CARTERA col 33 = 'Vendedor')
    # AW DESARROLLADOR   = VLOOKUP(vendedor, REF.O:S col 3 = 'VENDEDOR OK')
    # AX CODIGO CLIENTE  = IF(LEN(destinatario)<=5, lookup centro, destinatario)
    # AY EQUIPO          = IF "CEMENTO" in producto → via vendedor, else via grupo_vendedores
    # AZ LOCALIDAD IM    = VLOOKUP(localidad, REF.A:B col 2)
    # BA INCOTERMS IM    = incoterms + centro_distribucion
    # BB GERENCIA        = VLOOKUP(equipo, REF.R:S col 2)
    # BC Semana          = VLOOKUP(dia, REF.U:V col 2)
    # BD x               = dia (espejo)
    codigo_cliente   = Column(BigInteger)
    nombre_cliente   = Column(String(500))
    vendedor_cartera = Column(String(100))   # = AV VENDEDOR del cliente
    equipo           = Column(String(100))
    gerencia         = Column(String(100))
    canal            = Column(String(100))   # solo para alimentar DESPACHO_MES
    localidad_im     = Column(String(100))
    incoterms_im     = Column(String(200))
    semana           = Column(String(20))
    x                = Column(Integer)       # espejo de dia (col BD del cliente)
