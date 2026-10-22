-- ====================================================================
-- Slice: DESPACHO BI
-- Transformación: int_query -> int_despacho_bi (Acumulado real)
-- ====================================================================

-- 1. Eliminar únicamente los registros del mes que vamos a cargar para no duplicar
DELETE FROM [int_despacho_bi] 
WHERE mes IN (SELECT DISTINCT mes FROM [int_query])
  AND anio IN (SELECT DISTINCT anio FROM [int_query]);

-- 2. Insertar los despachos enriquecidos con cruces en BD
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

    -- Codigo Cliente
    COALESCE(cen.codigo_sap_cliente, q.cod_destinatario) AS codigo_cliente,
    COALESCE(c.nombre_cliente, 'Prospecto') AS nombre_cliente,
    COALESCE(c.vendedor, '0') AS vendedor,
    COALESCE(eq_v.vendedor_ok, 'No encontrado') AS desarrollador,

    -- Equipo
    CASE 
        WHEN q.material LIKE '%CEMENTO%' THEN COALESCE(eq_v.equipo, 'No encontrado')
        ELSE COALESCE(eq_g.equipo, 'No encontrado')
    END AS equipo,

    -- Gerencia
    COALESCE(eq_e.gerencia, 'OTROS') AS gerencia,

    -- Canal
    COALESCE(alm.canal, 'OTROS') AS canal,

    -- Localidad IM
    COALESCE(loc.localidad_im, q.localidad) AS localidad_im,

    -- Semana
    COALESCE(sem.semana, 'SEMANA 0') AS semana

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
    CASE 
        WHEN q.material LIKE '%CEMENTO%' THEN eq_v.equipo 
        ELSE eq_g.equipo 
    END
)
LEFT JOIN (
    SELECT descripcion_sap, MIN(canal) AS canal
    FROM [int_ref_almacen]
    WHERE descripcion_sap IS NOT NULL AND descripcion_sap != ''
    GROUP BY descripcion_sap
) alm ON alm.descripcion_sap = c.attribute_10
LEFT JOIN (
    SELECT localidad_despacho, MIN(localidad_im) AS localidad_im
    FROM [int_ref_localidad]
    WHERE localidad_despacho IS NOT NULL AND localidad_despacho != ''
    GROUP BY localidad_despacho
) loc ON loc.localidad_despacho = q.localidad
LEFT JOIN (
    SELECT dia, MIN(semana) AS semana
    FROM [int_ref_semana]
    WHERE dia IS NOT NULL AND dia != ''
    GROUP BY dia
) sem ON sem.dia = q.dia;
