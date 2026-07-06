# Reporte GD20 / VENTAS BI

El reporte más crítico: GD20 SAP → `int_gd20` (snapshot del período) →
UPSERT SCD2 → `int_ventas_bi` (histórico versionado por hash) → export.

## Dónde está cada cosa

| Necesidad | Archivo |
|---|---|
| Lookup/fórmula simple (cartera, material, equipo, almacén, centro, tipo_embalaje, region_m) | `columnas.yaml` |
| CD / Zona de Entrega (5 capas sobre stg_query) | `reglas.py` → `Gd20CdZeRule` |
| Overrides por centro físico (LOGISTICA→CLINQUER, …) | `config.yaml` → `centro_overrides` (mecanismo en `reglas.py`) |
| Fórmulas numéricas (ingreso_bruto, volumen, bonificaciones) | `reglas.py` → `Gd20BusinessRulesUseCase` |
| Constantes de negocio (0.87, 1.42, cuenta bonif.) | `config.yaml` → `constants` |
| Renames SAP→negocio | `mapping.py` + `config.yaml` |
| Qué compone cada hash SCD2 | `persistence/row_hasher.py` |
| Mecanismo MERGE SCD2 | `persistence/repositories/ventas_bi_repository_sql.py` |

## Regla de oro del histórico

Cualquier cambio acá debe pasar el gate de hashes: correr
`tools/calibracion/simular_gd20.py` antes y después — si un
`source_hash`/`derived_hash` cambia sin querer, el histórico versionará
filas falsamente. Paridad byte a byte verificada en la migración
2026-07-06 (Fase 4).

## Decisiones calibradas registradas

- `zona_entrega` = col `ruta` de QUERY (no `zona_descarga`) — validado.
- Overrides de centro validados contra BASE PANEL mayo 2026.
- `_rule_codigo_cliente_zero_fill` y `override_nombre_dest_from_query`
  DESACTIVADOS por default (el basepanel no los aplica; flags en config).
- post_replaces: solo tipo_venta AGENCIA→VENTA INDIRECTA.
