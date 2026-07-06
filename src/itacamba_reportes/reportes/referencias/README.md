# Catálogos de REFERENCIAS.xlsx → int_ref_*

Los datos de negocio administrables (equipos, gerencias, semanas,
localidades, centros, materiales) viven en `fijos/REFERENCIAS.xlsx` y
se cargan como tablas `int_ref_*`. REGLA DEL PROYECTO: los datos de
negocio se cambian AHÍ (o en el config.yaml del reporte), nunca en
código Python.

| Necesidad | Dónde |
|---|---|
| Agregar/editar filas de un catálogo | `REFERENCIAS.xlsx` (negocio) |
| Hoja/renames/dedupe de un catálogo | `config.yaml` → `catalogs:<key>` |
| Agregar un catálogo nuevo | bloque en `config.yaml` + modelo en `persistence/models/references/` + entrada en `reference_loader.CATALOGS` |
| Orquestación | `pipeline.py` (`build_pipeline()`) |
