"""Reporte GD20 / VENTAS BI — slice vertical.

    config.yaml         source Excel, renames, overrides por centro,
                        constantes de negocio, defaults CD/ZE
    columnas.yaml       lookups/formulas simples (ColumnEngine)
    mapping.py          renames STG -> lenguaje de negocio
    enriquecimiento.py  orquesta catalogo + reglas (orden calibrado)
    reglas.py           CD/ZE 5 capas, overrides, formulas numericas
    pipeline.py         extract -> stg -> enrich -> int_gd20 -> SCD2
                        int_ventas_bi -> export (+ build_pipeline)

Historico SCD2: persistence/repositories/ventas_bi_repository_sql.py
(mecanismo MERGE por hash; las columnas que componen cada hash estan en
persistence/row_hasher.py). Modelos SQL centralizados en
persistence/models/.
"""

from pathlib import Path

SLICE_DIR = Path(__file__).resolve().parent


def load_config() -> dict:
    from itacamba_reportes.config.yaml_loader import _read_yaml
    return _read_yaml(SLICE_DIR / "config.yaml")


def load_catalog() -> dict:
    from itacamba_reportes.config.yaml_loader import load_column_catalog_file
    return load_column_catalog_file(SLICE_DIR / "columnas.yaml")
