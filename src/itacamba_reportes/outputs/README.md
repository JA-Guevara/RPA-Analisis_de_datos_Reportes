# Outputs - Slices Verticales de Salida y Reportes BI

Agrupa los módulos que producen los reportes consumidos por Power BI, la Gerencia Comercial y Operaciones.

## Slices de Salida

### 1. `ventas_bi` - Histórico de Ventas Multianual
- **Fuente:** `int_gd20` (BASE PANEL del mes) + Histórico acumulado `int_ventas_bi`.
- **Lógica:** Implementa **Slowly Changing Dimensions Tipo 2 (SCD2)**:
  - Compara `source_hash` (columnas SAP) y `derived_hash` (columnas calculadas).
  - Si cambian columnas de SAP, vence la fila anterior (`is_current = 0`, `valid_to = NOW`) y crea una nueva versión (`version + 1`).
  - Si solo cambian columnas derivadas por recalibración, actualiza en el lugar.
- **Exportación:** `storage/exports/VENTAS_BI_YYYY-MM-DD_HHMM.xlsx`.

### 2. `despacho_bi` - Histórico Real de Despachos
- **Fuente:** `int_query` (Despachos operativos) enriquecidos con cruces a `int_ref_*` y `int_cartera`.
- **Lógica:** Acumula históricamente año tras año. Al ejecutarse, reemplaza **únicamente el mes en curso** en `int_despacho_bi`, preservando intactos los registros de meses y años pasados.
- **Regla de Oro:** **Nunca** incluye proyecciones ni metas RF; solo despachos reales.
- **Exportación:** `storage/exports/DESPACHO_BI_YYYY-MM-DD_HHMM.xlsx`.

### 3. `despacho_mes` - Resumen Mensual Operativo + Proyección
- **Fuente:** Unión vertical (`UNION ALL`) de:
  1. `int_query`: Despachos reales ejecutados hasta el día de ayer.
  2. `stg_proyeccion`: Proyección comercial semanal (`RF AJUSTADO SEMANAL`) desde el día de hoy hasta fin de mes.
- **Métrica Clave:** `PROYECCION = CASE WHEN dia < dia_corte THEN despacho_t ELSE rf_ajustado_im END`.
- **Exportación:** `storage/exports/DESPACHO_MES_YYYY-MM-DD_HHMM.xlsx`.
