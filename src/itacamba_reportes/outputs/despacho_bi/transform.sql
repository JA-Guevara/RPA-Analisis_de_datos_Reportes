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
    SELECT centro, codigo_sap_cliente, nombre,
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
    centro_origen, ds_centro_origen, cod_material, material,
    fecha_salida, nro_pedido, cod_destinatario, nom_destinatario,
    poblacion, incoterm, clase_doc_ventas, centro_destino,
    ds_centro_destino, atributo_7, departamento_facturacion,
    clase_expedicion, vc_embalaje, cod_transportista, transportista,
    nombre_transportista, telefono_1, tipo_servicio_transporte,
    placa, tipo_vehiculo, cod_ruta, nom_ruta, distancia_km,
    numero_transporte, distancia, cantidad, despacho_t,
    departamento, traslados_t, mes, anio, grupo_producto,
    tipo_traslado, producto, centro_distribucion, link,
    provincia, semana_anio, traslados, zona_descarga, cd,
    localidad, tipo_venta, vendedor, desarrollador,
    codigo_cliente, nombre_cliente, equipo, localidad_im, incoterms_im,
    gerencia, semana, dia, canal, cod_pagador, pagador
)
SELECT 
    q.centro_origen,
    COALESCE(q.nom_centro_origen, cen_orig.nombre, q.centro_origen) AS ds_centro_origen,
    q.cod_material,
    q.material,
    q.fecha_salida,
    q.nro_pedido,
    q.cod_destinatario,
    q.nom_destinatario,
    COALESCE(c.poblacion, q.localidad) AS poblacion,
    q.incoterm,
    'Venta de Stock - Off' AS clase_doc_ventas,
    q.centro_destino,
    COALESCE(q.nom_centro_destino, cen.nombre, 'Sin asignar') AS ds_centro_destino,
    COALESCE(c.attribute_7, 'VC-BO-Z5') AS atributo_7,
    COALESCE(c.region_nombre, q.departamento, 'Santa Cruz') AS departamento_facturacion,
    'Terrestre' AS clase_expedicion,
    'E' AS vc_embalaje,
    NULL AS cod_transportista,
    NULL AS transportista,
    NULL AS nombre_transportista,
    NULL AS telefono_1,
    NULL AS tipo_servicio_transporte,
    NULL AS placa,
    NULL AS tipo_vehiculo,
    q.cod_ruta,
    q.nom_ruta,
    NULL AS distancia_km,
    NULL AS numero_transporte,
    NULL AS distancia,
    (COALESCE(q.despacho_t, 0) + COALESCE(q.traslados_t, 0)) AS cantidad,
    q.despacho_t,
    q.departamento,
    q.traslados_t,
    q.mes,
    q.anio,
    CASE 
        WHEN q.material LIKE '%CLINQUER%' THEN 'Clinker'
        WHEN q.material LIKE '%AGREGADOS%' THEN 'Agregados'
        ELSE 'Cemento Interno'
    END AS grupo_producto,
    CASE 
        WHEN q.material LIKE '%GRANEL%' THEN 'Granel'
        WHEN q.material LIKE '%BIG BAG%' OR q.material LIKE '%BIG-BAG%' THEN 'Big Bag'
        ELSE 'Embolsado'
    END AS tipo_traslado,
    q.material AS producto,
    q.centro_distribucion,
    NULL AS link,
    COALESCE(c.barrio, 'IT-SC-ANDRES IBAÑEZ') AS provincia,
    DATEPART(isowk, q.fecha_salida) AS semana_anio,
    NULL AS traslados,
    CASE 
        WHEN UPPER(q.departamento) LIKE '%SANTA CRUZ%' THEN 'SCZ-LOCAL' 
        ELSE 'INTERIOR' 
    END AS zona_descarga,
    'CD' AS cd,
    q.localidad,
    CASE 
        WHEN c.canal_distribucion = '10' THEN 'VENTA DIRECTA' 
        ELSE 'VENTA INDIRECTA' 
    END AS tipo_venta,

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

    -- Código Cliente: si len(destinatario) <= 5 cruza centro_destino con Centros (H:I)
    calc_cli.codigo_cliente,
    COALESCE(c.nombre_cliente, 'Prospecto') AS nombre_cliente,

    -- Equipo
    CASE 
        WHEN q.material LIKE '%CEMENTO%' THEN COALESCE(eq_v.equipo, 'OTROS')
        ELSE COALESCE(eq_g.equipo, 'OTROS')
    END AS equipo,

    -- Localidad IM
    COALESCE(loc.localidad_im, q.localidad) AS localidad_im,

    NULL AS incoterms_im,

    -- Gerencia
    COALESCE(eq_e.gerencia, 'OTROS') AS gerencia,

    -- Semana
    COALESCE(sem.semana, 'SEMANA 0') AS semana,

    -- x (día del mes 1..31)
    q.dia,

    -- Columnas auxiliares internas
    COALESCE(alm_can.canal, 'OTROS') AS canal,
    q.cod_pagador,
    q.pagador

FROM [int_query] q
LEFT JOIN ref_cen cen_orig ON cen_orig.centro = UPPER(LTRIM(RTRIM(q.centro_origen))) AND cen_orig.rn = 1
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
