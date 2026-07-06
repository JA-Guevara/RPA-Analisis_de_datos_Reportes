"""Catalogos de REFERENCIAS.xlsx -> tablas int_ref_* — slice vertical.

    config.yaml  un bloque por catalogo (hoja, renames, dedupe, tabla)
    pipeline.py  carga replace-all de los 6 catalogos (+ build_pipeline)

El registro catalogo->modelo (CATALOGS) vive en
persistence/repositories/reference_loader.py.
"""

from pathlib import Path

SLICE_DIR = Path(__file__).resolve().parent


def load_config() -> dict:
    from itacamba_reportes.config.yaml_loader import _read_yaml
    return _read_yaml(SLICE_DIR / "config.yaml")
