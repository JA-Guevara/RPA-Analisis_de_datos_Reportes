# Slice de Entrada: QUERY.xlsx (Despachos Operativos SAP ZBCS)

## Descripción
Lee la información de despachos operativos extraída de SAP (transacción `ZBCS`, layout `IM`). Reemplaza la hoja `QUERY` de `basepanel.xlsm`.

## Formato de Entrada
- **Archivo**: `QUERY*.xlsx`
- **Hoja**: `base`
- **Encabezado**: primera fila de la hoja (`header_row=0`)
- **Columnas**: 24 columnas oficiales de SAP ZBCS (Fecha salida, fecha creación entrega, pedido, incoterms, centros, materiales, rutas, destinatario, pagador, cantidad en toneladas, facturación).

## Tipos de Datos y Normalización
- `fecha_salida`: `DateTime` (fecha efectiva: `COALESCE(fecha_salida, fecha_creacion_entrega)`).
- `dia`: `Integer` ($1..31$, extraído como `DAY(fecha_efectiva)` para alineación dimensional).
- `mes`: `Integer` ($1..12$).
- `anio`: `Integer` ($YYYY$).
- `despacho_t` y `traslados_t`: `Numeric(18, 4)`.

## Transformación en BD (`transform.sql`)
1. Determina la fecha efectiva (`COALESCE(fecha_salida, fecha_creacion_entrega)`).
2. **Macro `EliminarMeses`**: Filtra en SQL para conservar únicamente el mes objetivo en curso.
3. Clasifica toneladas de despacho y centro de distribución.
