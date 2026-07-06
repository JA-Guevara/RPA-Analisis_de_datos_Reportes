# Reporte QUERY (fase 1 de despachos)

Ingesta del QUERY*.xlsx de SAP BI: copia fiel a `stg_query` y capa
tipada/filtrada `int_query` (mes objetivo). Es el insumo de
`despacho_bi` (int) y de la resolución CD/ZE de `gd20_ventas_bi` (stg).

| Necesidad | Archivo |
|---|---|
| Archivo/hoja/renames de las 49 cols | `config.yaml` → `source` |
| Mes objetivo (auto/current/explícito) | `config.yaml` → `mes_objetivo` |
| Macro ModificarCentro ('#'→0) | `reglas.py` → `QueryNormalizeUseCase` |
| Macro EliminarMeses (filtro mes) | `reglas.py` → `QueryBusinessRulesUseCase` |
| Descarte de columnas de anotaciones | `mapping.py` |
| Orquestación | `pipeline.py` (`build_pipeline()`) |
| Modelos SQL | `persistence/models/stg/stg_query_model.py` + `models/int/query_model.py` |

Pendiente (Fase 6): columnas fantasma del layout viejo en ambos modelos
(rama `fase6-limpieza-bd`) y decisión de negocio sobre `BOB`/`cu` que
hoy se descartan.
