# Slice de Salida: VENTAS BI (Histórico Multianual con Versionado)

## Descripción
Consolida el histórico acumulado de ventas para consumo en Power BI. Reemplaza la Power Query `VENTAS BI` y el archivo `HISTORIAL VENTAS.xlsx`.

## Reglas de Acumulación SCD Tipo 2
- **Llave de Negocio**: `[ejercicio, documento_comercial, numero_documento, material]`.
- **Nuevos documentos**: Se insertan como versión 1 con `is_current = 1`.
- **Cambio en columnas SAP (`source_hash`)**: Se crea una nueva versión (versión $N+1$) y la anterior pasa a `is_current = 0`.
- **Cambio solo en derivadas (`derived_hash`)**: **pendiente**. Se detecta y se cuenta en el log, pero no se actualiza la fila (falta el UPDATE). Hasta implementarlo, después de corregir una regla hay que reconstruir el mes.
