-- ====================================================================
-- Slice: QUERY (SAP ZBCS)
-- Transformación: stg_query -> int_query (Filtro mes y clasificación)
-- ====================================================================

TRUNCATE TABLE [int_query];

INSERT INTO [int_query] (
    fecha_salida,
    dia,
    mes,
    anio,
    nro_pedido,
    incoterm,
    centro_origen,
    centro_destino,
    cod_material,
    material,
    cod_ruta,
    nom_ruta,
    cod_destinatario,
    nom_destinatario,
    cod_pagador,
    pagador,
    despacho_t,
    traslados_t,
    centro_distribucion,
    localidad,
    departamento
)
SELECT 
    COALESCE(q.fecha_salida, q.fecha_creacion_entrega) AS fecha_salida,
    DAY(COALESCE(q.fecha_salida, q.fecha_creacion_entrega)) AS dia,
    MONTH(COALESCE(q.fecha_salida, q.fecha_creacion_entrega)) AS mes,
    YEAR(COALESCE(q.fecha_salida, q.fecha_creacion_entrega)) AS anio,
    q.nro_pedido,
    COALESCE(q.incoterm, 'OTROS') AS incoterm,
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
    COALESCE(q.cantidad_ton, 0) AS despacho_t,
    0 AS traslados_t,
    COALESCE(q.nom_centro_origen, 'OTROS') AS centro_distribucion,
    COALESCE(q.nom_ruta, 'OTROS') AS localidad,
    'SANTA CRUZ' AS departamento
FROM [stg_query] q
WHERE (
    YEAR(COALESCE(q.fecha_salida, q.fecha_creacion_entrega)) = (
        SELECT MAX(YEAR(COALESCE(fecha_salida, fecha_creacion_entrega))) 
        FROM [stg_query] 
        WHERE fecha_salida IS NOT NULL OR fecha_creacion_entrega IS NOT NULL
    )
    AND MONTH(COALESCE(q.fecha_salida, q.fecha_creacion_entrega)) = (
        SELECT MAX(MONTH(COALESCE(fecha_salida, fecha_creacion_entrega))) 
        FROM [stg_query] 
        WHERE fecha_salida IS NOT NULL OR fecha_creacion_entrega IS NOT NULL
    )
);
