# config

Configuración del runtime: variables de entorno, rutas y carga de YAMLs.
(Actualizado 2026-07-06 — la versión anterior describía una arquitectura
que ya no existe: pydantic-settings, data_sources.py, domain/constants.)

## Qué hay aquí (real)

- `env_config.py` — `EnvConfig`: lee `.env` con python-dotenv y expone
  `DB_*`, `DATA_PATH`, `EXPORT_PATH`, `LOG_*`. Validaciones en
  `validate_config()` / `validate_db_config()` / `validate_data_paths()`.
- `paths.py` — `DataPaths.from_env()`: inbox/processed/archive/exports.
- `sources.py` — construye `ExcelSource` desde los YAML de
  `assets/configs/` (`load_all_excel_sources`, `load_reference_sources`,
  `excel_source_from_cfg`). Única fuente de verdad de QUÉ archivo/hoja/
  renames lee cada dataset.
- `yaml_loader.py` — `YamlDatasetLoader` (spec Pydantic completa, hoy
  solo cartera), `load_pipeline_config` (dict libre validando `source:`)
  y `load_column_catalog` (catálogos de columnas de
  `assets/configs/columnas/`, ejecutados por el ColumnEngine).
- `dataset_spec.py` — modelos Pydantic de la spec de cartera
  (source, normalize, mapping, lookups, rules).

## Qué NO va aquí

- Datos de negocio: van en `Referencias.xlsx` → tablas `int_ref_*`, o en
  los YAML de `assets/configs/` (regla del proyecto).
- Lógica de transformación: vive en `transforms/`.
