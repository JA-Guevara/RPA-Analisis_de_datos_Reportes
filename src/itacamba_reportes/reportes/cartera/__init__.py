"""Reporte CARTERA (catastro de clientes) — slice vertical.

    config.yaml       spec completa (source, normalize, mapping, lookups,
                      rules, output_contract) — validada con Pydantic
    normalizacion.py  NormalizeCarteraFromSpec (dtypes, renames posicionales)
    reglas.py         donaciones + validacion de regiones
    contrato.py       contrato pandera de salida (int_cartera)
    pipeline.py       extract -> stg -> normalize -> map -> rules ->
                      validate -> int_cartera (+ build_pipeline)
"""

from pathlib import Path

SLICE_DIR = Path(__file__).resolve().parent


def load_config() -> dict:
    from itacamba_reportes.config.yaml_loader import _read_yaml
    return _read_yaml(SLICE_DIR / "config.yaml")
