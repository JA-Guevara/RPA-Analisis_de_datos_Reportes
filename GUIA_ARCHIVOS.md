# Guía del proyecto — qué hace cada archivo

Un renglón por archivo. Columna "tocás cuando": **F** = cambiar fórmulas
/ configuración (lo habitual) · **O** = ocasional (tests, calibración)
· **N** = casi nunca (motor / infraestructura).

## Raíz

| Archivo | Qué hace | Tocás |
|---|---|---|
| `main.py` | Entrada del bot: `python main.py run-all` | N |
| `alembic.ini` + `alembic/` | Migraciones de BD (0003 espera en rama fase6) | N |
| `scripts/empaquetar.py` | ZIP limpio para entregas (`git archive`) | O |
| `.env` | Credenciales y rutas LOCALES (nunca se versiona) | O |
| `.gitignore` | Qué no entra a git (venv, storage, .env) | N |
| `GUIA_ARCHIVOS.md` | Este documento | — |

## `src/itacamba_reportes/reportes/` — LOS 6 REPORTES (acá vive el negocio)

Cada carpeta tiene los mismos archivos con el mismo rol:

| Archivo (en cada reporte) | Qué hace | Tocás |
|---|---|---|
| `columnas.yaml` | **Las fórmulas del cliente** (VLOOKUP, concat, case…), un bloque por columna, autodocumentado | **F** |
| `config.yaml` | Parámetros: archivo/hoja fuente, renames, mes objetivo, overrides, umbrales de CONTROL | **F** |
| `reglas.py` | Solo lógica compleja no expresable en YAML (macros VBA portadas, CD/ZE, fórmulas numéricas) | O |
| `pipeline.py` | Orquestación de etapas + `build_pipeline()` | N |
| `manifest.yaml` | Portada técnica: entrada, tablas, dependencias, llave (validada por verificar.py) | O |
| `README.md` | Tabla "quiero X → toco Y" del reporte | O |
| `__init__.py` | Helpers de carga del slice | N |

Particularidades por reporte:

| Reporte | Extra | Nota |
|---|---|---|
| `referencias/` | — | REFERENCIAS.xlsx → 6 tablas `int_ref_*`. **Los datos de negocio se editan en el Excel, no acá** |
| `cartera/` | `normalizacion.py`, `contrato.py` | 100% spec-driven desde su config.yaml (Pydantic + contrato pandera) |
| `query/` | `mapping.py` | QUERY.xlsx → stg (fiel) + int (mes objetivo). Insumo de despachos y del CD/ZE de ventas |
| `gd20_ventas_bi/` | `mapping.py`, `enriquecimiento.py` | El crítico: alimenta el HISTÓRICO SCD2. Cambios acá exigen gate de hashes |
| `despacho_bi/` | `mapping.py` | 15 fórmulas en catálogo |
| `despacho_mes/` | `agregacion.py` | GROUP BY del mes + 7 fórmulas + macros de limpieza |

## `src/itacamba_reportes/` — motor común (sin reglas de negocio)

| Archivo | Qué hace | Tocás |
|---|---|---|
| `cli.py` | Registra los comandos `run-*` y delega en cada slice | N |
| `transforms/column_engine.py` | Ejecuta los `columnas.yaml` (6 operaciones: copy, const, case, concat, lookup, branch) | N |
| `transforms/common.py` | Mapeo de columnas genérico + interfaz de reglas | N |
| `pipelines/runner.py` | Ciclo común con change-detection por huella de archivo | N |
| `pipelines/run_all.py` | El DAG: referencias+cartera → query → ventas y despachos | N |
| `pipelines/file_state.py` | Huellas (mtime+size) para no reprocesar archivos iguales | N |
| `config/env_config.py` | Lee `.env` (BD, rutas) | N |
| `config/paths.py` | Rutas de datos (inbox/exports/…) | N |
| `config/yaml_loader.py` | Carga configs y catálogos; registro de qué reporte vive en qué slice | N |
| `config/sources.py` | Construye lectores de Excel desde los configs | N |
| `config/dataset_spec.py` | Validación Pydantic de la spec de cartera | N |
| `config/manifest.py` | Valida que los manifest.yaml no mientan (los cruza contra modelos reales) | N |
| `ingestion/excel_reader.py` + `excel_source.py` | Lector genérico de Excel (renames, dedupe, skip) | N |
| `shared/control_corrida.py` | **Control de corrida**: hash de contenido + % sin-match con umbrales + registro en bitácora | N |
| `shared/logging_setup.py`, `pandas_utils.py`, `null_tokens.py` | Utilidades (logs, Int64, tokens nulos SAP) | N |

