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


class Gd20StgModel(Base, TimestampsMixin):
    __tablename__ = "stg_gd20"
    __table_args__ = (
        Index("ix_stg_gd20_documento_comercial", "documento_comercial"),
        Index("ix_stg_gd20_cliente", "cliente"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    ejercicio = Column(String(10))
    sociedad = Column(String(10))
    organizacion_ventas = Column(String(10))
    centro = Column(String(10))
    division = Column(String(10))
    oficina_ventas = Column(String(10))
    canal_distribucion = Column(String(10))
    sector = Column(String(10))
    numero_cuenta = Column(BigInteger)
    centro_beneficio = Column(String(50))

    material = Column(BigInteger)
    unidad_medida_base = Column(String(10))
    periodo_contable = Column(String(10))

    clave_pais_region = Column(String(10))
    region = Column(String(10))
    poblacion = Column(String(100))
    grupo_vendedores = Column(String(10))

    cliente = Column(BigInteger)
    emisor_orden = Column(BigInteger)
    customer_bill_to = Column(BigInteger)
    customer_rebate = Column(BigInteger)
    grupo_clientes_2 = Column(String(10))
    atributo_6 = Column(String(10))
    atributo_7 = Column(String(10))
    atributo_10 = Column(String(10))
    clase_factura = Column(String(10))
    nombre_usuario = Column(String(50))
    texto = Column(String(200))
    numero_documento = Column(BigInteger)
    cantidad = Column(Numeric(18, 4))
    moneda_sociedad = Column(Numeric(18, 4))
    fe_contabilizacion = Column(DateTime)
    fecha_entrada = Column(DateTime)
    fecha_valor = Column(DateTime)
    documento_comercial = Column(BigInteger)
    hora_entrada = Column(String(20))
    moneda_transaccion = Column(Numeric(18, 4))
    clave_moneda_transaccion = Column(String(10))
    moneda_fuerte = Column(Numeric(18, 4))
    clave_moneda_fuerte = Column(String(10))

    numero_doc_referencia = Column(BigInteger)
    numero_documento_2 = Column(BigInteger)

    incoterms = Column(String(10))
    incoterms_parte_2 = Column(String(50))
    clase_documento = Column(String(10))
    cond_pago = Column(String(10))
    dias_1 = Column(Integer)
    numero_transporte = Column(BigInteger)
    e = Column(String(10))


class Gd20IntModel(Base, TimestampsMixin):
    __tablename__ = "int_gd20"
    __table_args__ = (
        Index("ix_int_gd20_documento_comercial", "documento_comercial"),
        Index("ix_int_gd20_pagador", "pagador"),
        Index("ix_int_gd20_destinatario", "destinatario"),
        Index("ix_int_gd20_fe_contabilizacion", "fe_contabilizacion"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    ejercicio = Column(Integer)
    sociedad = Column(Integer)
    organizacion_ventas = Column(Integer)
    centro = Column(String(20))
    division = Column(String(20))
    oficina_ventas = Column(String(20))
    canal_distribucion = Column(Integer)
    sector = Column(Integer)
    numero_cuenta = Column(BigInteger)
    centro_beneficio = Column(String(50))
    material = Column(BigInteger)
    unidad_medida_base = Column(String(10))
    periodo_contable = Column(Integer)
    clave_pais = Column(String(10))
    region_sap = Column(String(10))
    poblacion_sap = Column(String(100))
    grupo_vendedores = Column(String(20))

    pagador = Column(BigInteger)
    emisor_solicitante = Column(BigInteger)
    customer_bill_to = Column(BigInteger)
    destinatario = Column(BigInteger)

    grupo_clientes_2 = Column(Integer)
    atributo_6 = Column(String(20))
    atributo_7 = Column(String(20))
    atributo_10 = Column(String(20))
    clase_factura = Column(String(20))
    nombre_usuario = Column(String(50))
    texto = Column(String(250))
    numero_documento = Column(BigInteger)
    cantidad = Column(Numeric(18, 4))
    moneda_sociedad = Column(Numeric(18, 4))
    fe_contabilizacion = Column(DateTime)
    fecha_entrada = Column(DateTime)
    fecha_valor = Column(DateTime)
    documento_comercial = Column(BigInteger)
    hora_entrada = Column(String(20))
    moneda_transaccion = Column(Numeric(18, 4))
    clave_moneda_transaccion = Column(String(10))
    moneda_fuerte = Column(Numeric(18, 4))
    clave_moneda_fuerte = Column(String(10))
    numero_doc_referencia = Column(BigInteger)
    numero_documento_2 = Column(BigInteger)

    incoterms = Column(String(20))
    incoterms_parte_2 = Column(String(100))
    clase_documento = Column(String(20))
    cond_pago = Column(String(20))
    dias_1 = Column(Integer)
    numero_transporte = Column(BigInteger)
    e = Column(String(10))

    tipo_embalaje = Column(String(50))
    nombre_producto = Column(String(250))
    volumen_toneladas = Column(Numeric(18, 4))

    nombre_pagador = Column(String(500))
    nombre_solicitante = Column(String(500))
    vendedor_sap = Column(String(150))
    vendedor = Column(String(150))
    vendedor_ok = Column(String(150))
    gerencia = Column(String(150))
    equipo = Column(String(150))
    canal = Column(String(100))
    sub_canal = Column(String(100))

    dia = Column(Integer)
    mes = Column(Integer)
    anio = Column(Integer)

    tipo_venta = Column(String(50))
    localidad = Column(String(200))
    provincia = Column(String(200))
    dpto = Column(String(100))
    region_m = Column(String(100))
    ingreso_bruto = Column(Numeric(18, 4))
    dpto_pagador = Column(String(100))
    localidad_pagador = Column(String(200))
    codigo_cliente = Column(BigInteger)
    bonificaciones = Column(Numeric(18, 4))

    centro_distribucion = Column(String(100))
    zona_entrega = Column(String(100))

    nombre_destinatario = Column(String(500))
