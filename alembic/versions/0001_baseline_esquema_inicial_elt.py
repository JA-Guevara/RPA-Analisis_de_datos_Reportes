from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '0001_baseline'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('int_cartera',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('orden_origen', sa.Integer(), nullable=False),
    sa.Column('cliente', sa.BigInteger(), nullable=True),
    sa.Column('nombre_cliente', sa.String(length=500), nullable=True),
    sa.Column('attribute_10', sa.String(length=100), nullable=True),
    sa.Column('poblacion', sa.String(length=200), nullable=True),
    sa.Column('barrio', sa.String(length=200), nullable=True),
    sa.Column('attribute_7', sa.String(length=100), nullable=True),
    sa.Column('attribute_6', sa.String(length=100), nullable=True),
    sa.Column('region', sa.String(length=20), nullable=True),
    sa.Column('region_nombre', sa.String(length=100), nullable=True),
    sa.Column('grupo_cuentas', sa.String(length=20), nullable=True),
    sa.Column('sector', sa.String(length=20), nullable=True),
    sa.Column('sector_desc', sa.String(length=200), nullable=True),
    sa.Column('canal_distribucion', sa.String(length=20), nullable=True),
    sa.Column('canal_distribucion_desc', sa.String(length=200), nullable=True),
    sa.Column('organizacion_ventas', sa.String(length=20), nullable=True),
    sa.Column('oficina_ventas', sa.String(length=20), nullable=True),
    sa.Column('grupo_vendedores', sa.String(length=20), nullable=True),
    sa.Column('equipo', sa.String(length=100), nullable=True),
    sa.Column('vendedor', sa.String(length=150), nullable=True),
    sa.Column('coordinador', sa.String(length=150), nullable=True),
    sa.Column('canal', sa.String(length=100), nullable=True),
    sa.Column('condicion_pago', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_int_cartera_cliente', 'int_cartera', ['cliente'], unique=True)
    op.create_index('ix_int_cartera_orden', 'int_cartera', ['orden_origen'], unique=False)
    op.create_index('ix_int_cartera_vendedor', 'int_cartera', ['vendedor'], unique=False)
    op.create_table('int_despacho_bi',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('fecha_salida', sa.DateTime(), nullable=True),
    sa.Column('dia', sa.Integer(), nullable=True),
    sa.Column('mes', sa.Integer(), nullable=True),
    sa.Column('anio', sa.Integer(), nullable=True),
    sa.Column('nro_pedido', sa.BigInteger(), nullable=True),
    sa.Column('incoterm', sa.String(length=20), nullable=True),
    sa.Column('centro_origen', sa.String(length=20), nullable=True),
    sa.Column('centro_destino', sa.String(length=20), nullable=True),
    sa.Column('cod_material', sa.BigInteger(), nullable=True),
    sa.Column('material', sa.String(length=200), nullable=True),
    sa.Column('cod_ruta', sa.String(length=50), nullable=True),
    sa.Column('nom_ruta', sa.String(length=200), nullable=True),
    sa.Column('cod_destinatario', sa.BigInteger(), nullable=True),
    sa.Column('nom_destinatario', sa.String(length=200), nullable=True),
    sa.Column('cod_pagador', sa.BigInteger(), nullable=True),
    sa.Column('pagador', sa.String(length=200), nullable=True),
    sa.Column('despacho_t', sa.Numeric(precision=18, scale=4), nullable=True),
    sa.Column('traslados_t', sa.Numeric(precision=18, scale=4), nullable=True),
    sa.Column('centro_distribucion', sa.String(length=100), nullable=True),
    sa.Column('localidad', sa.String(length=100), nullable=True),
    sa.Column('departamento', sa.String(length=100), nullable=True),
    sa.Column('codigo_cliente', sa.BigInteger(), nullable=True),
    sa.Column('nombre_cliente', sa.String(length=500), nullable=True),
    sa.Column('vendedor', sa.String(length=150), nullable=True),
    sa.Column('desarrollador', sa.String(length=150), nullable=True),
    sa.Column('equipo', sa.String(length=150), nullable=True),
    sa.Column('gerencia', sa.String(length=150), nullable=True),
    sa.Column('canal', sa.String(length=100), nullable=True),
    sa.Column('localidad_im', sa.String(length=150), nullable=True),
    sa.Column('semana', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_int_despacho_bi_cliente', 'int_despacho_bi', ['codigo_cliente'], unique=False)
    op.create_index('ix_int_despacho_bi_destinatario', 'int_despacho_bi', ['cod_destinatario'], unique=False)
    op.create_index('ix_int_despacho_bi_fecha', 'int_despacho_bi', ['dia'], unique=False)
    op.create_index('ix_int_despacho_bi_pedido', 'int_despacho_bi', ['nro_pedido'], unique=False)
    op.create_table('int_despacho_mes',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('gerencia', sa.String(length=150), nullable=True),
    sa.Column('equipo', sa.String(length=150), nullable=True),
    sa.Column('departamento', sa.String(length=100), nullable=True),
    sa.Column('localidad', sa.String(length=150), nullable=True),
    sa.Column('centro_distribucion', sa.String(length=150), nullable=True),
    sa.Column('producto', sa.String(length=200), nullable=True),
    sa.Column('incoterms', sa.String(length=20), nullable=True),
    sa.Column('dia', sa.Integer(), nullable=True),
    sa.Column('codigo_cliente', sa.BigInteger(), nullable=True),
    sa.Column('despacho_t', sa.Numeric(precision=18, scale=4), nullable=True),
    sa.Column('rf', sa.Numeric(precision=18, scale=4), nullable=True),
    sa.Column('rf_ajustado_im', sa.Numeric(precision=18, scale=4), nullable=True),
    sa.Column('proyeccion', sa.Numeric(precision=18, scale=4), nullable=True),
    sa.Column('nombre_cliente', sa.String(length=500), nullable=True),
    sa.Column('vendedor', sa.String(length=150), nullable=True),
    sa.Column('tipo_venta', sa.String(length=50), nullable=True),
    sa.Column('canal', sa.String(length=100), nullable=True),
    sa.Column('semana2', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_int_despacho_mes_cliente', 'int_despacho_mes', ['codigo_cliente'], unique=False)
    op.create_index('ix_int_despacho_mes_fecha', 'int_despacho_mes', ['dia'], unique=False)
    op.create_table('int_gd20',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('ejercicio', sa.Integer(), nullable=True),
    sa.Column('sociedad', sa.Integer(), nullable=True),
    sa.Column('organizacion_ventas', sa.Integer(), nullable=True),
    sa.Column('centro', sa.String(length=20), nullable=True),
    sa.Column('division', sa.String(length=20), nullable=True),
    sa.Column('oficina_ventas', sa.String(length=20), nullable=True),
    sa.Column('canal_distribucion', sa.Integer(), nullable=True),
    sa.Column('sector', sa.String(length=10), nullable=True),
    sa.Column('numero_cuenta', sa.BigInteger(), nullable=True),
    sa.Column('centro_beneficio', sa.String(length=50), nullable=True),
    sa.Column('material', sa.BigInteger(), nullable=True),
    sa.Column('unidad_medida_base', sa.String(length=10), nullable=True),
    sa.Column('periodo_contable', sa.Integer(), nullable=True),
    sa.Column('clave_pais', sa.String(length=10), nullable=True),
    sa.Column('region_sap', sa.String(length=10), nullable=True),
    sa.Column('poblacion_sap', sa.String(length=100), nullable=True),
    sa.Column('grupo_vendedores', sa.String(length=20), nullable=True),
    sa.Column('pagador', sa.BigInteger(), nullable=True),
    sa.Column('emisor_solicitante', sa.BigInteger(), nullable=True),
    sa.Column('customer_bill_to', sa.BigInteger(), nullable=True),
    sa.Column('destinatario', sa.BigInteger(), nullable=True),
    sa.Column('grupo_clientes_2', sa.String(length=10), nullable=True),
    sa.Column('atributo_6', sa.String(length=20), nullable=True),
    sa.Column('atributo_7', sa.String(length=20), nullable=True),
    sa.Column('atributo_10', sa.String(length=20), nullable=True),
    sa.Column('clase_factura', sa.String(length=20), nullable=True),
    sa.Column('nombre_usuario', sa.String(length=50), nullable=True),
    sa.Column('texto', sa.String(length=250), nullable=True),
    sa.Column('numero_documento', sa.BigInteger(), nullable=True),
    sa.Column('cantidad', sa.Numeric(precision=18, scale=4), nullable=True),
    sa.Column('moneda_sociedad', sa.Numeric(precision=18, scale=4), nullable=True),
    sa.Column('fe_contabilizacion', sa.DateTime(), nullable=True),
    sa.Column('fecha_entrada', sa.DateTime(), nullable=True),
    sa.Column('fecha_valor', sa.DateTime(), nullable=True),
    sa.Column('documento_comercial', sa.BigInteger(), nullable=True),
    sa.Column('hora_entrada', sa.String(length=20), nullable=True),
    sa.Column('moneda_transaccion', sa.Numeric(precision=18, scale=4), nullable=True),
    sa.Column('clave_moneda_transaccion', sa.String(length=10), nullable=True),
    sa.Column('moneda_fuerte', sa.Numeric(precision=18, scale=4), nullable=True),
    sa.Column('clave_moneda_fuerte', sa.String(length=10), nullable=True),
    sa.Column('numero_doc_referencia', sa.BigInteger(), nullable=True),
    sa.Column('numero_documento_2', sa.BigInteger(), nullable=True),
    sa.Column('incoterms', sa.String(length=20), nullable=True),
    sa.Column('incoterms_parte_2', sa.String(length=100), nullable=True),
    sa.Column('clase_documento', sa.String(length=20), nullable=True),
    sa.Column('cond_pago', sa.String(length=20), nullable=True),
    sa.Column('dias_1', sa.Integer(), nullable=True),
    sa.Column('numero_transporte', sa.BigInteger(), nullable=True),
    sa.Column('e', sa.String(length=10), nullable=True),
    sa.Column('tipo_embalaje', sa.String(length=50), nullable=True),
    sa.Column('nombre_producto', sa.String(length=250), nullable=True),
    sa.Column('volumen_toneladas', sa.Numeric(precision=18, scale=4), nullable=True),
    sa.Column('nombre_pagador', sa.String(length=500), nullable=True),
    sa.Column('nombre_solicitante', sa.String(length=500), nullable=True),
    sa.Column('vendedor_sap', sa.String(length=150), nullable=True),
    sa.Column('vendedor', sa.String(length=150), nullable=True),
    sa.Column('vendedor_ok', sa.String(length=150), nullable=True),
    sa.Column('gerencia', sa.String(length=150), nullable=True),
    sa.Column('equipo', sa.String(length=150), nullable=True),
    sa.Column('canal', sa.String(length=100), nullable=True),
    sa.Column('sub_canal', sa.String(length=100), nullable=True),
    sa.Column('dia', sa.Integer(), nullable=True),
    sa.Column('mes', sa.Integer(), nullable=True),
    sa.Column('anio', sa.Integer(), nullable=True),
    sa.Column('tipo_venta', sa.String(length=50), nullable=True),
    sa.Column('localidad', sa.String(length=200), nullable=True),
    sa.Column('provincia', sa.String(length=200), nullable=True),
    sa.Column('dpto', sa.String(length=100), nullable=True),
    sa.Column('region_m', sa.String(length=100), nullable=True),
    sa.Column('ingreso_bruto', sa.Numeric(precision=18, scale=4), nullable=True),
    sa.Column('dpto_pagador', sa.String(length=100), nullable=True),
    sa.Column('localidad_pagador', sa.String(length=200), nullable=True),
    sa.Column('codigo_cliente', sa.BigInteger(), nullable=True),
    sa.Column('bonificaciones', sa.Numeric(precision=18, scale=4), nullable=True),
    sa.Column('centro_distribucion', sa.String(length=100), nullable=True),
    sa.Column('zona_entrega', sa.String(length=100), nullable=True),
    sa.Column('nombre_destinatario', sa.String(length=500), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_int_gd20_destinatario', 'int_gd20', ['destinatario'], unique=False)
    op.create_index('ix_int_gd20_documento_comercial', 'int_gd20', ['documento_comercial'], unique=False)
    op.create_index('ix_int_gd20_fe_contabilizacion', 'int_gd20', ['fe_contabilizacion'], unique=False)
    op.create_index('ix_int_gd20_pagador', 'int_gd20', ['pagador'], unique=False)
    op.create_table('int_query',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('fecha_salida', sa.DateTime(), nullable=True),
    sa.Column('dia', sa.Integer(), nullable=True),
    sa.Column('mes', sa.Integer(), nullable=True),
    sa.Column('anio', sa.Integer(), nullable=True),
    sa.Column('nro_pedido', sa.BigInteger(), nullable=True),
    sa.Column('incoterm', sa.String(length=20), nullable=True),
    sa.Column('centro_origen', sa.String(length=20), nullable=True),
    sa.Column('centro_destino', sa.String(length=20), nullable=True),
    sa.Column('cod_material', sa.BigInteger(), nullable=True),
    sa.Column('material', sa.String(length=200), nullable=True),
    sa.Column('cod_ruta', sa.String(length=50), nullable=True),
    sa.Column('nom_ruta', sa.String(length=200), nullable=True),
    sa.Column('cod_destinatario', sa.BigInteger(), nullable=True),
    sa.Column('nom_destinatario', sa.String(length=200), nullable=True),
    sa.Column('cod_pagador', sa.BigInteger(), nullable=True),
    sa.Column('pagador', sa.String(length=200), nullable=True),
    sa.Column('despacho_t', sa.Numeric(precision=18, scale=4), nullable=True),
    sa.Column('traslados_t', sa.Numeric(precision=18, scale=4), nullable=True),
    sa.Column('centro_distribucion', sa.String(length=100), nullable=True),
    sa.Column('localidad', sa.String(length=100), nullable=True),
    sa.Column('departamento', sa.String(length=100), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_int_query_destinatario', 'int_query', ['cod_destinatario'], unique=False)
    op.create_index('ix_int_query_fecha', 'int_query', ['dia'], unique=False)
    op.create_index('ix_int_query_pedido', 'int_query', ['nro_pedido'], unique=False)
    op.create_table('int_ref_almacen',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('descripcion_sap', sa.String(length=100), nullable=True),
    sa.Column('canal', sa.String(length=50), nullable=True),
    sa.Column('segmento', sa.String(length=100), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_int_ref_almacen_descripcion_sap'), 'int_ref_almacen', ['descripcion_sap'], unique=False)
    op.create_table('int_ref_centro',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('centro', sa.String(length=20), nullable=True),
    sa.Column('nombre', sa.String(length=150), nullable=True),
    sa.Column('codigo_sap_cliente', sa.BigInteger(), nullable=True),
    sa.Column('tipo', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_int_ref_centro_centro'), 'int_ref_centro', ['centro'], unique=False)
    op.create_index(op.f('ix_int_ref_centro_codigo_sap_cliente'), 'int_ref_centro', ['codigo_sap_cliente'], unique=False)
    op.create_table('int_ref_equipo',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('vendedor_sap', sa.String(length=150), nullable=True),
    sa.Column('vendedor', sa.String(length=150), nullable=True),
    sa.Column('vendedor_ok', sa.String(length=150), nullable=True),
    sa.Column('grupo_vendedores', sa.String(length=20), nullable=True),
    sa.Column('equipo', sa.String(length=150), nullable=True),
    sa.Column('gerencia', sa.String(length=150), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_int_ref_equipo_equipo'), 'int_ref_equipo', ['equipo'], unique=False)
    op.create_index(op.f('ix_int_ref_equipo_grupo_vendedores'), 'int_ref_equipo', ['grupo_vendedores'], unique=False)
    op.create_index(op.f('ix_int_ref_equipo_vendedor_sap'), 'int_ref_equipo', ['vendedor_sap'], unique=False)
    op.create_table('int_ref_localidad',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('localidad_despacho', sa.String(length=150), nullable=True),
    sa.Column('localidad_im', sa.String(length=150), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_int_ref_localidad_localidad_despacho'), 'int_ref_localidad', ['localidad_despacho'], unique=False)
    op.create_table('int_ref_material',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('codigo', sa.BigInteger(), nullable=True),
    sa.Column('descripcion', sa.String(length=250), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_int_ref_material_codigo'), 'int_ref_material', ['codigo'], unique=False)
    op.create_table('int_ref_semana',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('dia', sa.Integer(), nullable=True),
    sa.Column('semana', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_int_ref_semana_dia'), 'int_ref_semana', ['dia'], unique=False)
    op.create_table('int_ref_ruta',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('codigo_ruta', sa.String(length=50), nullable=True),
    sa.Column('ruta', sa.String(length=200), nullable=True),
    sa.Column('departamento', sa.String(length=100), nullable=True),
    sa.Column('localidad', sa.String(length=150), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_int_ref_ruta_codigo_ruta'), 'int_ref_ruta', ['codigo_ruta'], unique=False)
    op.create_table('int_ventas_bi',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('ejercicio', sa.Integer(), nullable=True),
    sa.Column('sociedad', sa.Integer(), nullable=True),
    sa.Column('organizacion_ventas', sa.Integer(), nullable=True),
    sa.Column('centro', sa.String(length=20), nullable=True),
    sa.Column('division', sa.String(length=20), nullable=True),
    sa.Column('oficina_ventas', sa.String(length=20), nullable=True),
    sa.Column('canal_distribucion', sa.Integer(), nullable=True),
    sa.Column('sector', sa.String(length=10), nullable=True),
    sa.Column('numero_cuenta', sa.BigInteger(), nullable=True),
    sa.Column('centro_beneficio', sa.String(length=50), nullable=True),
    sa.Column('material', sa.BigInteger(), nullable=True),
    sa.Column('unidad_medida_base', sa.String(length=10), nullable=True),
    sa.Column('periodo_contable', sa.Integer(), nullable=True),
    sa.Column('clave_pais', sa.String(length=10), nullable=True),
    sa.Column('region_sap', sa.String(length=10), nullable=True),
    sa.Column('poblacion_sap', sa.String(length=100), nullable=True),
    sa.Column('grupo_vendedores', sa.String(length=20), nullable=True),
    sa.Column('pagador', sa.BigInteger(), nullable=True),
    sa.Column('emisor_solicitante', sa.BigInteger(), nullable=True),
    sa.Column('customer_bill_to', sa.BigInteger(), nullable=True),
    sa.Column('destinatario', sa.BigInteger(), nullable=True),
    sa.Column('grupo_clientes_2', sa.String(length=10), nullable=True),
    sa.Column('atributo_6', sa.String(length=20), nullable=True),
    sa.Column('atributo_7', sa.String(length=20), nullable=True),
    sa.Column('atributo_10', sa.String(length=20), nullable=True),
    sa.Column('clase_factura', sa.String(length=20), nullable=True),
    sa.Column('nombre_usuario', sa.String(length=50), nullable=True),
    sa.Column('texto', sa.String(length=250), nullable=True),
    sa.Column('numero_documento', sa.BigInteger(), nullable=True),
    sa.Column('cantidad', sa.Numeric(precision=18, scale=4), nullable=True),
    sa.Column('moneda_sociedad', sa.Numeric(precision=18, scale=4), nullable=True),
    sa.Column('fe_contabilizacion', sa.DateTime(), nullable=True),
    sa.Column('fecha_entrada', sa.DateTime(), nullable=True),
    sa.Column('fecha_valor', sa.DateTime(), nullable=True),
    sa.Column('documento_comercial', sa.BigInteger(), nullable=True),
    sa.Column('hora_entrada', sa.String(length=20), nullable=True),
    sa.Column('moneda_transaccion', sa.Numeric(precision=18, scale=4), nullable=True),
    sa.Column('clave_moneda_transaccion', sa.String(length=10), nullable=True),
    sa.Column('moneda_fuerte', sa.Numeric(precision=18, scale=4), nullable=True),
    sa.Column('clave_moneda_fuerte', sa.String(length=10), nullable=True),
    sa.Column('numero_doc_referencia', sa.BigInteger(), nullable=True),
    sa.Column('numero_documento_2', sa.BigInteger(), nullable=True),
    sa.Column('incoterms', sa.String(length=20), nullable=True),
    sa.Column('incoterms_parte_2', sa.String(length=100), nullable=True),
    sa.Column('clase_documento', sa.String(length=20), nullable=True),
    sa.Column('cond_pago', sa.String(length=20), nullable=True),
    sa.Column('dias_1', sa.Integer(), nullable=True),
    sa.Column('numero_transporte', sa.BigInteger(), nullable=True),
    sa.Column('e', sa.String(length=10), nullable=True),
    sa.Column('tipo_embalaje', sa.String(length=50), nullable=True),
    sa.Column('nombre_producto', sa.String(length=250), nullable=True),
    sa.Column('volumen_toneladas', sa.Numeric(precision=18, scale=4), nullable=True),
    sa.Column('nombre_pagador', sa.String(length=500), nullable=True),
    sa.Column('nombre_solicitante', sa.String(length=500), nullable=True),
    sa.Column('vendedor_sap', sa.String(length=150), nullable=True),
    sa.Column('vendedor', sa.String(length=150), nullable=True),
    sa.Column('vendedor_ok', sa.String(length=150), nullable=True),
    sa.Column('gerencia', sa.String(length=150), nullable=True),
    sa.Column('equipo', sa.String(length=150), nullable=True),
    sa.Column('canal', sa.String(length=100), nullable=True),
    sa.Column('sub_canal', sa.String(length=100), nullable=True),
    sa.Column('dia', sa.Integer(), nullable=True),
    sa.Column('mes', sa.Integer(), nullable=True),
    sa.Column('anio', sa.Integer(), nullable=True),
    sa.Column('tipo_venta', sa.String(length=50), nullable=True),
    sa.Column('localidad', sa.String(length=200), nullable=True),
    sa.Column('provincia', sa.String(length=200), nullable=True),
    sa.Column('dpto', sa.String(length=100), nullable=True),
    sa.Column('region_m', sa.String(length=100), nullable=True),
    sa.Column('ingreso_bruto', sa.Numeric(precision=18, scale=4), nullable=True),
    sa.Column('dpto_pagador', sa.String(length=100), nullable=True),
    sa.Column('localidad_pagador', sa.String(length=200), nullable=True),
    sa.Column('codigo_cliente', sa.BigInteger(), nullable=True),
    sa.Column('bonificaciones', sa.Numeric(precision=18, scale=4), nullable=True),
    sa.Column('centro_distribucion', sa.String(length=100), nullable=True),
    sa.Column('zona_entrega', sa.String(length=100), nullable=True),
    sa.Column('nombre_destinatario', sa.String(length=500), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('is_current', sa.Boolean(), nullable=False),
    sa.Column('valid_from', sa.DateTime(), nullable=False),
    sa.Column('valid_to', sa.DateTime(), nullable=True),
    sa.Column('source_hash', sa.String(length=64), nullable=True),
    sa.Column('derived_hash', sa.String(length=64), nullable=True),
    sa.Column('full_row_hash', sa.String(length=64), nullable=True),
    sa.Column('cd_status', sa.String(length=15), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_int_ventas_bi_anio_mes', 'int_ventas_bi', ['anio', 'mes'], unique=False)
    op.create_index('ix_int_ventas_bi_destinatario', 'int_ventas_bi', ['destinatario'], unique=False)
    op.create_index('ix_int_ventas_bi_doc_ejercicio', 'int_ventas_bi', ['documento_comercial', 'ejercicio'], unique=False)
    op.create_index('ix_int_ventas_bi_fe_contabilizacion', 'int_ventas_bi', ['fe_contabilizacion'], unique=False)
    op.create_index('ix_int_ventas_bi_material', 'int_ventas_bi', ['material'], unique=False)
    op.create_index('ix_int_ventas_bi_pagador', 'int_ventas_bi', ['pagador'], unique=False)
    op.create_index('ix_int_ventas_bi_vendedor_ok', 'int_ventas_bi', ['vendedor_ok'], unique=False)
    op.create_table('pipeline_executions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('report_name', sa.String(length=50), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('rows_processed', sa.Integer(), nullable=True),
    sa.Column('duration_seconds', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('details', sa.Text(), nullable=True),
    sa.Column('executed_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('stg_cartera',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('orden_origen', sa.Integer(), nullable=False),
    sa.Column('cliente', sa.BigInteger(), nullable=True),
    sa.Column('nombre_cliente', sa.String(length=500), nullable=True),
    sa.Column('attribute_10', sa.String(length=100), nullable=True),
    sa.Column('poblacion', sa.String(length=200), nullable=True),
    sa.Column('barrio', sa.String(length=200), nullable=True),
    sa.Column('attribute_7', sa.String(length=100), nullable=True),
    sa.Column('attribute_6', sa.String(length=100), nullable=True),
    sa.Column('region', sa.String(length=20), nullable=True),
    sa.Column('region_nombre', sa.String(length=100), nullable=True),
    sa.Column('grupo_cuentas', sa.String(length=20), nullable=True),
    sa.Column('sector', sa.String(length=20), nullable=True),
    sa.Column('sector_desc', sa.String(length=200), nullable=True),
    sa.Column('canal_distribucion', sa.String(length=20), nullable=True),
    sa.Column('canal_distribucion_desc', sa.String(length=200), nullable=True),
    sa.Column('organizacion_ventas', sa.String(length=20), nullable=True),
    sa.Column('oficina_ventas', sa.String(length=20), nullable=True),
    sa.Column('grupo_vendedores', sa.String(length=20), nullable=True),
    sa.Column('equipo', sa.String(length=100), nullable=True),
    sa.Column('vendedor', sa.String(length=150), nullable=True),
    sa.Column('coordinador', sa.String(length=150), nullable=True),
    sa.Column('canal', sa.String(length=100), nullable=True),
    sa.Column('condicion_pago', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_stg_cartera_cliente', 'stg_cartera', ['cliente'], unique=False)
    op.create_index('ix_stg_cartera_orden', 'stg_cartera', ['orden_origen'], unique=False)
    op.create_table('stg_gd20',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('ejercicio', sa.String(length=10), nullable=True),
    sa.Column('sociedad', sa.String(length=10), nullable=True),
    sa.Column('organizacion_ventas', sa.String(length=10), nullable=True),
    sa.Column('centro', sa.String(length=10), nullable=True),
    sa.Column('division', sa.String(length=10), nullable=True),
    sa.Column('oficina_ventas', sa.String(length=10), nullable=True),
    sa.Column('canal_distribucion', sa.String(length=10), nullable=True),
    sa.Column('sector', sa.String(length=10), nullable=True),
    sa.Column('numero_cuenta', sa.BigInteger(), nullable=True),
    sa.Column('centro_beneficio', sa.String(length=50), nullable=True),
    sa.Column('material', sa.BigInteger(), nullable=True),
    sa.Column('unidad_medida_base', sa.String(length=10), nullable=True),
    sa.Column('periodo_contable', sa.String(length=10), nullable=True),
    sa.Column('clave_pais_region', sa.String(length=10), nullable=True),
    sa.Column('region', sa.String(length=10), nullable=True),
    sa.Column('poblacion', sa.String(length=100), nullable=True),
    sa.Column('grupo_vendedores', sa.String(length=10), nullable=True),
    sa.Column('cliente', sa.BigInteger(), nullable=True),
    sa.Column('emisor_orden', sa.BigInteger(), nullable=True),
    sa.Column('customer_bill_to', sa.BigInteger(), nullable=True),
    sa.Column('customer_rebate', sa.BigInteger(), nullable=True),
    sa.Column('grupo_clientes_2', sa.String(length=10), nullable=True),
    sa.Column('atributo_6', sa.String(length=10), nullable=True),
    sa.Column('atributo_7', sa.String(length=10), nullable=True),
    sa.Column('atributo_10', sa.String(length=10), nullable=True),
    sa.Column('clase_factura', sa.String(length=10), nullable=True),
    sa.Column('nombre_usuario', sa.String(length=50), nullable=True),
    sa.Column('texto', sa.String(length=200), nullable=True),
    sa.Column('numero_documento', sa.BigInteger(), nullable=True),
    sa.Column('cantidad', sa.Numeric(precision=18, scale=4), nullable=True),
    sa.Column('moneda_sociedad', sa.Numeric(precision=18, scale=4), nullable=True),
    sa.Column('fe_contabilizacion', sa.DateTime(), nullable=True),
    sa.Column('fecha_entrada', sa.DateTime(), nullable=True),
    sa.Column('fecha_valor', sa.DateTime(), nullable=True),
    sa.Column('documento_comercial', sa.BigInteger(), nullable=True),
    sa.Column('hora_entrada', sa.String(length=20), nullable=True),
    sa.Column('moneda_transaccion', sa.Numeric(precision=18, scale=4), nullable=True),
    sa.Column('clave_moneda_transaccion', sa.String(length=10), nullable=True),
    sa.Column('moneda_fuerte', sa.Numeric(precision=18, scale=4), nullable=True),
    sa.Column('clave_moneda_fuerte', sa.String(length=10), nullable=True),
    sa.Column('numero_doc_referencia', sa.BigInteger(), nullable=True),
    sa.Column('numero_documento_2', sa.BigInteger(), nullable=True),
    sa.Column('incoterms', sa.String(length=10), nullable=True),
    sa.Column('incoterms_parte_2', sa.String(length=50), nullable=True),
    sa.Column('clase_documento', sa.String(length=10), nullable=True),
    sa.Column('cond_pago', sa.String(length=10), nullable=True),
    sa.Column('dias_1', sa.Integer(), nullable=True),
    sa.Column('numero_transporte', sa.BigInteger(), nullable=True),
    sa.Column('e', sa.String(length=10), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_stg_gd20_cliente', 'stg_gd20', ['cliente'], unique=False)
    op.create_index('ix_stg_gd20_documento_comercial', 'stg_gd20', ['documento_comercial'], unique=False)
    op.create_table('stg_proyeccion',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('gerencia', sa.String(length=100), nullable=True),
    sa.Column('equipo', sa.String(length=100), nullable=True),
    sa.Column('departamento', sa.String(length=100), nullable=True),
    sa.Column('incoterms', sa.String(length=20), nullable=True),
    sa.Column('centro_distribucion', sa.String(length=100), nullable=True),
    sa.Column('material', sa.String(length=200), nullable=True),
    sa.Column('localidad_im', sa.String(length=100), nullable=True),
    sa.Column('codigo_cliente', sa.BigInteger(), nullable=True),
    sa.Column('dia', sa.Integer(), nullable=True),
    sa.Column('rf', sa.Numeric(precision=18, scale=4), nullable=True),
    sa.Column('rf_ajustado_im', sa.Numeric(precision=18, scale=4), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_stg_proy_cliente', 'stg_proyeccion', ['codigo_cliente'], unique=False)
    op.create_index('ix_stg_proy_dia', 'stg_proyeccion', ['dia'], unique=False)
    op.create_table('stg_query',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('fecha_salida', sa.DateTime(), nullable=True),
    sa.Column('fecha_creacion_entrega', sa.DateTime(), nullable=True),
    sa.Column('nro_pedido', sa.BigInteger(), nullable=True),
    sa.Column('incoterm', sa.String(length=20), nullable=True),
    sa.Column('centro_origen', sa.String(length=20), nullable=True),
    sa.Column('centro_destino', sa.String(length=20), nullable=True),
    sa.Column('cod_material', sa.BigInteger(), nullable=True),
    sa.Column('material', sa.String(length=200), nullable=True),
    sa.Column('cod_ruta', sa.String(length=50), nullable=True),
    sa.Column('nom_ruta', sa.String(length=200), nullable=True),
    sa.Column('cod_destinatario', sa.BigInteger(), nullable=True),
    sa.Column('nom_destinatario', sa.String(length=200), nullable=True),
    sa.Column('cod_pagador', sa.BigInteger(), nullable=True),
    sa.Column('pagador', sa.String(length=200), nullable=True),
    sa.Column('cantidad_ton', sa.Numeric(precision=18, scale=4), nullable=True),
    sa.Column('precio_pedido', sa.Numeric(precision=18, scale=4), nullable=True),
    sa.Column('unidad_entrega', sa.String(length=20), nullable=True),
    sa.Column('nom_centro_origen', sa.String(length=200), nullable=True),
    sa.Column('nom_centro_destino', sa.String(length=200), nullable=True),
    sa.Column('fecha_facturacion', sa.DateTime(), nullable=True),
    sa.Column('nro_factura', sa.BigInteger(), nullable=True),
    sa.Column('tipo_pos_pedido', sa.String(length=50), nullable=True),
    sa.Column('documento_referencia', sa.String(length=50), nullable=True),
    sa.Column('codigo_ferretero', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_stg_query_destinatario', 'stg_query', ['cod_destinatario'], unique=False)
    op.create_index('ix_stg_query_pedido', 'stg_query', ['nro_pedido'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_stg_query_pedido', table_name='stg_query')
    op.drop_index('ix_stg_query_destinatario', table_name='stg_query')
    op.drop_table('stg_query')
    op.drop_index('ix_stg_proy_dia', table_name='stg_proyeccion')
    op.drop_index('ix_stg_proy_cliente', table_name='stg_proyeccion')
    op.drop_table('stg_proyeccion')
    op.drop_index('ix_stg_gd20_documento_comercial', table_name='stg_gd20')
    op.drop_index('ix_stg_gd20_cliente', table_name='stg_gd20')
    op.drop_table('stg_gd20')
    op.drop_index('ix_stg_cartera_orden', table_name='stg_cartera')
    op.drop_index('ix_stg_cartera_cliente', table_name='stg_cartera')
    op.drop_table('stg_cartera')
    op.drop_table('pipeline_executions')
    op.drop_index('ix_int_ventas_bi_vendedor_ok', table_name='int_ventas_bi')
    op.drop_index('ix_int_ventas_bi_pagador', table_name='int_ventas_bi')
    op.drop_index('ix_int_ventas_bi_material', table_name='int_ventas_bi')
    op.drop_index('ix_int_ventas_bi_fe_contabilizacion', table_name='int_ventas_bi')
    op.drop_index('ix_int_ventas_bi_doc_ejercicio', table_name='int_ventas_bi')
    op.drop_index('ix_int_ventas_bi_destinatario', table_name='int_ventas_bi')
    op.drop_index('ix_int_ventas_bi_anio_mes', table_name='int_ventas_bi')
    op.drop_table('int_ventas_bi')
    op.drop_index(op.f('ix_int_ref_semana_dia'), table_name='int_ref_semana')
    op.drop_table('int_ref_semana')
    op.drop_index(op.f('ix_int_ref_ruta_codigo_ruta'), table_name='int_ref_ruta')
    op.drop_table('int_ref_ruta')
    op.drop_index(op.f('ix_int_ref_material_codigo'), table_name='int_ref_material')
    op.drop_table('int_ref_material')
    op.drop_index(op.f('ix_int_ref_localidad_localidad_despacho'), table_name='int_ref_localidad')
    op.drop_table('int_ref_localidad')
    op.drop_index(op.f('ix_int_ref_equipo_vendedor_sap'), table_name='int_ref_equipo')
    op.drop_index(op.f('ix_int_ref_equipo_grupo_vendedores'), table_name='int_ref_equipo')
    op.drop_index(op.f('ix_int_ref_equipo_equipo'), table_name='int_ref_equipo')
    op.drop_table('int_ref_equipo')
    op.drop_index(op.f('ix_int_ref_centro_codigo_sap_cliente'), table_name='int_ref_centro')
    op.drop_index(op.f('ix_int_ref_centro_centro'), table_name='int_ref_centro')
    op.drop_table('int_ref_centro')
    op.drop_index(op.f('ix_int_ref_almacen_descripcion_sap'), table_name='int_ref_almacen')
    op.drop_table('int_ref_almacen')
    op.drop_index('ix_int_query_pedido', table_name='int_query')
    op.drop_index('ix_int_query_fecha', table_name='int_query')
    op.drop_index('ix_int_query_destinatario', table_name='int_query')
    op.drop_table('int_query')
    op.drop_index('ix_int_gd20_pagador', table_name='int_gd20')
    op.drop_index('ix_int_gd20_fe_contabilizacion', table_name='int_gd20')
    op.drop_index('ix_int_gd20_documento_comercial', table_name='int_gd20')
    op.drop_index('ix_int_gd20_destinatario', table_name='int_gd20')
    op.drop_table('int_gd20')
    op.drop_index('ix_int_despacho_mes_fecha', table_name='int_despacho_mes')
    op.drop_index('ix_int_despacho_mes_cliente', table_name='int_despacho_mes')
    op.drop_table('int_despacho_mes')
    op.drop_index('ix_int_despacho_bi_pedido', table_name='int_despacho_bi')
    op.drop_index('ix_int_despacho_bi_fecha', table_name='int_despacho_bi')
    op.drop_index('ix_int_despacho_bi_destinatario', table_name='int_despacho_bi')
    op.drop_index('ix_int_despacho_bi_cliente', table_name='int_despacho_bi')
    op.drop_table('int_despacho_bi')
    op.drop_index('ix_int_cartera_vendedor', table_name='int_cartera')
    op.drop_index('ix_int_cartera_orden', table_name='int_cartera')
    op.drop_index('ix_int_cartera_cliente', table_name='int_cartera')
    op.drop_table('int_cartera')
