# Reporte CARTERA (catastro de clientes)

Catastro SAP de clientes. Único pipeline 100% spec-driven: TODA su
configuración (dtypes, renames posicionales, transforms, lookups de
donaciones/regiones, contrato de salida) vive en `config.yaml` validado
con Pydantic (`config/dataset_spec.py`).

| Necesidad | Archivo |
|---|---|
| Cualquier regla de columnas/dtypes/renames | `config.yaml` |
| Regla de donaciones / validación regiones | `reglas.py` (mecanismo; datos en config.yaml) |
| Normalización desde spec | `normalizacion.py` |
| Contrato pandera de salida | `contrato.py` (referenciado por `output_contract` en config.yaml — import dinámico) |
| Orquestación | `pipeline.py` (`build_pipeline()`) |

OJO: `output_contract` en config.yaml importa `contrato.py` POR RUTA
STRING — si movés/renombrás el módulo, actualizá esa clave (no lo
detecta ningún grep de imports).
