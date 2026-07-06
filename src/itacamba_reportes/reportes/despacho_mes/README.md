# Reporte DESPACHO MES

Agregado mensual de despachos (réplica de la hoja `DESPACHO_MES` del
basepanel): GROUP BY gerencia/equipo/depto/localidad/CD/producto/
incoterms/fecha/cliente + SUM(despacho_t), 5 VLOOKUP vivos y 2 macros
VBA portadas.

## Dónde está cada cosa

| Necesidad | Archivo |
|---|---|
| Los 5 VLOOKUP (nombre_cliente, vendedor, tipo_venta, canal, semana2) | `columnas.yaml` |
| Dimensiones del GROUP BY / mes objetivo / flags de reglas | `config.yaml` |
| Agregación (detalle → 1 fila por combinación) | `agregacion.py` |
| Macros VBA (EliminarFilasDespacho, EliminarRFajustado) | `reglas.py` |
| Orquestación | `pipeline.py` (`build_pipeline()`) |
| Modelo SQL | `persistence/models/int/despacho_mes_model.py` (centralizado) |

## Orden del pipeline

filtro mes → `agregacion.py` → `columnas.yaml` (ColumnEngine) →
`reglas.py` → INT load → export. El orden replica el flujo del Excel.
