-- ====================================================================
-- Slice: DESPACHO MES
-- Transformación: UNION ALL (Despacho Real + Proyección Comercial)
-- ====================================================================

TRUNCATE TABLE [int_despacho_mes];

WITH union_base AS (
    -- 1. DESPACHO REAL (de int_query)
    SELECT 
        COALESCE(eq_e.gerencia, 'OTROS') AS gerencia,
        CASE 
            WHEN q.material LIKE '%CEMENTO%' THEN COALESCE(eq_v.equipo, 'No encontrado')
            ELSE COALESCE(eq_g.equipo, 'No encontrado')
        END AS equipo,
        q.departamento,
        COALESCE(loc.localidad_im, q.localidad) AS localidad,
        q.centro_distribucion,
        q.material AS producto,
        q.incoterm AS incoterms,
        q.dia AS dia,
        COALESCE(cen.codigo_sap_cliente, q.cod_destinatario) AS codigo_cliente,
        COALESCE(q.despacho_t, 0) AS despacho_t,
        0 AS rf,
        0 AS rf_ajustado_im
    FROM [int_query] q
    LEFT JOIN (
        SELECT centro, MIN(codigo_sap_cliente) AS codigo_sap_cliente
        FROM [int_ref_centro]
        WHERE centro IS NOT NULL AND centro != ''
        GROUP BY centro
    ) cen ON cen.centro = CAST(q.cod_destinatario AS VARCHAR(20))
    LEFT JOIN [int_cartera] c ON c.cliente = COALESCE(cen.codigo_sap_cliente, q.cod_destinatario)
    LEFT JOIN (
        SELECT vendedor_sap, MIN(vendedor) AS vendedor, MIN(vendedor_ok) AS vendedor_ok, MIN(equipo) AS equipo
        FROM [int_ref_equipo]
        WHERE vendedor_sap IS NOT NULL AND vendedor_sap != ''
        GROUP BY vendedor_sap
    ) eq_v ON eq_v.vendedor_sap = c.vendedor
    LEFT JOIN (
        SELECT grupo_vendedores, MIN(equipo) AS equipo
        FROM [int_ref_equipo]
        WHERE grupo_vendedores IS NOT NULL AND grupo_vendedores != ''
        GROUP BY grupo_vendedores
    ) eq_g ON eq_g.grupo_vendedores = c.grupo_vendedores
    LEFT JOIN (
        SELECT equipo, MIN(gerencia) AS gerencia
        FROM [int_ref_equipo]
        WHERE equipo IS NOT NULL AND equipo != ''
        GROUP BY equipo
    ) eq_e ON eq_e.equipo = (
        CASE WHEN q.material LIKE '%CEMENTO%' THEN eq_v.equipo ELSE eq_g.equipo END
    )
    LEFT JOIN (
        SELECT localidad_despacho, MIN(localidad_im) AS localidad_im
        FROM [int_ref_localidad]
        WHERE localidad_despacho IS NOT NULL AND localidad_despacho != ''
        GROUP BY localidad_despacho
    ) loc ON loc.localidad_despacho = q.localidad

    UNION ALL

    -- 2. PROYECCIÓN COMERCIAL (de stg_proyeccion)
    SELECT 
        p.gerencia,
        p.equipo,
        p.departamento,
        p.localidad_im AS localidad,
        p.centro_distribucion,
        p.material AS producto,
        p.incoterms,
        p.dia,
        p.codigo_cliente,
        0 AS despacho_t,
        COALESCE(p.rf, 0) AS rf,
        COALESCE(p.rf_ajustado_im, 0) AS rf_ajustado_im
    FROM [stg_proyeccion] p
)
INSERT INTO [int_despacho_mes] (
    gerencia, equipo, departamento, localidad, centro_distribucion,
    producto, incoterms, dia, codigo_cliente,
    despacho_t, rf, rf_ajustado_im, proyeccion,
    nombre_cliente, vendedor, tipo_venta, canal, semana2
)
SELECT 
    u.gerencia,
    u.equipo,
    u.departamento,
    u.localidad,
    u.centro_distribucion,
    u.producto,
    u.incoterms,
    u.dia,
    u.codigo_cliente,
    SUM(u.despacho_t) AS despacho_t,
    SUM(u.rf) AS rf,
    SUM(u.rf_ajustado_im) AS rf_ajustado_im,
    
    -- PROYECCIÓN: Real hasta ayer + RF ajustado desde hoy
    SUM(CASE WHEN u.dia < /* DIA_CORTE */ THEN u.despacho_t ELSE u.rf_ajustado_im END) AS proyeccion,

    COALESCE(c.nombre_cliente, 'Prospecto') AS nombre_cliente,
    COALESCE(c.vendedor, '0') AS vendedor,
    COALESCE(c.canal_distribucion_desc, 'VENTA DIRECTA') AS tipo_venta,
    COALESCE(alm.canal, 'OTROS') AS canal,
    'SEMANA ' + CAST(((u.dia - 1) / 7 + 1) AS VARCHAR(10)) AS semana2

FROM union_base u
LEFT JOIN [int_cartera] c ON c.cliente = u.codigo_cliente
LEFT JOIN [int_ref_almacen] alm ON alm.descripcion_sap = c.attribute_10
GROUP BY 
    u.gerencia, u.equipo, u.departamento, u.localidad, u.centro_distribucion,
    u.producto, u.incoterms, u.dia, u.codigo_cliente,
    c.nombre_cliente, c.vendedor, c.canal_distribucion_desc, alm.canal;
