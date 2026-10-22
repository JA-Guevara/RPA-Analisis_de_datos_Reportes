-- ====================================================================
-- Slice: GD20
-- Transformación: stg_gd20 -> int_gd20 (BASE PANEL: Fórmulas y Cruces)
-- ====================================================================

TRUNCATE TABLE [int_gd20];

INSERT INTO [int_gd20] (
    ejercicio, sociedad, organizacion_ventas, centro, division, oficina_ventas,
    canal_distribucion, sector, numero_cuenta, centro_beneficio, material,
    unidad_medida_base, periodo_contable, clave_pais, region_sap, poblacion_sap,
    grupo_vendedores, pagador, emisor_solicitante, customer_bill_to, destinatario,
    grupo_clientes_2, atributo_6, atributo_7, atributo_10, clase_factura,
    nombre_usuario, texto, numero_documento, cantidad, moneda_sociedad,
    fe_contabilizacion, fecha_entrada, fecha_valor, documento_comercial,
    hora_entrada, moneda_transaccion, clave_moneda_transaccion, moneda_fuerte,
    clave_moneda_fuerte, numero_doc_referencia, numero_documento_2, incoterms,
    incoterms_parte_2, clase_documento, cond_pago, dias_1, numero_transporte, e,
    tipo_embalaje, nombre_producto, volumen_toneladas, nombre_pagador,
    nombre_solicitante, vendedor_sap, vendedor, vendedor_ok, gerencia, equipo,
    canal, sub_canal, dia, mes, anio, tipo_venta, localidad, provincia,
    dpto, region_m, ingreso_bruto, dpto_pagador, localidad_pagador,
    codigo_cliente, bonificaciones, centro_distribucion, zona_entrega,
    nombre_destinatario
)
SELECT 
    CAST(g.ejercicio AS INT),
    CAST(g.sociedad AS INT),
    CAST(g.organizacion_ventas AS INT),
    g.centro,
    g.division,
    g.oficina_ventas,
    CAST(g.canal_distribucion AS INT),
    CAST(g.sector AS INT),
    g.numero_cuenta,
    g.centro_beneficio,
    g.material,
    g.unidad_medida_base,
    CAST(g.periodo_contable AS INT),
    g.clave_pais_region AS clave_pais,
    g.region AS region_sap,
    g.poblacion AS poblacion_sap,
    g.grupo_vendedores,

    -- Pagador, solicitante y destinatario con fallback de macro DPTO_0
    g.cliente AS pagador,
    g.emisor_orden AS emisor_solicitante,
    g.customer_bill_to,
    CASE 
        WHEN COALESCE(c_dest.region_nombre, '0') = '0' THEN g.cliente
        ELSE g.customer_rebate 
    END AS destinatario,

    CAST(g.grupo_clientes_2 AS INT),
    g.atributo_6,
    g.atributo_7,
    g.atributo_10,
    g.clase_factura,
    g.nombre_usuario,
    g.texto,
    g.numero_documento,
    g.cantidad,
    g.moneda_sociedad,
    g.fe_contabilizacion,
    g.fecha_entrada,
    g.fecha_valor,
    g.documento_comercial,
    g.hora_entrada,
    g.moneda_transaccion,
    g.clave_moneda_transaccion,
    g.moneda_fuerte,
    g.clave_moneda_fuerte,
    g.numero_doc_referencia,
    g.numero_documento_2,
    g.incoterms,
    g.incoterms_parte_2,
    g.clase_documento,
    g.cond_pago,
    g.dias_1,
    g.numero_transporte,
    g.e,

    -- AX: TIPO DE EMBALAJE
    CASE 
        WHEN g.unidad_medida_base = 'M3' THEN 'Granel M3'
        WHEN g.unidad_medida_base = 'T' THEN 'Granel t'
        WHEN g.unidad_medida_base = 'S50' THEN 'Embolsado'
        WHEN g.unidad_medida_base = 'PC' THEN 'Bolsas Vacias'
        ELSE '0'
    END AS tipo_embalaje,

    -- AY: NOMBRE DE PRODUCTO
    COALESCE(m.descripcion, '0') AS nombre_producto,

    -- AZ: VOLUMEN TONELADAS
    CASE 
        WHEN g.unidad_medida_base = 'M3' THEN (g.cantidad * -1) * 1.42
        WHEN g.unidad_medida_base = 'T' THEN g.cantidad * -1
        WHEN g.unidad_medida_base = 'S50' THEN (g.cantidad * -1) / 20.0
        ELSE 0
    END AS volumen_toneladas,

    -- BA, BB: Nombres
    COALESCE(c_pag.nombre_cliente, '0') AS nombre_pagador,
    COALESCE(c_sol.nombre_cliente, '0') AS nombre_solicitante,

    -- BC, BD, BE: Vendedor
    COALESCE(c_dest.vendedor, '0') AS vendedor_sap,
    COALESCE(eq_v.vendedor, '0') AS vendedor,
    COALESCE(eq_v.vendedor_ok, '0') AS vendedor_ok,

    -- BF, BG: Gerencia y Equipo
    COALESCE(eq_e.gerencia, '0') AS gerencia,
    CASE 
        WHEN m.descripcion LIKE '%CEMENTO%' THEN COALESCE(eq_v.equipo, '0')
        ELSE COALESCE(eq_g.equipo, 'No encontrado')
    END AS equipo,

    -- BH, BI: Canal y Sub Canal
    COALESCE(alm.canal, 'OTROS') AS canal,
    COALESCE(alm.segmento, 'OTROS') AS sub_canal,

    -- Fechas
    DAY(g.fe_contabilizacion) AS dia,
    MONTH(g.fe_contabilizacion) AS mes,
    YEAR(g.fe_contabilizacion) AS anio,

    -- BM: Tipo de Venta
    COALESCE(cen.tipo, 'VENTA DIRECTA') AS tipo_venta,

    -- BN, BO, BP: Localidad, Provincia, Dpto
    COALESCE(c_dest.poblacion, '0') AS localidad,
    COALESCE(c_dest.attribute_6, g.poblacion, '0') AS provincia,
    COALESCE(c_dest.region_nombre, '0') AS dpto,

    -- BQ: Region M
    CASE 
        WHEN c_dest.region_nombre = 'SANTA CRUZ' THEN COALESCE(loc.localidad_im, '0')
        ELSE COALESCE(c_dest.region_nombre, '0')
    END AS region_m,

    -- BR: INGRESO BRUTO (con macro EliminarMonedaSociedad)
    CASE 
        WHEN g.numero_cuenta = 33111020 THEN 0
        WHEN (c_dest.region_nombre = 'Pando' AND g.incoterms = 'CIF') OR (c_dest.region_nombre = 'GENERIC' AND g.incoterms = 'FCA') 
            THEN g.moneda_sociedad * -1
        ELSE (g.moneda_sociedad / 0.87) * -1
    END AS ingreso_bruto,

    -- BS, BT, BU: Dpto pagador, localidad pagador, codigo cliente
    COALESCE(c_pag.region_nombre, '0') AS dpto_pagador,
    COALESCE(c_pag.poblacion, '0') AS localidad_pagador,
    COALESCE(cen.codigo_sap_cliente, g.cliente) AS codigo_cliente,

    -- BV: BONIFICACIONES (Macro CambiarSignoVolumen)
    CASE 
        WHEN g.numero_cuenta = 33111020 THEN 
            ABS(CASE 
                WHEN g.unidad_medida_base = 'M3' THEN (g.cantidad * -1) * 1.42
                WHEN g.unidad_medida_base = 'T' THEN g.cantidad * -1
                WHEN g.unidad_medida_base = 'S50' THEN (g.cantidad * -1) / 20.0
                ELSE 0
            END)
        ELSE 0
    END AS bonificaciones,

    -- BW, BX: Centro distribucion y Zona de entrega
    'OTROS' AS centro_distribucion,
    'OTROS' AS zona_entrega,

    -- BY: Nombre destinatario
    COALESCE(c_dest.nombre_cliente, '0') AS nombre_destinatario

