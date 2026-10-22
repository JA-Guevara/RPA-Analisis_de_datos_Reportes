# Bot - Itacamba_Reportes

Bot que reemplaza el proceso manual del `basepanel.xlsm`: lee los Excel que se descargan de SAP o que entrega el área, los limpia, calcula las columnas y genera los reportes VENTAS BI, DESPACHO BI y DESPACHO MES en SQL Server y en Excel.

## Mapa general

| Excel que entra | Módulo | Tablas que escribe | Lo usan |
|---|---|---|---|
| REFERENCIAS.xlsx (área) | `referencias/` | `int_ref_almacen`, `int_ref_centro`, `int_ref_equipo`, `int_ref_material`, `int_ref_localidad`, `int_ref_semana` | gd20, despacho_bi, despacho_mes |
| CARTERA*.xlsx (correo automático) | `cartera/` | `stg_cartera`, `int_cartera` | gd20, despacho_bi, despacho_mes |
| GD20*.xlsx (SAP GD20) | `gd20/` | `stg_gd20`, `int_gd20` | ventas_bi |
| QUERY*.xlsx (SAP ZBCS) | `query/` | `stg_query`, `int_query` | gd20 (centro y zona), despacho_bi |
| PROYECCION-SEMANAL.xlsx (área) | `proyeccion/` | pendiente | despacho_mes |

| Reporte que sale | Módulo | Combina | Tabla | Excel exportado |
|---|---|---|---|---|
| VENTAS BI | `ventas_bi/` | `int_gd20` + histórico | `int_ventas_bi` | `VENTAS_BI_<fecha>.xlsx` |
| DESPACHO BI | `despacho_bi/` | `int_query` + referencias + cartera | `int_despacho_bi` | `DESPACHO_BI_<fecha>.xlsx` |
| DESPACHO MES | `despacho_mes/` | `int_despacho_bi` (+ proyección, pendiente) | `int_despacho_mes` | `DESPACHO_MES_<fecha>.xlsx` |

## Proceso

| Nivel | Qué es | Periodo | En el Excel | En el bot |
|---|---|---|---|---|
| Crudo | Excel tal como sale de SAP o del área | Lo que traiga la descarga | Archivos de `archivos\` | Tablas `stg_*` |
| Compuesto del mes | Crudo + columnas calculadas con REFERENCIAS y CARTERA | Solo el mes en curso, hasta ayer | Hojas BASE PANEL (GD20) y QUERY | `int_gd20`, `int_query` |
| BI | Compuesto del mes acumulado con el histórico | Todos los meses | VENTAS BI = HISTORIAL VENTAS (hoja VENTAS) + BASE PANEL; DESPACHOS BI = HISTORIAL VENTAS (hoja DESPACHOS) + QUERY | `int_ventas_bi`, `int_despacho_bi` |
| Resumen del mes | Despacho real hasta ayer + proyección desde hoy | Solo el mes en curso | DESPACHO_MES = QUERY + RF AJUSTADO SEMANAL | `int_despacho_mes` |

En resumen: **VENTAS BI es el GD20 compuesto de cada día acumulado con su histórico**, y **DESPACHO BI es la QUERY compuesta acumulada con su histórico**. Al cerrar el mes, el compuesto del mes pasa al histórico y el siguiente mes empieza vacío.

Estado actual del bot frente a ese proceso:

| Reporte | Acumula histórico | Detalle |
|---|---|---|
| VENTAS BI | Sí | `int_ventas_bi` guarda todas las versiones por documento (ver `ventas_bi/README.md`) |
| DESPACHO BI | **No** | `int_despacho_bi` se reemplaza completo en cada corrida con el mes de `int_query`: hoy es solo el mes, no el histórico |
| Histórico anterior | No cargado | HISTORIAL VENTAS.xlsx (hojas VENTAS y DESPACHOS) todavía no se carga a la BD |

## Documentos de Arquitectura y Flujo

- **`DECISIONES_ARQUITECTURA_ELT.md`**: Registro exhaustivo de decisiones (ADRs), diagramas del flujo ELT, justificación técnica del enfoque *Database-First*, purga de emuladores en RAM y traducción de macros VBA a SQL nativo.
- **`FLUJO.md`**: Paso a paso del Excel y del bot hasta VENTAS BI y DESPACHO BI, puntos de control para calibrar y qué falta para coincidir al 100 %.

## Estructura oficial (Database-First ELT & Vertical Slicing)

```
main.py                         entrada: python main.py <comando>
src/itacamba_reportes/
  core/                         motor compartido (agnóstico al negocio): db, io, audit, settings
  inputs/                       vertical slices de entrada (un módulo por cada Excel entrante)
    referencias/                catálogos maestros (almacén, centros, equipos, materiales, rutas)
    cartera/                    catastro de clientes y donaciones
    query/                      despachos operativos SAP ZBCS (layout IM de 24 columnas)
    gd20/                       movimientos contables SAP GD20 (BASE PANEL del mes)
    proyeccion/                 metas comerciales PROYECCION-SEMANAL.xlsx (RF y RF ajustado)
  outputs/                      vertical slices de salida (reportes y acumulados BI)
    ventas_bi/                  histórico acumulado multianual de ventas (SCD Tipo 2)
    despacho_bi/                histórico acumulado multianual de despachos
    despacho_mes/               cierre y proyección del mes en curso (Query real + RF ajustado)
  sap/                          módulo RPA para automatización de descargas SAP GUI (selectors, session, actions)
  cli.py                        punto de entrada CLI con comandos run-* y run-all
