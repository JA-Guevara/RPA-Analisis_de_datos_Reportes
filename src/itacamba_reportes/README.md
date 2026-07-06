# itacamba_reportes

Paquete principal del ETL de reportes (VENTAS BI, DESPACHOS BI, DESPACHO MES).
Organizado por responsabilidad técnica real — capas que el dato atraviesa:

```
itacamba_reportes/
├── cli.py           ← entrypoint + composition root (registry de pipelines)
├── config/          ← env, paths, specs Pydantic, loader YAML, sources Excel
├── contracts/       ← schemas Pandera de validación de salida
├── ingestion/       ← ExcelReader + ExcelSource (lectura configurable)
├── pipelines/       ← orquestación: runner común (change-detection) + 1 módulo
│                      por pipeline + run_all (DAG secuencial fail-fast)
├── transforms/      ← normalize / business_rules / mapping por dataset
│                      + column_engine (ejecuta catálogos declarativos de
│                      assets/configs/columnas/ — las fórmulas del cliente
│                      calibradas viven como YAML, no como código)
├── persistence/     ← engine, session, models/, repositorios SQL, export,
│                      SCD2 de int_ventas_bi, execution tracker
└── shared/          ← utilidades transversales (pandas, null tokens, logging)
```

## Flujo (DAG)

```
references ─┐
cartera ────┼──► gd20 ──► UPSERT SCD2 int_ventas_bi   (REPORTE VENTAS BI)
query ──────┼──► despacho_bi ──► despacho_mes          (REPORTE DESPACHOS)
```

## Convenciones

- **Los datos fluyen como DataFrames** de punta a punta; STG persiste el raw,
  INT persiste el resultado transformado.
- **Configuración en YAML** (`assets/configs/*.yaml`): fuentes Excel (hoja,
  header, renames, dedupe), renames STG→INT, lookups y reglas. Los datos de
  negocio NO van hardcodeados en Python.
- **Agregar un catálogo de referencia**: 1 modelo en `persistence/models/references/`
  + 1 entrada en `references.yaml:catalogs` + 1 línea en
  `persistence/repositories/reference_loader.py:CATALOGS`.
- **Agregar un pipeline**: 1 módulo en `pipelines/` (solo stages; el ciclo
  fingerprint/skip/state lo da `pipelines/runner.py`) + 1 builder y 1 entry
  en `cli.py:PIPELINES`.
- **Una abstracción se gana su lugar con 2+ implementaciones reales o
  eliminando duplicación existente. Nunca "por si acaso".**

## Tests

- `tests/characterization/`: red de seguridad del refactor — goldens del
  comportamiento de transforms, mappings, limpieza de referencias, config y
  state. Correr `pytest tests/characterization/` tras CUALQUIER cambio en
  esas piezas. Si un cambio de comportamiento es INTENCIONAL, regenerar con
  `python tests/characterization/capture_goldens.py --write` y revisar el diff.
