# Slice de Entrada: REFERENCIAS.xlsx

## Descripción
Lee las hojas maestras del archivo `REFERENCIAS.xlsx` y las carga directamente a las tablas maestras dimensionales en la Base de Datos (`int_ref_*`).

## Tablas Generadas
- `int_ref_almacen`: Relación de descripción SAP, Canal y Segmento (`segmento`: `String(100)`, permite descripciones de más de 50 caracteres como obras de saneamiento).
- `int_ref_centro`: La hoja Centros mezcla dos tablas: unas 93 filas de centros (centro → código SAP de cliente) y 84 filas sin centro que son una lista de clientes con su tipo de venta (código → VENTA INDIRECTA). La columna `nombre` del modelo no existe en el Excel.
- `int_ref_equipo`: Vendedores, grupos de vendedores, equipo comercial y gerencia.
- `int_ref_localidad`: Mapeo de localidad de despacho a localidad IM.
- `int_ref_material`: Códigos y descripciones oficiales de materiales (`codigo`: `BigInteger`).
- `int_ref_semana`: Equivalencia de día a semana comercial (`dia`: `Integer` del 1 al 31).

## Estrategia de Carga
Truncado y carga masiva directa (`bulk_insert_df`) en cada corrida para asegurar que cualquier actualización realizada por el área comercial se propague de inmediato.
