# Reporte DESPACHO BI

Detalle de despachos a nivel transacción (réplica de la hoja
`DESPACHOS BI` del basepanel del cliente). Compone `int_query` (mes
objetivo) con cartera + 5 catálogos de referencia y entrega
`int_despacho_bi` + export Excel.

## Dónde está cada cosa

| Necesidad | Archivo |
|---|---|
| Fórmula de una columna (VLOOKUP, concat, espejo) | `columnas.yaml` |
| Qué columnas se heredan de int_query | `config.yaml` → `source_columns` |
| Fuente, tablas, dependencias, llave | `manifest.yaml` |
| Orquestación (stages) | `pipeline.py` (`build_pipeline()`) |
| Subset/mapping de entrada | `mapping.py` |
| Modelo SQL | `persistence/models/int/despacho_bi_model.py` (centralizado) |

## Cambiar una fórmula

1. Editar el bloque en `columnas.yaml` (cada bloque referencia la
   fórmula original del basepanel).
2. `python tools/calibracion/simular_despacho.py` + diff de paridad.
3. `pytest tests/` (goldens); si el cambio es intencional, re-capturar.
4. Correr pipeline en prueba y comparar export.

## Historia

Calibrado 2026-07-01 (3 bugs: desarrollador, semana, incoterms_im — ver
`Calibracion_Despacho_Fase2_2026-07-01.md` en la carpeta de docs).
Migrado a slice vertical en Fase 3 del plan 2026-07-06.
