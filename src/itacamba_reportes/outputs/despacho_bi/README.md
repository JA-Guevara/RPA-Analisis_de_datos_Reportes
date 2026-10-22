# Slice de Salida: DESPACHO BI (Histórico Multianual Real)

## Descripción
Consolida el histórico acumulado de despachos reales para su consumo en Power BI. Reemplaza la hoja `DESPACHOS` de `HISTORIAL VENTAS.xlsx` y la Power Query `DESPACHOS BI`.

## Reglas Clave
1. **Solo Hechos Reales**: No contiene metas ni proyecciones de RF.
2. **Reemplazo por Mes**: En cada corrida diaria, reemplaza únicamente el mes que se está procesando en `int_query`, conservando intactos todos los meses y años previos.
3. **Enriquecimiento en BD**: Cruza en SQL Server contra `int_cartera` y las 5 tablas de referencias.
