"""Reporte QUERY (fase 1 de despachos) — slice vertical.

    config.yaml  source Excel (hoja base, renames de 49 cols), mes objetivo
    mapping.py   descarte de columnas de anotaciones manuales
    reglas.py    macros VBA: ModificarCentro + EliminarMeses
    pipeline.py  extract -> stg_query -> int_query (+ build_pipeline)
"""

from pathlib import Path

SLICE_DIR = Path(__file__).resolve().parent


def load_config() -> dict:
    from itacamba_reportes.config.yaml_loader import _read_yaml
    return _read_yaml(SLICE_DIR / "config.yaml")
