-- ====================================================================
-- Slice: DESPACHO BI
-- Transformación: int_query -> int_despacho_bi (Acumulado real)
-- ====================================================================

-- 1. Eliminar únicamente los registros del mes que vamos a cargar para no duplicar
DELETE FROM [int_despacho_bi] 
WHERE mes IN (SELECT DISTINCT mes FROM [int_query])
  AND anio IN (SELECT DISTINCT anio FROM [int_query]);

-- 2. Insertar los despachos enriquecidos con cruces en BD
WITH ref_cen AS (
    SELECT centro, codigo_sap_cliente,
           ROW_NUMBER() OVER (PARTITION BY UPPER(LTRIM(RTRIM(centro))) ORDER BY id) AS rn
    FROM [int_ref_centro]
    WHERE centro IS NOT NULL AND centro <> ''
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
ref_loc AS (
    SELECT localidad_despacho, localidad_im,
           ROW_NUMBER() OVER (PARTITION BY UPPER(LTRIM(RTRIM(localidad_despacho))) ORDER BY id) AS rn
    FROM [int_ref_localidad]
    WHERE localidad_despacho IS NOT NULL AND localidad_despacho <> ''
),
ref_sem AS (
    SELECT dia, semana,
           ROW_NUMBER() OVER (PARTITION BY dia ORDER BY id) AS rn
    FROM [int_ref_semana]
    WHERE dia IS NOT NULL
)
INSERT INTO [int_despacho_bi] (
    fecha_salida, dia, mes, anio, nro_pedido, incoterm,
    centro_origen, centro_destino, cod_material, material,
    cod_ruta, nom_ruta, cod_destinatario, nom_destinatario,
    cod_pagador, pagador, despacho_t, traslados_t,
    centro_distribucion, localidad, departamento,
    codigo_cliente, nombre_cliente, vendedor, desarrollador,
    equipo, gerencia, canal, localidad_im, semana
)
SELECT 
    q.fecha_salida,
    q.dia,
    q.mes,
    q.anio,
    q.nro_pedido,
    q.incoterm,
    q.centro_origen,
    q.centro_destino,
    q.cod_material,
    q.material,
    q.cod_ruta,
    q.nom_ruta,
    q.cod_destinatario,
    q.nom_destinatario,
    q.cod_pagador,
    q.pagador,
    q.despacho_t,
    q.traslados_t,
    q.centro_distribucion,
    q.localidad,
    q.departamento,

    -- Código Cliente: si len(destinatario) <= 5 cruza centro_destino con Centros (H:I)
    calc_cli.codigo_cliente,
    COALESCE(c.nombre_cliente, 'Prospecto') AS nombre_cliente,

    -- Vendedor: regla 5281728 (La Paz -> Vivian, Cbba -> Salustia) o Cartera
    CASE 
        WHEN calc_cli.codigo_cliente = 5281728 THEN
            CASE 
                WHEN UPPER(q.departamento) = 'LA PAZ' THEN 'VIVIAN JANETH ARZABE CALZADILLA'
                WHEN UPPER(q.departamento) = 'COCHABAMBA' THEN 'SALUSTIA CONDORI VELA'
                ELSE 'No encontrado'
            END
        ELSE COALESCE(c.vendedor, 'OTROS')
    END AS vendedor,

    -- Desarrollador: vendedor_ok en Equipo
    COALESCE(eq_v.vendedor_ok, 'OTROS') AS desarrollador,

    -- Equipo
    CASE 
        WHEN q.material LIKE '%CEMENTO%' THEN COALESCE(eq_v.equipo, 'OTROS')
        ELSE COALESCE(eq_g.equipo, 'OTROS')
    END AS equipo,

    -- Gerencia
    COALESCE(eq_e.gerencia, 'OTROS') AS gerencia,

    -- Canal (Búsqueda en 2 pasos: attribute_10 -> segmento -> canal)
    COALESCE(alm_can.canal, 'OTROS') AS canal,

    -- Localidad IM
    COALESCE(loc.localidad_im, q.localidad) AS localidad_im,

    -- Semana
    COALESCE(sem.semana, 'SEMANA 0') AS semana

FROM [int_query] q
LEFT JOIN ref_cen cen ON cen.centro = UPPER(LTRIM(RTRIM(q.centro_destino))) AND cen.rn = 1
CROSS APPLY (
    SELECT CASE 
        WHEN LEN(CAST(q.cod_destinatario AS VARCHAR(20))) <= 5 
        THEN COALESCE(cen.codigo_sap_cliente, q.cod_destinatario)
        ELSE q.cod_destinatario
    END AS codigo_cliente
) calc_cli
LEFT JOIN [int_cartera] c ON c.cliente = calc_cli.codigo_cliente
LEFT JOIN ref_eq_v eq_v ON eq_v.vendedor_sap = c.vendedor AND eq_v.rn = 1
LEFT JOIN ref_eq_g eq_g ON eq_g.grupo_vendedores = c.grupo_vendedores AND eq_g.rn = 1
LEFT JOIN ref_eq_e eq_e ON eq_e.equipo = (
    CASE 
        WHEN q.material LIKE '%CEMENTO%' THEN eq_v.equipo 
        ELSE eq_g.equipo 
    END
) AND eq_e.rn = 1
LEFT JOIN ref_alm_seg alm_seg ON alm_seg.descripcion_sap = c.attribute_10 AND alm_seg.rn = 1
LEFT JOIN ref_alm_can alm_can ON alm_can.segmento = alm_seg.segmento AND alm_can.rn = 1
LEFT JOIN ref_loc loc ON loc.localidad_despacho = q.localidad AND loc.rn = 1
LEFT JOIN ref_sem sem ON sem.dia = q.dia AND sem.rn = 1;
