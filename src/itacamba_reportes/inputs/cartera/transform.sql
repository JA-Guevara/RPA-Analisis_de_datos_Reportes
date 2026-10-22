-- ====================================================================
-- Slice: CARTERA
-- Transformación: stg_cartera -> int_cartera (Normalización, Deduplicación y Donaciones)
-- ====================================================================

TRUNCATE TABLE [int_cartera];

WITH ranked_cartera AS (
    SELECT 
        s.*,
        ROW_NUMBER() OVER(PARTITION BY s.cliente ORDER BY s.orden_origen ASC) AS rn
    FROM [stg_cartera] s
    WHERE s.cliente IS NOT NULL AND s.cliente > 0
)
INSERT INTO [int_cartera] (
    orden_origen,
    cliente,
    nombre_cliente,
    attribute_10,
    poblacion,
    barrio,
    attribute_7,
    attribute_6,
    region,
    region_nombre,
    grupo_cuentas,
    sector,
    sector_desc,
    canal_distribucion,
    canal_distribucion_desc,
    organizacion_ventas,
    oficina_ventas,
    grupo_vendedores,
    equipo,
    vendedor,
    coordinador,
    canal,
    condicion_pago
)
SELECT 
    s.orden_origen,
    s.cliente,
    s.nombre_cliente,
    s.attribute_10,
    s.poblacion,
    s.barrio,
    s.attribute_7,
    s.attribute_6,
    s.region,
    UPPER(REPLACE(s.region_nombre, 'POTOSÍ', 'POTOSI')) AS region_nombre,
    s.grupo_cuentas,
    s.sector,
    s.sector_desc,
    s.canal_distribucion,
    s.canal_distribucion_desc,
    s.organizacion_ventas,
    s.oficina_ventas,
    s.grupo_vendedores,
    s.equipo,
    
    -- Macro ModificarDonaciones
    CASE 
        WHEN s.nombre_cliente IN (
            'Cliente Donaciones',
            'DONACIONES DTM',
            'CLIENTE GENERICO SIN FACTURA',
            'DONACIONES COMERCIAL'
        ) THEN 'DONACION'
        ELSE COALESCE(s.vendedor, '0')
    END AS vendedor,
    
    CASE 
        WHEN s.nombre_cliente IN (
            'Cliente Donaciones',
            'DONACIONES DTM',
            'CLIENTE GENERICO SIN FACTURA',
            'DONACIONES COMERCIAL'
        ) THEN 'DONACION'
        ELSE COALESCE(s.coordinador, '0')
    END AS coordinador,

    s.canal,
    s.condicion_pago
FROM ranked_cartera s
WHERE s.rn = 1;
