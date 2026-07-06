# Configuración migrada a los slices (Fase 5 — 2026-07-06)

Los YAML de cada reporte ya NO viven acá: cada reporte tiene su carpeta
en `src/itacamba_reportes/reportes/<reporte>/` con `config.yaml`,
`columnas.yaml` (fórmulas declarativas), `manifest.yaml` y README.

| Antes (acá) | Ahora |
|---|---|
| cartera.yaml | `reportes/cartera/config.yaml` |
| query.yaml | `reportes/query/config.yaml` |
| gd20.yaml | `reportes/gd20_ventas_bi/config.yaml` |
| despacho_bi.yaml (+ columnas/) | `reportes/despacho_bi/config.yaml` + `columnas.yaml` |
| despacho_mes.yaml | `reportes/despacho_mes/config.yaml` + `columnas.yaml` |
| references.yaml | `reportes/referencias/config.yaml` |

El código sigue funcionando con las rutas viejas como fallback: el
registro `_SLICE_DE_DATASET` de `config/yaml_loader.py` resuelve la
ubicación real. Esta carpeta queda para configs transversales futuras.
