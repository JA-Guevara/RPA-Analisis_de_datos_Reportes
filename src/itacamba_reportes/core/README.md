# Core de Infraestructura y Utilidades

Capa de servicios fundamentales compartidos por todos los slices, agnóstica a la lógica particular del negocio de cemento.

## Componentes

### 1. `db/` - Base de Datos
- `base.py`: Clase base declarativa SQLAlchemy (`DeclarativeBase`) y mixin `TimestampsMixin` (`created_at`, `updated_at`).
- `connection.py`: Factoría de conexiones. Conecta a SQL Server (`Reportes_Itacamba`) si hay red/VPN activa, o realiza un fallback automático a SQLite local (`storage/db/local.db`) para entornos offline.
- `bulk.py`: Inserción masiva de alto rendimiento (`bulk_insert_df`). Utiliza chunks de 10.000 filas y soporte de truncado atómico previo (`TRUNCATE` en SQL Server / `DELETE` en SQLite).
- `schema.py`: Función `init_db()` que registra e inicializa todos los modelos DDL de Staging, Tablas Intermedias e Históricos.

### 2. `io/` - Lectura y Exportación
- `reader.py`: `FastExcelReader` basado en la biblioteca en Rust `calamine` para lectura ultrarrápida de archivos Excel pesados, con fallback a `openpyxl`. Resuelve hojas de trabajo numéricas o por nombre, y gestiona alias de columnas.
- `exporter.py`: `ExcelReportExporter` para volcar dataframes procesados a archivos `.xlsx` bajo `storage/exports/`, generando la hoja de datos principal `DATOS` y una hoja de auditoría `CONTROL`.

### 3. `audit/` - Auditoría y Versionado
- `hashing.py`: Generador de hashes criptográficos SHA-256 (`compute_row_hash`, `add_hashes_to_df`). Separa hashes de columnas origen (`source_hash`) y derivadas (`derived_hash`) para el versionado SCD Tipo 2.
- `tracker.py`: Registrador de ejecuciones en la tabla `pipeline_executions`, guardando estado (`SUCCESS`/`FAILED`), filas procesadas y duración en segundos.

### 4. `settings.py` - Configuración del Entorno
- Detecta automáticamente rutas del proyecto en OneDrive (`Documentos ITACAMBA` / `Documentos/Archivos`) o variables `.env`.
