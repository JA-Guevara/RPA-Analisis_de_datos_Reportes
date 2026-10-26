-- ====================================================================
-- Slice: DESPACHO MES
-- Transformación: UNION ALL (Despacho Real + Proyección Comercial)
-- ====================================================================

TRUNCATE TABLE [int_despacho_mes];

WITH ref_cen_1 AS (
    SELECT centro, codigo_sap_cliente, tipo,
           ROW_NUMBER() OVER (PARTITION BY centro ORDER BY id) AS rn
    FROM [int_ref_centro]
    WHERE centro IS NOT NULL AND centro <> ''
),
ref_cen_tipo AS (
    SELECT codigo_sap_cliente, tipo,
           ROW_NUMBER() OVER (PARTITION BY codigo_sap_cliente ORDER BY id) AS rn
    FROM [int_ref_centro]
    WHERE codigo_sap_cliente IS NOT NULL AND codigo_sap_cliente <> 0
),
ref_eq_v AS (
    SELECT vendedor_sap, vendedor, vendedor_ok, equipo,
           ROW_NUMBER() OVER (PARTITION BY UPPER(LTRIM(RTRIM(vendedor_sap))) ORDER BY id) AS rn
    FROM [int_ref_equipo]
    WHERE vendedor_sap IS NOT NULL AND vendedor_sap <> ''
),
ref_eq_g AS (
    SELECT grupo_vendedores, equipo,
           ROW_NUMBER() OVER (PARTITION BY UPPER(LTRIM(RTRIM(grupo_vendedores))) ORDER BY id) AS rn
    FROM [int_ref_equipo]
    WHERE grupo_vendedores IS NOT NULL AND grupo_vendedores <> ''
),
ref_eq_e AS (
    SELECT equipo, gerencia,
           ROW_NUMBER() OVER (PARTITION BY UPPER(LTRIM(RTRIM(equipo))) ORDER BY id) AS rn
    FROM [int_ref_equipo]
    WHERE equipo IS NOT NULL AND equipo <> ''
),
ref_loc AS (
    SELECT localidad_despacho, localidad_im,
           ROW_NUMBER() OVER (PARTITION BY UPPER(LTRIM(RTRIM(localidad_despacho))) ORDER BY id) AS rn
    FROM [int_ref_localidad]
    WHERE localidad_despacho IS NOT NULL AND localidad_despacho <> ''
),
ref_alm_seg AS (
    SELECT descripcion_sap, segmento,
           ROW_NUMBER() OVER (PARTITION BY UPPER(LTRIM(RTRIM(descripcion_sap))) ORDER BY id) AS rn
    FROM [int_ref_almacen]
    WHERE descripcion_sap IS NOT NULL AND descripcion_sap <> ''
),
ref_alm_can AS (
    SELECT segmento, canal,
           ROW_NUMBER() OVER (PARTITION BY UPPER(LTRIM(RTRIM(segmento))) ORDER BY id) AS rn
    FROM [int_ref_almacen]
    WHERE segmento IS NOT NULL AND segmento <> ''
),
ref_sem AS (
    SELECT dia, semana,
           ROW_NUMBER() OVER (PARTITION BY dia ORDER BY id) AS rn
    FROM [int_ref_semana]
    WHERE dia IS NOT NULL
),
union_base AS (
    -- 1. DESPACHO REAL (de int_query)
    SELECT 
        COALESCE(eq_e.gerencia, 'OTROS') AS gerencia,
        CASE 
            WHEN q.material LIKE '%CEMENTO%' THEN COALESCE(eq_v.equipo, 'No encontrado')
            ELSE COALESCE(eq_g.equipo, 'No encontrado')
        END AS equipo,
        q.departamento,
        q.localidad AS localidad,
        q.centro_distribucion,
        q.material AS producto,
        q.incoterm AS incoterms,
        q.dia AS dia,
        CASE 
            WHEN LEN(CAST(q.cod_destinatario AS VARCHAR(20))) <= 5 
            THEN COALESCE(cen.codigo_sap_cliente, q.cod_destinatario)
            ELSE q.cod_destinatario 
        END AS codigo_cliente,
        COALESCE(q.despacho_t, 0) AS despacho_t,
        0 AS rf,
        0 AS rf_ajustado_im
    FROM [int_query] q
    LEFT JOIN ref_cen_1 cen ON cen.centro = UPPER(LTRIM(RTRIM(q.centro_destino))) AND cen.rn = 1
    LEFT JOIN [int_cartera] c ON c.cliente = (
        CASE 
            WHEN LEN(CAST(q.cod_destinatario AS VARCHAR(20))) <= 5 
            THEN COALESCE(cen.codigo_sap_cliente, q.cod_destinatario)
            ELSE q.cod_destinatario 
        END
    )
    LEFT JOIN ref_eq_v eq_v ON eq_v.vendedor_sap = c.vendedor AND eq_v.rn = 1
    LEFT JOIN ref_eq_g eq_g ON eq_g.grupo_vendedores = c.grupo_vendedores AND eq_g.rn = 1
    LEFT JOIN ref_eq_e eq_e ON eq_e.equipo = (
        CASE WHEN q.material LIKE '%CEMENTO%' THEN eq_v.equipo ELSE eq_g.equipo END
    ) AND eq_e.rn = 1
    LEFT JOIN ref_loc loc ON loc.localidad_despacho = q.localidad AND loc.rn = 1

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
    COALESCE(c.vendedor, 'Prospecto') AS vendedor,
    COALESCE(cen_tipo.tipo, 'VENTA DIRECTA') AS tipo_venta,
    COALESCE(alm_can.canal, 'OTROS') AS canal,
    COALESCE(sem.semana, 'SEMANA ' + CAST(((u.dia - 1) / 7 + 1) AS VARCHAR(10))) AS semana2

FROM union_base u
LEFT JOIN [int_cartera] c ON c.cliente = u.codigo_cliente
LEFT JOIN ref_cen_tipo cen_tipo ON cen_tipo.codigo_sap_cliente = u.codigo_cliente AND cen_tipo.rn = 1
LEFT JOIN ref_alm_seg alm_seg ON alm_seg.descripcion_sap = c.attribute_10 AND alm_seg.rn = 1
LEFT JOIN ref_alm_can alm_can ON alm_can.segmento = alm_seg.segmento AND alm_can.rn = 1
LEFT JOIN ref_sem sem ON sem.dia = u.dia AND sem.rn = 1
WHERE u.producto IN (
    'CEMENTO IM-40 (BIG-BAG )',
    'CEMENTO IM-40 (BOLSAS 50KG.)',
    'CEMENTO IM-40 (GRANEL TN.)',
    'CEMENTO PORTLAND IF-30 50 KG',
    'CEMENTO PORTLAND IF-30 BIG BAG',
    'CEMENTO PORTLAND IF-30 GRANEL',
    'CEMENTO PORTLAND IF-40 50 KG',
    'CEMENTO PORTLAND IF-40 50 KG-MQL',
    'CEMENTO PORTLAND IP-30 PRO 50 KG-MQL',
    'CEMENTO PORTLAND TIPO CPII-C40 BIG BAG'
)
GROUP BY 
    u.gerencia, u.equipo, u.departamento, u.localidad, u.centro_distribucion,
    u.producto, u.incoterms, u.dia, u.codigo_cliente,
    c.nombre_cliente, c.vendedor, cen_tipo.tipo, alm_can.canal, sem.semana;
