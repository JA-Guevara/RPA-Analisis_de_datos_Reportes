"""Initial schema — esquema completo del DW Itacamba Reportes.

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-10

Crea las 16 tablas del proyecto en una sola migracion:

  STG  (Bronze)  : stg_cartera, stg_gd20, stg_query

  REF  (catalogos): int_ref_almacen, int_ref_centro, int_ref_equipo,
                    int_ref_localidad, int_ref_material, int_ref_semana

  INT VENTAS BI  : int_cartera, int_gd20
                   int_ventas_bi (FACT TABLE con SCD Type 2 by-hash)

  INT DESPACHOS  : int_query, int_despacho_bi, int_despacho_mes

  AUDIT          : pipeline_executions

Patron aplicado en int_ventas_bi:
  - SCD Type 2 (versionado por hash)
  - Sticky semantico en CD/ZE (centro_distribucion, zona_entrega)
  - Trazabilidad: source_execution_id -> pipeline_executions.id

Idempotente: si una tabla ya existe, se omite.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def _ts() -> tuple[sa.Column, sa.Column]:
    """Cols created_at / updated_at NOT NULL DEFAULT CURRENT_TIMESTAMP."""
    return (
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def _exists(inspector, name: str) -> bool:
    return name in inspector.get_table_names()


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    # ════════════════════════════════════════════════════════════════════
    # STG — snapshots crudos del Excel SAP
    # ════════════════════════════════════════════════════════════════════

    if not _exists(insp, "stg_cartera"):
        op.create_table(
            "stg_cartera",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("run_id", sa.DateTime(), nullable=False),
            sa.Column("row_index", sa.Integer(), nullable=False),
            sa.Column("cliente", sa.String(50)),
            sa.Column("column2", sa.String(500)),
            sa.Column("attribute_10", sa.String(100)),
            sa.Column("poblacion", sa.String(200)),
            sa.Column("barrio", sa.String(200)),
            sa.Column("attribute_7", sa.String(100)),
            sa.Column("attribute_6", sa.String(100)),
            sa.Column("region", sa.String(10)),
            sa.Column("column9", sa.String(100)),
            sa.Column("grupo_de_cuentas", sa.String(20)),
            sa.Column("column11", sa.String(200)),
            sa.Column("telefono", sa.String(50)),
            sa.Column("nif_1", sa.String(50)),
            sa.Column("codigo_postal", sa.String(20)),
            sa.Column("gcd_codemplazfiscal", sa.String(50)),
            sa.Column("calle", sa.String(500)),
            sa.Column("inclusion_date", sa.String(50)),
            sa.Column("tipo_de_operacion", sa.String(50)),
            sa.Column("zemailadd", sa.String(100)),
            sa.Column("zvcrisk", sa.String(50)),
            sa.Column("via_de_pago", sa.String(50)),
            sa.Column("sector", sa.String(50)),
            sa.Column("column23", sa.String(200)),
            sa.Column("canal_distribucion", sa.String(50)),
            sa.Column("column25", sa.String(200)),
            sa.Column("organizacion_de_ventas", sa.String(50)),
            sa.Column("column27", sa.String(200)),
            sa.Column("oficina_de_ventas", sa.String(50)),
            sa.Column("column29", sa.String(200)),
            sa.Column("grupo_de_vendedores", sa.String(50)),
            sa.Column("equipo", sa.String(100)),
            sa.Column("representante_ventas", sa.String(100)),
            sa.Column("vendedor", sa.String(100)),
            sa.Column("coordinador_ventas", sa.String(100)),
            sa.Column("coordinador", sa.String(100)),
            sa.Column("trilha", sa.String(50)),
            sa.Column("canal", sa.String(100)),
            sa.Column("condicion_pago", sa.String(50)),
            sa.Column("contador", sa.String(50)),
            *_ts(),
        )
        op.create_index("ix_stg_cartera_run_id", "stg_cartera", ["run_id"])
        op.create_index("ix_stg_cartera_cliente", "stg_cartera", ["cliente"])

    if not _exists(insp, "stg_gd20"):
        op.create_table(
            "stg_gd20",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("ejercicio", sa.String(10)),
            sa.Column("sociedad", sa.String(10)),
            sa.Column("organizacion_ventas", sa.String(10)),
            sa.Column("centro", sa.String(10)),
            sa.Column("division", sa.String(10)),
            sa.Column("oficina_ventas", sa.String(10)),
            sa.Column("canal_distribucion", sa.String(10)),
            sa.Column("sector", sa.String(10)),
            sa.Column("numero_cuenta", sa.BigInteger()),
            sa.Column("centro_beneficio", sa.String(50)),
            sa.Column("material", sa.BigInteger()),
            sa.Column("unidad_medida_base", sa.String(10)),
            sa.Column("periodo_contable", sa.String(10)),
            sa.Column("clave_pais_region", sa.String(10)),
            sa.Column("region", sa.String(10)),
            sa.Column("poblacion", sa.String(100)),
            sa.Column("grupo_vendedores", sa.String(10)),
            sa.Column("cliente", sa.BigInteger()),
            sa.Column("emisor_orden", sa.BigInteger()),
            sa.Column("customer_bill_to", sa.BigInteger()),
            sa.Column("customer_rebate", sa.BigInteger()),
            sa.Column("grupo_clientes_2", sa.String(10)),
            sa.Column("atributo_6", sa.String(10)),
            sa.Column("atributo_7", sa.String(10)),
            sa.Column("atributo_10", sa.String(10)),
            sa.Column("clase_factura", sa.String(10)),
            sa.Column("nombre_usuario", sa.String(50)),
            sa.Column("texto", sa.String(200)),
            sa.Column("numero_documento", sa.BigInteger()),
            sa.Column("cantidad", sa.Numeric(18, 4)),
            sa.Column("moneda_sociedad", sa.Numeric(18, 4)),
            sa.Column("fe_contabilizacion", sa.DateTime()),
            sa.Column("fecha_entrada", sa.DateTime()),
            sa.Column("fecha_valor", sa.DateTime()),
            sa.Column("documento_comercial", sa.BigInteger()),
            sa.Column("hora_entrada", sa.String(20)),
            sa.Column("moneda_transaccion", sa.Numeric(18, 4)),
            sa.Column("clave_moneda_transaccion", sa.String(10)),
            sa.Column("moneda_fuerte", sa.Numeric(18, 4)),
            sa.Column("clave_moneda_fuerte", sa.String(10)),
            sa.Column("numero_doc_referencia", sa.BigInteger()),
            sa.Column("numero_documento_2", sa.BigInteger()),
            sa.Column("incoterms", sa.String(10)),
            sa.Column("incoterms_parte_2", sa.String(50)),
            sa.Column("clase_documento", sa.String(10)),
            sa.Column("cond_pago", sa.String(10)),
            sa.Column("dias_1", sa.Integer()),
            sa.Column("numero_transporte", sa.BigInteger()),
            *_ts(),
        )
        op.create_index("ix_stg_gd20_documento_comercial", "stg_gd20", ["documento_comercial"])
        op.create_index("ix_stg_gd20_cliente", "stg_gd20", ["cliente"])

    if not _exists(insp, "stg_query"):
        op.create_table(
            "stg_query",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("centro_proveedor", sa.String(20)),
            sa.Column("sucursal", sa.String(50)),
            sa.Column("material", sa.BigInteger()),
            sa.Column("nombre_material", sa.String(200)),
            sa.Column("dia_natural", sa.String(20)),
            sa.Column("documento_venta", sa.BigInteger()),
            sa.Column("destinatario_mcia", sa.BigInteger()),
            sa.Column("nombre_centro_destinatario", sa.String(200)),
            sa.Column("poblacion", sa.String(100)),
            sa.Column("incoterms", sa.String(10)),
            sa.Column("clase_doc_ventas", sa.String(10)),
            sa.Column("tipo_venta", sa.String(50)),
            sa.Column("centro_receptor", sa.String(20)),
            sa.Column("nombre_centro_receptor", sa.String(200)),
            sa.Column("ship_to_zkatr7", sa.String(50)),
            sa.Column("ship_to_region", sa.String(50)),
            sa.Column("clase_expedicion", sa.String(50)),
            sa.Column("vc_embalaje", sa.String(20)),
            sa.Column("transportista", sa.BigInteger()),
            sa.Column("nombre_transportista", sa.String(200)),
            sa.Column("nombre", sa.String(200)),
            sa.Column("telefono_1", sa.String(50)),
            sa.Column("forwagent_accnt_g", sa.String(100)),
            sa.Column("placa", sa.String(50)),
            sa.Column("tp_vehiculo", sa.String(100)),
            sa.Column("ruta", sa.String(20)),
            sa.Column("nombre_ruta", sa.String(200)),
            sa.Column("punto_entrega", sa.String(100)),
            sa.Column("numero_transporte", sa.BigInteger()),
            sa.Column("distancia", sa.Numeric(10, 2)),
            sa.Column("cantidad", sa.Numeric(18, 4)),
            sa.Column("xx", sa.String(50)),
            sa.Column("xx2", sa.String(50)),
            sa.Column("xx3", sa.String(50)),
            sa.Column("xx4", sa.String(50)),
            sa.Column("fecha", sa.DateTime()),
            sa.Column("despacho_t", sa.Numeric(18, 4)),
            sa.Column("departamento", sa.String(50)),
            sa.Column("traslados_t", sa.Numeric(18, 4)),
            sa.Column("dia", sa.Integer()),
            sa.Column("mes", sa.Integer()),
            sa.Column("anio", sa.Integer()),
            sa.Column("grupo_producto", sa.String(100)),
            sa.Column("tipo_traslado", sa.String(50)),
            sa.Column("producto", sa.String(200)),
            sa.Column("centro_distribucion", sa.String(100)),
            sa.Column("link", sa.String(200)),
            sa.Column("provincia", sa.String(100)),
            sa.Column("semana_anio", sa.Integer()),
            sa.Column("traslados", sa.Numeric(18, 4)),
            sa.Column("zona_descarga", sa.String(50)),
            sa.Column("cd", sa.String(20)),
            sa.Column("localidad", sa.String(100)),
            sa.Column("distancia_km", sa.Integer()),
            sa.Column("tipo_venta_2", sa.String(50)),
            sa.Column("vendedor", sa.String(100)),
            sa.Column("desarrollador", sa.String(100)),
            *_ts(),
        )
        op.create_index("ix_stg_query_destinatario_mcia", "stg_query", ["destinatario_mcia"])
        op.create_index("ix_stg_query_documento_venta", "stg_query", ["documento_venta"])

    # ════════════════════════════════════════════════════════════════════
    # REF — catalogos de lookup (Referencias.xlsx)
    # ════════════════════════════════════════════════════════════════════

    if not _exists(insp, "int_ref_almacen"):
        op.create_table(
            "int_ref_almacen",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("descripcion_sap", sa.String(100), nullable=False, unique=True),
            sa.Column("segmento", sa.String(200)),
            sa.Column("canal", sa.String(50)),
            *_ts(),
        )
        op.create_index("ix_int_ref_almacen_descripcion_sap",
                        "int_ref_almacen", ["descripcion_sap"])

    if not _exists(insp, "int_ref_centro"):
        op.create_table(
            "int_ref_centro",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("centro", sa.String(10), nullable=True),
            sa.Column("codigo_sap_cliente", sa.BigInteger(), nullable=True),
            sa.Column("tipo", sa.String(50)),
            *_ts(),
        )
        op.create_index("ix_int_ref_centro_centro", "int_ref_centro", ["centro"])
        op.create_index("ix_int_ref_centro_codigo_sap_cliente",
                        "int_ref_centro", ["codigo_sap_cliente"])

    if not _exists(insp, "int_ref_equipo"):
        op.create_table(
            "int_ref_equipo",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("grupo_vendedores", sa.String(10), nullable=True),
            sa.Column("vendedor_sap", sa.String(200), nullable=True),
            sa.Column("vendedor", sa.String(200), nullable=True),
            sa.Column("vendedor_ok", sa.String(100), nullable=True),
            sa.Column("equipo", sa.String(100), nullable=True),
            sa.Column("gerencia", sa.String(100), nullable=True),
            *_ts(),
        )
        op.create_index("ix_int_ref_equipo_grupo_vendedores",
                        "int_ref_equipo", ["grupo_vendedores"])
        op.create_index("ix_int_ref_equipo_vendedor_ok",
                        "int_ref_equipo", ["vendedor_ok"])

    if not _exists(insp, "int_ref_localidad"):
        op.create_table(
            "int_ref_localidad",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("localidad_despacho", sa.String(200), nullable=False, unique=True),
            sa.Column("localidad_im", sa.String(100)),
            *_ts(),
        )
        op.create_index("ix_int_ref_localidad_localidad_despacho",
                        "int_ref_localidad", ["localidad_despacho"])

    if not _exists(insp, "int_ref_material"):
        op.create_table(
            "int_ref_material",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("codigo", sa.BigInteger(), nullable=False, unique=True),
            sa.Column("descripcion", sa.String(300)),
            *_ts(),
        )
        op.create_index("ix_int_ref_material_codigo",
                        "int_ref_material", ["codigo"])

    if not _exists(insp, "int_ref_semana"):
        op.create_table(
            "int_ref_semana",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("dia", sa.Integer(), nullable=False, unique=True),
            sa.Column("semana", sa.String(20)),
            *_ts(),
        )
        op.create_index("ix_int_ref_semana_dia", "int_ref_semana", ["dia"])

    # ════════════════════════════════════════════════════════════════════
    # INT VENTAS BI
    # ════════════════════════════════════════════════════════════════════

    if not _exists(insp, "int_cartera"):
        op.create_table(
            "int_cartera",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("cliente", sa.BigInteger(), nullable=False),
            sa.Column("nombre_cliente", sa.String(500)),
            sa.Column("attribute_10", sa.String(100)),
            sa.Column("attribute_7", sa.String(100)),
            sa.Column("attribute_6", sa.String(100)),
            sa.Column("poblacion", sa.String(200)),
            sa.Column("barrio", sa.String(200)),
            sa.Column("calle", sa.String(500)),
            sa.Column("codigo_postal", sa.String(20)),
            sa.Column("region", sa.String(10)),
            sa.Column("region_nombre", sa.String(100)),
            sa.Column("telefono", sa.String(50)),
            sa.Column("nit", sa.String(50)),
            sa.Column("gcd_cod_emplaz_fiscal", sa.String(50)),
            sa.Column("grupo_cuentas", sa.String(20)),
            sa.Column("grupo_cuentas_desc", sa.String(200)),
            sa.Column("sector", sa.String(10)),
            sa.Column("sector_desc", sa.String(200)),
            sa.Column("canal_distribucion", sa.String(20)),
            sa.Column("canal_distribucion_desc", sa.String(200)),
            sa.Column("organizacion_ventas", sa.String(20)),
            sa.Column("organizacion_ventas_desc", sa.String(200)),
            sa.Column("oficina_ventas", sa.String(20)),
            sa.Column("oficina_ventas_desc", sa.String(200)),
            sa.Column("grupo_vendedores", sa.String(20)),
            sa.Column("equipo", sa.String(100)),
            sa.Column("representante_ventas", sa.String(100)),
            sa.Column("vendedor", sa.String(100)),
            sa.Column("coordinador_ventas", sa.String(100)),
            sa.Column("coordinador", sa.String(100)),
            sa.Column("via_pago", sa.String(50)),
            sa.Column("condicion_pago", sa.String(50)),
            sa.Column("trilha", sa.String(50)),
            sa.Column("canal", sa.String(50)),
            sa.Column("zemailadd", sa.String(100)),
            sa.Column("zvcrisk", sa.String(50)),
            sa.Column("tipo_operacion", sa.String(50)),
            sa.Column("contador", sa.Integer()),
            sa.Column("fecha_inclusion", sa.DateTime()),
            sa.UniqueConstraint(
                "cliente", "sector", "organizacion_ventas", "oficina_ventas",
                name="uq_int_cartera_cliente_sector_org_oficina",
            ),
            *_ts(),
        )
        op.create_index("ix_int_cartera_cliente", "int_cartera", ["cliente"])

    if not _exists(insp, "int_gd20"):
        op.create_table(
            "int_gd20",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("ejercicio", sa.Integer()),
            sa.Column("sociedad", sa.Integer()),
            sa.Column("organizacion_ventas", sa.Integer()),
            sa.Column("centro", sa.String(10)),
            sa.Column("division", sa.String(10)),
            sa.Column("oficina_ventas", sa.String(10)),
            sa.Column("canal_distribucion", sa.Integer()),
            sa.Column("sector", sa.Integer()),
            sa.Column("numero_cuenta", sa.BigInteger()),
            sa.Column("centro_beneficio", sa.String(50)),
            sa.Column("material", sa.BigInteger()),
            sa.Column("unidad_medida_base", sa.String(10)),
            sa.Column("periodo_contable", sa.Integer()),
            sa.Column("clave_pais", sa.String(5)),
            sa.Column("region_sap", sa.String(5)),
            sa.Column("poblacion_sap", sa.String(100)),
            sa.Column("grupo_vendedores", sa.String(10)),
            sa.Column("pagador", sa.BigInteger()),
            sa.Column("emisor_solicitante", sa.BigInteger()),
            sa.Column("customer_bill_to", sa.BigInteger()),
            sa.Column("destinatario", sa.BigInteger()),
            sa.Column("grupo_clientes_2", sa.Integer()),
            sa.Column("atributo_6", sa.String(10)),
            sa.Column("atributo_7", sa.String(10)),
            sa.Column("atributo_10", sa.String(10)),
            sa.Column("clase_factura", sa.String(10)),
            sa.Column("nombre_usuario", sa.String(50)),
            sa.Column("texto", sa.String(200)),
            sa.Column("numero_documento", sa.BigInteger()),
            sa.Column("cantidad", sa.Numeric(18, 4)),
            sa.Column("moneda_sociedad", sa.Numeric(18, 4)),
            sa.Column("fe_contabilizacion", sa.DateTime()),
            sa.Column("fecha_entrada", sa.DateTime()),
            sa.Column("fecha_valor", sa.DateTime()),
            sa.Column("documento_comercial", sa.BigInteger()),
            sa.Column("hora_entrada", sa.String(20)),
            sa.Column("moneda_transaccion", sa.Numeric(18, 4)),
            sa.Column("clave_moneda_transaccion", sa.String(10)),
            sa.Column("moneda_fuerte", sa.Numeric(18, 4)),
            sa.Column("clave_moneda_fuerte", sa.String(10)),
            sa.Column("numero_doc_referencia", sa.BigInteger()),
            sa.Column("numero_documento_2", sa.BigInteger()),
            sa.Column("incoterms", sa.String(10)),
            sa.Column("incoterms_parte_2", sa.String(50)),
            sa.Column("clase_documento", sa.String(10)),
            sa.Column("cond_pago", sa.String(10)),
            sa.Column("dias_1", sa.Integer()),
            sa.Column("numero_transporte", sa.BigInteger()),
            sa.Column("e", sa.String(10)),
            sa.Column("tipo_embalaje", sa.String(20)),
            sa.Column("nombre_producto", sa.String(200)),
            sa.Column("volumen_toneladas", sa.Numeric(18, 4)),
            sa.Column("nombre_pagador", sa.String(500)),
            sa.Column("nombre_solicitante", sa.String(500)),
            sa.Column("vendedor_sap", sa.String(100)),
            sa.Column("vendedor", sa.String(100)),
            sa.Column("vendedor_ok", sa.String(100)),
            sa.Column("gerencia", sa.String(100)),
            sa.Column("equipo", sa.String(100)),
            sa.Column("canal", sa.String(50)),
            sa.Column("sub_canal", sa.String(100)),
            sa.Column("dia", sa.Integer()),
            sa.Column("mes", sa.Integer()),
            sa.Column("anio", sa.Integer()),
            sa.Column("tipo_venta", sa.String(50)),
            sa.Column("localidad", sa.String(200)),
            sa.Column("provincia", sa.String(200)),
            sa.Column("dpto", sa.String(100)),
            sa.Column("region_m", sa.String(50)),
            sa.Column("ingreso_bruto", sa.Numeric(18, 4)),
            sa.Column("dpto_pagador", sa.String(100)),
            sa.Column("localidad_pagador", sa.String(200)),
            sa.Column("codigo_cliente", sa.BigInteger()),
            sa.Column("bonificaciones", sa.Numeric(18, 4)),
            sa.Column("centro_distribucion", sa.String(50)),
            sa.Column("zona_entrega", sa.String(50)),
            sa.Column("nombre_destinatario", sa.String(500)),
            *_ts(),
        )
        op.create_index("ix_int_gd20_material", "int_gd20", ["material"])
        op.create_index("ix_int_gd20_documento_comercial", "int_gd20", ["documento_comercial"])
        op.create_index("ix_int_gd20_pagador", "int_gd20", ["pagador"])
        op.create_index("ix_int_gd20_destinatario", "int_gd20", ["destinatario"])
        op.create_index("ix_int_gd20_fe_contabilizacion", "int_gd20", ["fe_contabilizacion"])

    if not _exists(insp, "int_ventas_bi"):
        op.create_table(
            "int_ventas_bi",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            # 49 raw
            sa.Column("ejercicio", sa.Integer()),
            sa.Column("sociedad", sa.Integer()),
            sa.Column("organizacion_ventas", sa.Integer()),
            sa.Column("centro", sa.String(10)),
            sa.Column("division", sa.String(10)),
            sa.Column("oficina_ventas", sa.String(10)),
            sa.Column("canal_distribucion", sa.Integer()),
            sa.Column("sector", sa.Integer()),
            sa.Column("numero_cuenta", sa.BigInteger()),
            sa.Column("centro_beneficio", sa.String(50)),
            sa.Column("material", sa.BigInteger()),
            sa.Column("unidad_medida_base", sa.String(10)),
            sa.Column("periodo_contable", sa.Integer()),
            sa.Column("clave_pais", sa.String(5)),
            sa.Column("region_sap", sa.String(5)),
            sa.Column("poblacion_sap", sa.String(100)),
            sa.Column("grupo_vendedores", sa.String(10)),
            sa.Column("pagador", sa.BigInteger()),
            sa.Column("emisor_solicitante", sa.BigInteger()),
            sa.Column("customer_bill_to", sa.BigInteger()),
            sa.Column("destinatario", sa.BigInteger()),
            sa.Column("grupo_clientes_2", sa.Integer()),
            sa.Column("atributo_6", sa.String(10)),
            sa.Column("atributo_7", sa.String(10)),
            sa.Column("atributo_10", sa.String(10)),
            sa.Column("clase_factura", sa.String(10)),
            sa.Column("nombre_usuario", sa.String(50)),
            sa.Column("texto", sa.String(200)),
            sa.Column("numero_documento", sa.BigInteger()),
            sa.Column("cantidad", sa.Numeric(18, 4)),
            sa.Column("moneda_sociedad", sa.Numeric(18, 4)),
            sa.Column("fe_contabilizacion", sa.DateTime()),
            sa.Column("fecha_entrada", sa.DateTime()),
            sa.Column("fecha_valor", sa.DateTime()),
            sa.Column("documento_comercial", sa.BigInteger()),
            sa.Column("hora_entrada", sa.String(20)),
            sa.Column("moneda_transaccion", sa.Numeric(18, 4)),
            sa.Column("clave_moneda_transaccion", sa.String(10)),
            sa.Column("moneda_fuerte", sa.Numeric(18, 4)),
            sa.Column("clave_moneda_fuerte", sa.String(10)),
            sa.Column("numero_doc_referencia", sa.BigInteger()),
            sa.Column("numero_documento_2", sa.BigInteger()),
            sa.Column("incoterms", sa.String(10)),
            sa.Column("incoterms_parte_2", sa.String(50)),
            sa.Column("clase_documento", sa.String(10)),
            sa.Column("cond_pago", sa.String(10)),
            sa.Column("dias_1", sa.Integer()),
            sa.Column("numero_transporte", sa.BigInteger()),
            sa.Column("e", sa.String(10)),
            # 26 derivadas
            sa.Column("tipo_embalaje", sa.String(20)),
            sa.Column("nombre_producto", sa.String(200)),
            sa.Column("volumen_toneladas", sa.Numeric(18, 4)),
            sa.Column("nombre_pagador", sa.String(500)),
            sa.Column("nombre_solicitante", sa.String(500)),
            sa.Column("vendedor_sap", sa.String(100)),
            sa.Column("vendedor", sa.String(100)),
            sa.Column("vendedor_ok", sa.String(100)),
            sa.Column("gerencia", sa.String(100)),
            sa.Column("equipo", sa.String(100)),
            sa.Column("canal", sa.String(50)),
            sa.Column("sub_canal", sa.String(100)),
            sa.Column("dia", sa.Integer()),
            sa.Column("mes", sa.Integer()),
            sa.Column("anio", sa.Integer()),
            sa.Column("tipo_venta", sa.String(50)),
            sa.Column("localidad", sa.String(200)),
            sa.Column("provincia", sa.String(200)),
            sa.Column("dpto", sa.String(100)),
            sa.Column("region_m", sa.String(50)),
            sa.Column("ingreso_bruto", sa.Numeric(18, 4)),
            sa.Column("dpto_pagador", sa.String(100)),
            sa.Column("localidad_pagador", sa.String(200)),
            sa.Column("codigo_cliente", sa.BigInteger()),
            sa.Column("bonificaciones", sa.Numeric(18, 4)),
            sa.Column("centro_distribucion", sa.String(50)),
            sa.Column("zona_entrega", sa.String(50)),
            sa.Column("nombre_destinatario", sa.String(500)),
            # SCD2 + auditoria
            sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("valid_from", sa.DateTime(), nullable=False,
                      server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("valid_to", sa.DateTime(), nullable=True),
            sa.Column("source_hash", sa.String(64), nullable=True),
            sa.Column("derived_hash", sa.String(64), nullable=True),
            sa.Column("full_row_hash", sa.String(64), nullable=True),
            sa.Column("cd_status", sa.String(15), nullable=False,
                      server_default=sa.text("'PENDING'")),
            sa.Column("quality_flags", sa.String(500), nullable=True),
            sa.Column("source_execution_id", sa.String(36), nullable=True),
            sa.Column("cd_locked_at", sa.DateTime(), nullable=True),
            *_ts(),
        )
        op.create_index("ix_int_ventas_bi_doc_ejercicio",
                        "int_ventas_bi", ["documento_comercial", "ejercicio"])
        op.create_index("ix_int_ventas_bi_fe_contabilizacion",
                        "int_ventas_bi", ["fe_contabilizacion"])
        op.create_index("ix_int_ventas_bi_anio_mes", "int_ventas_bi", ["anio", "mes"])
        op.create_index("ix_int_ventas_bi_pagador", "int_ventas_bi", ["pagador"])
        op.create_index("ix_int_ventas_bi_destinatario", "int_ventas_bi", ["destinatario"])
        op.create_index("ix_int_ventas_bi_vendedor_ok", "int_ventas_bi", ["vendedor_ok"])
        op.create_index("ix_int_ventas_bi_material", "int_ventas_bi", ["material"])
        op.create_index("ix_int_ventas_bi_is_current",
                        "int_ventas_bi", ["is_current"],
                        mssql_where=sa.text("is_current = 1"))
        op.create_index("ix_int_ventas_bi_cd_status",
                        "int_ventas_bi", ["cd_status"],
                        mssql_where=sa.text("cd_status = 'PENDING'"))
        op.create_index("ix_int_ventas_bi_execution",
                        "int_ventas_bi", ["source_execution_id"])

    # ════════════════════════════════════════════════════════════════════
    # INT DESPACHOS BI
    # ════════════════════════════════════════════════════════════════════

    if not _exists(insp, "int_query"):
        op.create_table(
            "int_query",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("centro_proveedor", sa.String(20)),
            sa.Column("sucursal", sa.String(50)),
            sa.Column("material", sa.BigInteger()),
            sa.Column("nombre_material", sa.String(200)),
            sa.Column("dia_natural", sa.String(20)),
            sa.Column("documento_venta", sa.BigInteger()),
            sa.Column("destinatario_mcia", sa.BigInteger()),
            sa.Column("nombre_centro_destinatario", sa.String(200)),
            sa.Column("poblacion", sa.String(100)),
            sa.Column("incoterms", sa.String(10)),
            sa.Column("clase_doc_ventas", sa.String(10)),
            sa.Column("tipo_venta", sa.String(50)),
            sa.Column("centro_receptor", sa.String(20)),
            sa.Column("nombre_centro_receptor", sa.String(200)),
            sa.Column("ship_to_zkatr7", sa.String(50)),
            sa.Column("ship_to_region", sa.String(50)),
            sa.Column("clase_expedicion", sa.String(50)),
            sa.Column("vc_embalaje", sa.String(20)),
            sa.Column("transportista", sa.BigInteger()),
            sa.Column("nombre_transportista", sa.String(200)),
            sa.Column("nombre", sa.String(200)),
            sa.Column("telefono_1", sa.String(50)),
            sa.Column("forwagent_accnt_g", sa.String(100)),
            sa.Column("placa", sa.String(50)),
            sa.Column("tp_vehiculo", sa.String(100)),
            sa.Column("ruta", sa.String(20)),
            sa.Column("nombre_ruta", sa.String(200)),
            sa.Column("punto_entrega", sa.String(100)),
            sa.Column("numero_transporte", sa.BigInteger()),
            sa.Column("distancia", sa.Numeric(10, 2)),
            sa.Column("cantidad", sa.Numeric(18, 4)),
            sa.Column("fecha", sa.DateTime()),
            sa.Column("despacho_t", sa.Numeric(18, 4)),
            sa.Column("departamento", sa.String(50)),
            sa.Column("traslados_t", sa.Numeric(18, 4)),
            sa.Column("dia", sa.Integer()),
            sa.Column("mes", sa.Integer()),
            sa.Column("anio", sa.Integer()),
            sa.Column("grupo_producto", sa.String(100)),
            sa.Column("tipo_traslado", sa.String(50)),
            sa.Column("producto", sa.String(200)),
            sa.Column("centro_distribucion", sa.String(100)),
            sa.Column("provincia", sa.String(100)),
            sa.Column("semana_anio", sa.Integer()),
            sa.Column("traslados", sa.Numeric(18, 4)),
            sa.Column("zona_descarga", sa.String(50)),
            sa.Column("cd", sa.String(20)),
            sa.Column("localidad", sa.String(100)),
            sa.Column("distancia_km", sa.Integer()),
            sa.Column("tipo_venta_2", sa.String(50)),
            sa.Column("vendedor", sa.String(100)),
            sa.Column("desarrollador", sa.String(100)),
            *_ts(),
        )
        op.create_index("ix_int_query_destinatario_mcia", "int_query", ["destinatario_mcia"])
        op.create_index("ix_int_query_documento_venta", "int_query", ["documento_venta"])
        op.create_index("ix_int_query_centro_receptor", "int_query", ["centro_receptor"])
        op.create_index("ix_int_query_anio_mes", "int_query", ["anio", "mes"])

    if not _exists(insp, "int_despacho_bi"):
        op.create_table(
            "int_despacho_bi",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("centro_proveedor", sa.String(20)),
            sa.Column("sucursal", sa.String(50)),
            sa.Column("material", sa.BigInteger()),
            sa.Column("nombre_material", sa.String(200)),
            sa.Column("dia_natural", sa.String(20)),
            sa.Column("documento_venta", sa.BigInteger()),
            sa.Column("destinatario_mcia", sa.BigInteger()),
            sa.Column("nombre_centro_destinatario", sa.String(200)),
            sa.Column("poblacion", sa.String(100)),
            sa.Column("incoterms", sa.String(10)),
            sa.Column("clase_doc_ventas", sa.String(10)),
            sa.Column("tipo_venta", sa.String(50)),
            sa.Column("centro_receptor", sa.String(20)),
            sa.Column("nombre_centro_receptor", sa.String(200)),
            sa.Column("clase_expedicion", sa.String(50)),
            sa.Column("vc_embalaje", sa.String(20)),
            sa.Column("transportista", sa.BigInteger()),
            sa.Column("nombre_transportista", sa.String(200)),
            sa.Column("ruta", sa.String(20)),
            sa.Column("nombre_ruta", sa.String(200)),
            sa.Column("distancia", sa.Numeric(10, 2)),
            sa.Column("cantidad", sa.Numeric(18, 4)),
            sa.Column("fecha", sa.DateTime()),
            sa.Column("despacho_t", sa.Numeric(18, 4)),
            sa.Column("departamento", sa.String(50)),
            sa.Column("traslados_t", sa.Numeric(18, 4)),
            sa.Column("dia", sa.Integer()),
            sa.Column("mes", sa.Integer()),
            sa.Column("anio", sa.Integer()),
            sa.Column("grupo_producto", sa.String(100)),
            sa.Column("tipo_traslado", sa.String(50)),
            sa.Column("producto", sa.String(200)),
            sa.Column("centro_distribucion", sa.String(100)),
            sa.Column("provincia", sa.String(100)),
            sa.Column("semana_anio", sa.Integer()),
            sa.Column("zona_descarga", sa.String(50)),
            sa.Column("cd", sa.String(20)),
            sa.Column("localidad", sa.String(100)),
            sa.Column("tipo_venta_2", sa.String(50)),
            sa.Column("vendedor", sa.String(100)),
            sa.Column("desarrollador", sa.String(100)),
            sa.Column("codigo_cliente", sa.BigInteger()),
            sa.Column("nombre_cliente", sa.String(500)),
            sa.Column("vendedor_cartera", sa.String(100)),
            sa.Column("equipo", sa.String(100)),
            sa.Column("gerencia", sa.String(100)),
            sa.Column("canal", sa.String(100)),
            sa.Column("localidad_im", sa.String(100)),
            sa.Column("incoterms_im", sa.String(200)),
            sa.Column("semana", sa.String(20)),
            sa.Column("x", sa.Integer()),
            *_ts(),
        )
        op.create_index("ix_int_despacho_bi_documento_venta", "int_despacho_bi", ["documento_venta"])
        op.create_index("ix_int_despacho_bi_destinatario_mcia", "int_despacho_bi", ["destinatario_mcia"])
        op.create_index("ix_int_despacho_bi_codigo_cliente", "int_despacho_bi", ["codigo_cliente"])
        op.create_index("ix_int_despacho_bi_anio_mes", "int_despacho_bi", ["anio", "mes"])

    if not _exists(insp, "int_despacho_mes"):
        op.create_table(
            "int_despacho_mes",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("gerencia", sa.String(100)),
            sa.Column("equipo", sa.String(100)),
            sa.Column("departamento", sa.String(50)),
            sa.Column("localidad", sa.String(100)),
            sa.Column("centro_distribucion", sa.String(100)),
            sa.Column("producto", sa.String(200)),
            sa.Column("incoterms", sa.String(10)),
            sa.Column("fecha", sa.DateTime()),
            sa.Column("mes", sa.Integer()),
            sa.Column("dia", sa.Integer()),
            sa.Column("codigo_cliente", sa.BigInteger()),
            sa.Column("despacho_t", sa.Numeric(18, 4)),
            sa.Column("rf", sa.Numeric(18, 4)),
            sa.Column("rf_ajustado_im", sa.Numeric(18, 4)),
            sa.Column("proyeccion", sa.Numeric(18, 4)),
            sa.Column("nombre_cliente", sa.String(500)),
            sa.Column("vendedor", sa.String(100)),
            sa.Column("tipo_venta", sa.String(50)),
            sa.Column("canal", sa.String(100)),
            sa.Column("semana2", sa.String(20)),
            *_ts(),
        )
        op.create_index("ix_int_despacho_mes_codigo_cliente", "int_despacho_mes", ["codigo_cliente"])
        op.create_index("ix_int_despacho_mes_fecha", "int_despacho_mes", ["fecha"])

    # ════════════════════════════════════════════════════════════════════
    # AUDIT — bitacora de corridas del bot
    # ════════════════════════════════════════════════════════════════════

    if not _exists(insp, "pipeline_executions"):
        op.create_table(
            "pipeline_executions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("pipeline_name", sa.String(50), nullable=False),
            sa.Column("started_at", sa.DateTime(), nullable=False,
                      server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False,
                      server_default=sa.text("'RUNNING'")),
            sa.Column("source_files", sa.Text(), nullable=True),
            sa.Column("rows_processed", sa.Integer(), nullable=True),
            sa.Column("rows_inserted", sa.Integer(), nullable=True),
            sa.Column("rows_updated", sa.Integer(), nullable=True),
            sa.Column("rows_skipped", sa.Integer(), nullable=True),
            sa.Column("rows_versioned", sa.Integer(), nullable=True),
            sa.Column("rows_rescued", sa.Integer(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("force_rebuild", sa.Boolean(), nullable=False,
                      server_default=sa.text("0")),
        )
        op.create_index("ix_pipeline_executions_pipeline_started",
                        "pipeline_executions", ["pipeline_name", "started_at"])


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    # Audit
    if _exists(insp, "pipeline_executions"):
        op.drop_table("pipeline_executions")

    # INT DESPACHOS
    for tbl in ("int_despacho_mes", "int_despacho_bi", "int_query"):
        if _exists(insp, tbl):
            op.drop_table(tbl)

    # INT VENTAS
    for tbl in ("int_ventas_bi", "int_gd20", "int_cartera"):
        if _exists(insp, tbl):
            op.drop_table(tbl)

    # REF
    for tbl in ("int_ref_semana", "int_ref_material", "int_ref_localidad",
                "int_ref_equipo", "int_ref_centro", "int_ref_almacen"):
        if _exists(insp, tbl):
            op.drop_table(tbl)

    # STG
    for tbl in ("stg_query", "stg_gd20", "stg_cartera"):
        if _exists(insp, tbl):
            op.drop_table(tbl)
