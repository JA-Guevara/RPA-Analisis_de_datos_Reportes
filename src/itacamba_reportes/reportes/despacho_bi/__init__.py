"""Reporte DESPACHO BI — slice vertical.

Todo lo que define este reporte vive en esta carpeta:
    config.yaml    parametros del pipeline (source_columns, notas)
    columnas.yaml  formulas del cliente (catalogo, ejecuta ColumnEngine)
    manifest.yaml  portada tecnica (entrada/salidas/dependencias)
    mapping.py     subset de columnas heredadas de int_query
    pipeline.py    orquestacion + build_pipeline()

Modelos SQL: centralizados en persistence/models/int/despacho_bi_model
(registro unico de metadata para Alembic).
"""

from pathlib import Path

SLICE_DIR = Path(__file__).resolve().parent


def load_config() -> dict:
    from itacamba_reportes.config.yaml_loader import _read_yaml
    return _read_yaml(SLICE_DIR / "config.yaml")


def load_catalog() -> dict:
    from itacamba_reportes.config.yaml_loader import load_column_catalog_file
    return load_column_catalog_file(SLICE_DIR / "columnas.yaml")