docs/                           INDEX.md, FLUJO.md, DECISIONES_ARQUITECTURA_ELT.md
tests/                          pruebas automatizadas
alembic/                        migraciones de base de datos
storage/                        logs, estado de corridas y huellas de archivos
```
```

## Arquitectura del Sistema (Database-First ELT)

El flujo operativo se basa en la separación estricta entre ingestión, transformación SQL y consumo:

```
[Archivos Excel Crudos / SAP RPA]
       │
       ▼  (Lectura ultrarrápida Rust Calamine)
[Tablas Staging stg_*]
       │
       ▼  (transform.sql nativo en SQL Server)
[Tablas Intermedias int_*]
       │
       ▼  (Versionado SCD Tipo 2 y Agregaciones)
[Salidas Analíticas int_ventas_bi / int_despacho_bi / int_despacho_mes]
       │
       ├──► Power BI (DirectQuery / Import)
       └──► Exportador Excel con hoja CONTROL
```

Dentro de cada slice de entrada u objetivo (`inputs/` y `outputs/`):
- `ingest.py`: Carga el archivo crudo a tablas `stg_*`.
- `transform.sql`: Consulta T-SQL con la lógica de negocio, cruces y macros.
- `models.py`: Declaración de esquemas DDL SQLAlchemy.
- `pipeline.py`: Orquestador del slice.
- `README.md`: Diccionario de datos y especificación técnica.

## Comandos CLI Disponibles

| Comando | Acción Ejecutada |
|---|---|
| `python main.py run-referencias` | Ingesta de los 6 catálogos a `int_ref_*` |
| `python main.py run-cartera` | Ingesta de cartera y macro `ModificarDonaciones` a `int_cartera` |
| `python main.py run-query` | Ingesta de ZBCS y filtrado del mes a `int_query` |
| `python main.py run-proyeccion` | Ingesta de metas RF ajustado a `stg_proyeccion` |
| `python main.py run-gd20 [--fin-de-mes]` | Ingesta y transformación de GD20 + actualización de `int_ventas_bi` |
| `python main.py run-ventas-bi` | Acumulación SCD Tipo 2 y exportación de `VENTAS_BI_<fecha>.xlsx` |
| `python main.py run-despacho-bi` | Transformación de despachos reales y exportación de `DESPACHO_BI_<fecha>.xlsx` |
| `python main.py run-despacho-mes` | Resumen mensual Real + Proyección y exportación de `DESPACHO_MES_<fecha>.xlsx` |
| `python main.py run-all [--fin-de-mes]` | Ejecución integral secuencial de todos los pipelines |
| `python main.py download-sap -t <tx> ...` | Descarga parametrizada de reportes desde SAP GUI (RPA) |
| `python main.py init-db` | Verificación de conexión DDL e inicialización de esquemas en SQL Server |

## Convenciones

- Código en inglés (carpetas, archivos, clases, funciones).
- Datos de negocio en español, igual que en SAP y en el Excel: nombres de tablas, columnas, claves de configuración y hojas.
- Sin docstrings ni comentarios en los `.py`. Si algo necesita explicación, va al `README.md` del módulo.
- Datos que cambia el área (listas, asignaciones, ajustes) van en REFERENCIAS.xlsx o como constantes en MAYÚSCULAS al inicio del `transform.py` del reporte.
- Configuración en Python, no en YAML: si un valor está mal escrito, el bot falla al arrancar con el nombre exacto.
- `ruff check .` y `ruff format .` antes de guardar cambios (configuración en `ruff.toml`).
- `python -m pytest -q` debe pasar antes de usar una versión en producción.

## Nombres en código vs tablas