FROM [stg_gd20] g
LEFT JOIN (
    SELECT codigo, MIN(descripcion) AS descripcion 
    FROM [int_ref_material] 
    WHERE codigo IS NOT NULL 
    GROUP BY codigo
) m ON m.codigo = g.material
LEFT JOIN [int_cartera] c_pag ON c_pag.cliente = g.cliente
LEFT JOIN [int_cartera] c_sol ON c_sol.cliente = g.emisor_orden
LEFT JOIN [int_cartera] c_dest ON c_dest.cliente = g.customer_rebate
LEFT JOIN (
    SELECT vendedor_sap, MIN(vendedor) AS vendedor, MIN(vendedor_ok) AS vendedor_ok, MIN(equipo) AS equipo 
    FROM [int_ref_equipo] 
    WHERE vendedor_sap IS NOT NULL AND vendedor_sap != '' 
    GROUP BY vendedor_sap
) eq_v ON eq_v.vendedor_sap = c_dest.vendedor
LEFT JOIN (
    SELECT grupo_vendedores, MIN(equipo) AS equipo 
    FROM [int_ref_equipo] 
    WHERE grupo_vendedores IS NOT NULL AND grupo_vendedores != '' 
    GROUP BY grupo_vendedores
) eq_g ON eq_g.grupo_vendedores = g.grupo_vendedores
LEFT JOIN (
    SELECT equipo, MIN(gerencia) AS gerencia 
    FROM [int_ref_equipo] 
    WHERE equipo IS NOT NULL AND equipo != '' 
    GROUP BY equipo
) eq_e ON eq_e.equipo = (
    CASE 
        WHEN m.descripcion LIKE '%CEMENTO%' THEN eq_v.equipo 
        ELSE eq_g.equipo 
    END
)
LEFT JOIN (
    SELECT descripcion_sap, MIN(canal) AS canal, MIN(segmento) AS segmento 
    FROM [int_ref_almacen] 
    WHERE descripcion_sap IS NOT NULL AND descripcion_sap != '' 
    GROUP BY descripcion_sap
) alm ON alm.descripcion_sap = c_dest.attribute_10
LEFT JOIN (
    SELECT centro, MIN(tipo) AS tipo, MIN(codigo_sap_cliente) AS codigo_sap_cliente 
    FROM [int_ref_centro] 
    WHERE centro IS NOT NULL AND centro != '' 
    GROUP BY centro
) cen ON cen.centro = g.centro
LEFT JOIN (
    SELECT localidad_despacho, MIN(localidad_im) AS localidad_im 
    FROM [int_ref_localidad] 
    WHERE localidad_despacho IS NOT NULL AND localidad_despacho != '' 
    GROUP BY localidad_despacho
) loc ON loc.localidad_despacho = c_dest.poblacion
/* DATE_FILTER */;
