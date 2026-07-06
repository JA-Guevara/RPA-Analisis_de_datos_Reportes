"""Reporte DESPACHO MES — slice vertical.

    config.yaml    parametros (mes_objetivo, group_by, reglas VBA)
    columnas.yaml  los 5 VLOOKUP vivos de la hoja (catalogo ColumnEngine)
    manifest.yaml  portada tecnica
    agregacion.py  GROUP BY + SUM (detalle -> 1 fila por combinacion)
    reglas.py      macros VBA portadas (EliminarFilasDespacho,
                   EliminarRFajustado)
    pipeline.py    orquestacion + build_pipeline()

Modelos SQL centralizados en persistence/models/int/despacho_mes_model.
"""

from pathlib import Path

SLICE_DIR = Path(__file__).resolve().parent


def load_config() -> dict:
    from itacamba_reportes.config.yaml_loader import _read_yaml
    return _read_yaml(SLICE_DIR / "config.yaml")


def load_catalog() -> dict:
    from itacamba_reportes.config.yaml_loader import load_column_catalog_file
    return load_column_catalog_file(SLICE_DIR / "columnas.yaml")
