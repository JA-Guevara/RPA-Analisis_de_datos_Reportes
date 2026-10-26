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
    f_calc.fecha_efectiva AS fecha_salida,
    DAY(f_calc.fecha_efectiva) AS dia,
    MONTH(f_calc.fecha_efectiva) AS mes,
    YEAR(f_calc.fecha_efectiva) AS anio,
    q.nro_pedido,
    COALESCE(q.incoterm, 'OTROS') AS incoterm,
    q.centro_origen,
    q.centro_destino,
    q.cod_material,
    CASE 
        WHEN q.material LIKE '%CALCÁREO CORRECTIVO DE SUELO BRÓTER M30%%' THEN 'BRÓTER MIX AZCALMAG 30+'
        WHEN q.material LIKE '%CALCÁREO CORRECTIVO DE SUELO BRÓTER DOLO%' THEN 'BRÓTER DOLOMITA 86+'
        ELSE q.material
    END AS material,
    q.cod_ruta,
    q.nom_ruta,
    q.cod_destinatario,
    q.nom_destinatario,
    q.cod_pagador,
    q.pagador,
    CASE 
        WHEN CONCAT(q.centro_origen, '|', CAST(q.cod_destinatario AS VARCHAR(20))) IN (
            '4B06|4495', '4B06|4689', '4B05|4689', '4B04|4495', '4B06|5181',
            '4B05|5181', '4B05|5217', '4B09|5217', '4B06|5217', '4B63|5217',
            '4B06|4496', '4B05|4496', '4B60|4689', '4B60|4495', '4B05|4495',
            '4B1A|4495', '4B1A|6497'
        ) THEN 0
        ELSE COALESCE(q.cantidad_ton, 0)
    END AS despacho_t,
    CASE 
        WHEN CONCAT(q.centro_origen, '|', CAST(q.cod_destinatario AS VARCHAR(20))) IN (
            '4B06|4495', '4B06|4689', '4B05|4689', '4B04|4495', '4B06|5181',
            '4B05|5181', '4B05|5217', '4B09|5217', '4B06|5217', '4B63|5217',
            '4B06|4496', '4B05|4496', '4B60|4689', '4B60|4495', '4B05|4495',
            '4B1A|4495', '4B1A|6497'
        ) THEN COALESCE(q.cantidad_ton, 0)
        ELSE 0
    END AS traslados_t,
    CASE q.centro_origen
        WHEN '4B09' THEN 'CD COCHABAMBA'
        WHEN '4B06' THEN 'FABRICA YACUSES'
        WHEN '4B05' THEN 'CD GUARACACHI'
        WHEN '4B01' THEN 'FAB. GB MINERALES'
        WHEN '4B03' THEN 'VCBO - CD SANTA CRUZ'
        WHEN '4B04' THEN 'VCBO - MOLIENDA'
        WHEN '4B60' THEN 'CD EL ALTO'
        WHEN '4B63' THEN 'CD MONTERO'
        WHEN '4B94' THEN 'CHACHI'
        WHEN '4B1A' THEN 'CENTRO INSUMOS'
        WHEN '4B3A' THEN 'CD INSUMOS'
        WHEN '4B12' THEN 'TERMINAL DE CARGA'
        ELSE 'OTROS'
    END AS centro_distribucion,
    COALESCE(r.localidad, NULLIF(c_dest.poblacion, '0'), q.nom_ruta, 'OTROS') AS localidad,
    COALESCE(r.departamento, NULLIF(c_dest.region_nombre, '0'), 'SANTA CRUZ') AS departamento
FROM [stg_query] q
CROSS APPLY (
    SELECT CASE 
        WHEN q.material = 'CLINQUER' AND q.fecha_salida IS NULL THEN q.fecha_creacion_entrega
        ELSE q.fecha_salida 
    END AS fecha_efectiva
) f_calc
LEFT JOIN [int_ref_ruta] r ON r.codigo_ruta = q.cod_ruta
LEFT JOIN [int_cartera] c_dest ON c_dest.cliente = q.cod_destinatario
WHERE f_calc.fecha_efectiva IS NOT NULL
  AND DATEFROMPARTS(YEAR(f_calc.fecha_efectiva), MONTH(f_calc.fecha_efectiva), 1) = (
      SELECT MAX(DATEFROMPARTS(
          YEAR(CASE WHEN material = 'CLINQUER' AND fecha_salida IS NULL THEN fecha_creacion_entrega ELSE fecha_salida END),
          MONTH(CASE WHEN material = 'CLINQUER' AND fecha_salida IS NULL THEN fecha_creacion_entrega ELSE fecha_salida END),
          1
      ))
      FROM [stg_query]
      WHERE (CASE WHEN material = 'CLINQUER' AND fecha_salida IS NULL THEN fecha_creacion_entrega ELSE fecha_salida END) IS NOT NULL
  );
