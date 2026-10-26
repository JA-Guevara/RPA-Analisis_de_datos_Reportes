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

    # 56 columnas oficiales de negocio (alineadas 1-a-1 a HISTORIAL VENTAS y BasePanel)
    centro_origen = Column(String(20))
    ds_centro_origen = Column(String(200))
    cod_material = Column(BigInteger)
    material = Column(String(200))
    fecha_salida = Column(DateTime, nullable=True)
    nro_pedido = Column(BigInteger)
    cod_destinatario = Column(BigInteger)
    nom_destinatario = Column(String(200))
    poblacion = Column(String(100))
    incoterm = Column(String(20))
    clase_doc_ventas = Column(String(50))
    centro_destino = Column(String(20))
    ds_centro_destino = Column(String(200))
    atributo_7 = Column(String(50))
    departamento_facturacion = Column(String(100))
    clase_expedicion = Column(String(50))
    vc_embalaje = Column(String(20))
    cod_transportista = Column(BigInteger)
    transportista = Column(String(200))
    nombre_transportista = Column(String(200))
    telefono_1 = Column(String(50))
    tipo_servicio_transporte = Column(String(100))
    placa = Column(String(50))
    tipo_vehiculo = Column(String(100))
    cod_ruta = Column(String(50))
    nom_ruta = Column(String(200))
    distancia_km = Column(String(50))
    numero_transporte = Column(BigInteger)
    distancia = Column(Numeric(18, 4))
    cantidad = Column(Numeric(18, 4))
    despacho_t = Column(Numeric(18, 4))
    departamento = Column(String(100))
    traslados_t = Column(Numeric(18, 4))
    mes = Column(Integer)
    anio = Column(Integer)
    grupo_producto = Column(String(100))
    tipo_traslado = Column(String(100))
    producto = Column(String(200))
    centro_distribucion = Column(String(100))
    link = Column(String(200))
    provincia = Column(String(100))
    semana_anio = Column(Integer)
    traslados = Column(BigInteger)
    zona_descarga = Column(String(100))
    cd = Column(String(20))
    localidad = Column(String(100))
    tipo_venta = Column(String(50))
    vendedor = Column(String(150))
    desarrollador = Column(String(150))
    codigo_cliente = Column(BigInteger)
    nombre_cliente = Column(String(500))
    equipo = Column(String(150))
    localidad_im = Column(String(150))
    incoterms_im = Column(String(100))
    gerencia = Column(String(150))
    semana = Column(String(50))
    dia = Column(Integer)

    # Columnas auxiliares internas
    canal = Column(String(100))
    cod_pagador = Column(BigInteger)
    pagador = Column(String(200))