| Clase | Tabla |
|---|---|
| `ChannelRefModel` | `int_ref_almacen` |
| `CenterRefModel` | `int_ref_centro` |
| `SalesTeamRefModel` | `int_ref_equipo` |
| `LocalityRefModel` | `int_ref_localidad` |
| `MaterialRefModel` | `int_ref_material` |
| `WeekRefModel` | `int_ref_semana` |
| `CustomerStgModel` / `CustomerIntModel` | `stg_cartera` / `int_cartera` |
| `Gd20StgModel` / `Gd20IntModel` | `stg_gd20` / `int_gd20` |
| `QueryStgModel` / `QueryIntModel` | `stg_query` / `int_query` |
| `SalesBiIntModel` | `int_ventas_bi` |
| `DispatchBiIntModel` | `int_despacho_bi` |
| `DispatchMonthIntModel` | `int_despacho_mes` |
| `PipelineExecutionModel` | `pipeline_executions` |

## Instalación

1. Python 3.12 y ODBC Driver 17 for SQL Server.
2. Crear el entorno virtual **fuera de OneDrive**: `python -m venv C:\venvs\itacamba_reportes`.
3. `pip install -r requirements.txt` y, para desarrollo, `pip install pytest ruff`.
4. Copiar `.env` con `DATABASE_URL` (o `DB_*`), `DATA_PATH` y `EXPORT_PATH`.
5. `python main.py init-db` para verificar la conexión e inicializar esquemas en la Base de Datos.

## Historial de cambios

| Fecha | Cambio | Motivo |
|---|---|---|
| 22-10-2026 | **Arquitectura Database-First ELT & Vertical Slicing**: Ingesta cruda directa a staging (`stg_*`) y transformaciones/cruces masivos resueltos directamente en la Base de Datos (SQL Server). Purga del emulador de Excel en memoria RAM (`ColumnEngine`, specs y lookups en Python). Soporte de la nueva QUERY (24 cols) e integración de `PROYECCION-SEMANAL.xlsx` mediante unión vertical para `despacho_mes`. Documentado en `docs/DECISIONES_ARQUITECTURA_ELT.md`. | Rendimiento masivo, eliminar cuello de botella de red/RAM y garantizar mantenibilidad |
| 22-10-2026 | Arquitectura limpia: `domain/` (fichas, puertos, cruces), `application/` (un pipeline genérico en lugar de 6), `reports/` (`definition.py` + `transform.py` + `contracts.py` por reporte), `infrastructure/` (SQL Server, Excel, estado, modo local), `interfaces/` (cli). Nuevo `--sin-bd` y `tools/calibrate_gd20.py`. Mismos resultados (comparación sobre octubre-2026: todas las tablas, controles y DDL idénticos; única diferencia, la opción nueva `--sin-bd`). | Escalar y mantener |
| 22-10-2026 | Estructura por capas: un módulo por Excel en la raíz de `src/itacamba_reportes/` con `source.py` + `calculations.py` + `pipeline.py`; todo lo de la BD en `persistence/`; herramientas en `shared/` (desaparecen `core/`, `inputs/`, `outputs/`). Reglas de dependencias verificadas por pruebas. Corregido `tools/check_db_connection.py`, que fallaba al importar desde la v2. Misma salida (25 de 25 elementos idénticos sobre octubre-2026). | Todo lo del Excel en una carpeta y lo de la BD en otra |
| 22-10-2026 | Configuración de YAML a Python: 9 archivos `.yaml` → `config.py` + `columns.py` por módulo, con los mismos valores (48 valores de configuración y 44 columnas comparados uno a uno) y la misma salida (25 de 25 elementos idénticos sobre octubre-2026). Se quitan PyYAML y Pydantic. Pruebas nuevas: motor de columnas, cruces apuntan a tablas/columnas reales, tablas de columnas de los README al día. | Errores detectados al arrancar, autocompletado, una sola fuente por valor |
| 22-10-2026 | Reestructuración v2: módulos por Excel (`inputs/`) y por reporte (`outputs/`), motor en `core/`, nombres en inglés, sin docstrings ni comentarios, README por módulo. Mismos resultados que la versión anterior (prueba de equivalencia sobre octubre-2026: 24 de 24 elementos idénticos). | Orden y mantenimiento |
| 22-10-2026 | Carpetas de módulos en español: `referencias`, `cartera`, `gd20`, `query`, `proyeccion`, `ventas_bi`, `despacho_bi`, `despacho_mes`. | Acordado con el equipo |
| 22-10-2026 | `cli.main()` completado: ahora devuelve código 1 cuando un pipeline falla (antes devolvía 0) e imprime el resumen final. | Bug: el fallo no llegaba al programador de tareas |
| 22-10-2026 | Eliminado código sin uso: `NombreDestQueryRule` (apagada por configuración), `_rule_codigo_cliente_zero_fill` (no se llamaba), `manifest.py` y los `manifest.yaml`, `load_all_excel_sources`, `load_column_catalog`, `get_lookup`. | Limpieza |
| 22-10-2026 | `requirements.txt` con las dependencias reales del proyecto. | El anterior listaba paquetes de otro proyecto |