## `src/itacamba_reportes/persistence/` — base de datos

| Archivo | Qué hace | Tocás |
|---|---|---|
| `models/stg/*` | Tablas espejo del Excel crudo (stg_query, stg_gd20, stg_cartera) | O* |
| `models/int/*` | Tablas de reportes (int_query, int_gd20, int_ventas_bi, int_despacho_*) | O* |
| `models/references/*` | Las 6 tablas de catálogos | O* |
| `repositories/*_repository_sql.py` | Escritura bulk de cada tabla | N |
| `repositories/ventas_bi_repository_sql.py` | **El histórico**: MERGE SCD2 por hash (no tocar sin gate) | N |
| `repositories/reference_loader.py` | Carga de catálogos + registro catálogo→modelo | N |
| `row_hasher.py` | Qué columnas componen los hashes del histórico | N |
| `excel_report_exporter.py` | Genera los .xlsx (hoja DATOS + hoja CONTROL) | N |
| `execution_tracker.py` | Bitácora `pipeline_executions` en BD | N |
| `engine.py`, `session.py`, `base.py`, `bulk_insert.py`, `df_to_rows.py`, `type_coercion.py`, `lookups.py`, `mixins.py` | Conexión, sesiones e inserción rápida | N |

\* O = solo al agregar/quitar columnas (junto con migración Alembic).

## `tests/` y `tools/` — se usan de vez en cuando, por separado

| Archivo | Qué hace | Cuándo correrlo |
|---|---|---|
| `tools/verificar.py` | **El único comando de control**: compila + tests + manifests + paridad | Antes de dar por bueno cualquier cambio |
| `tools/calibracion/simular_despacho.py` / `simular_gd20.py` | Reproducen los reportes en memoria sin BD (para comparar) | Al calibrar o tras cambiar fórmulas |
| `tools/calibracion/diff_contra_libro.py` | Compara contra el libro Excel del cliente | Cuando tengas el basepanel |
| `tests/test_column_engine.py` | 17 tests del motor de fórmulas | Los corre verificar.py |
| `tests/test_control_corrida.py` | 5 tests del control de corrida | Los corre verificar.py |
| `tests/test_bulk_insert.py`, `test_native_records.py` | Tests de inserción/tipos | Los corre verificar.py |
| `tests/characterization/` | Los "goldens": congelan el comportamiento para detectar cambios accidentales | Los corre verificar.py |
| `tests/test_db_connection.py`, `test_extraction_excel.py`, `benchmark_inserts.py` | Requieren BD/archivos reales | Manual, rara vez |

## Comandos del día a día

```bash
# Corrida completa (producción)
python main.py run-all

# Un reporte suelto
python main.py run-despacho-bi        # (o run-gd20, run-query, ...)

# ¿Está todo bien? (el único comando de control)
python tools/verificar.py --data C:/Users/ja.guevara/Documents/Archivos
```

## Qué mirar después del run-all (validación de los cambios)

1. Consola sin ALERTAS de CONTROL (si aparece una, dice qué columna y qué %).
2. Los 3 Excel en `Archivos/reports` con su hoja **CONTROL** nueva:
   fecha, filas, hash de contenido y semáforo por columna.
3. La hoja **DATOS** idéntica a siempre (mismas columnas y valores).
4. En BD: `SELECT TOP 10 * FROM pipeline_executions ORDER BY started_at DESC`
   → una fila por pipeline con su hash.
5. Si algo se ve mal: `git status` te dice qué cambió;
   `git checkout -- <archivo>` lo restaura al instante.
