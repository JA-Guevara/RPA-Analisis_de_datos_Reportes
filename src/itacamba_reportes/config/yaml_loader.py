"""Carga de configuración YAML — un solo punto de entrada.

Dos niveles de validación, según lo que el código consume:

- `YamlDatasetLoader.load(dataset)`: valida el YAML completo contra
  `DatasetSpec` (Pydantic). Hoy lo usa cartera, cuyo pipeline es
  100% spec-driven.
- `load_pipeline_config(dir, name)`: devuelve el dict del YAML para
  pipelines cuyos transforms leen claves libres (query, gd20,
  despachos, references). La sección `source:` — la única que el
  framework consume — se valida con `SourceSpec` si está presente.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

import yaml

from itacamba_reportes.config.dataset_spec import DatasetSpec, SourceSpec

logger = logging.getLogger(__name__)

_VAR_PATTERN = re.compile(r"\$\{(\w+)\}")


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config no encontrada: {path}")
    text = _expand_env_vars(path.read_text(encoding="utf-8"))
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"YAML '{path.name}' debe ser dict en top-level")
    return data


def _expand_env_vars(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        return os.environ.get(match.group(1), match.group(0))

    return _VAR_PATTERN.sub(replace, text)


class YamlDatasetLoader:
    """Valida el YAML completo contra DatasetSpec (pipelines spec-driven)."""

    def __init__(self, configs_dir: Path) -> None:
        self._configs_dir = Path(configs_dir)

    def load(self, dataset: str) -> DatasetSpec:
        path = self._configs_dir / f"{dataset}.yaml"
        data = _read_yaml(path)
        data.setdefault("dataset", dataset)
        try:
            spec = DatasetSpec.model_validate(data)
        except Exception as exc:
            raise ValueError(f"Config invalida en '{path}': {exc}") from exc
        logger.info("dataset='%s' cargado desde %s", spec.dataset, path.name)
        return spec


def load_pipeline_config(configs_dir: Path, name: str) -> dict[str, Any]:
    """Dict del YAML del pipeline, con `source:` validado si existe."""
    path = Path(configs_dir) / f"{name}.yaml"
    data = _read_yaml(path)
    if "source" in data and data["source"] is not None:
        try:
            SourceSpec.model_validate(data["source"])
        except Exception as exc:
            raise ValueError(f"Sección source invalida en '{path}': {exc}") from exc
    logger.info("Pipeline config '%s' cargado desde %s", name, path.name)
    return data


_CATALOG_OPS: frozenset[str] = frozenset(
    {"copy", "const", "concat", "lookup", "branch"},
)


def load_column_catalog(configs_dir: Path, name: str) -> dict[str, Any]:
    """Catálogo de columnas en configs_dir/columnas/<name>.yaml (legacy)."""
    return load_column_catalog_file(Path(configs_dir) / "columnas" / f"{name}.yaml")


def load_column_catalog_file(path: Path) -> dict[str, Any]:
    """Catálogo de columnas de un reporte (ruta directa al YAML).

    Valida la forma mínima (bloque `columns` con `op` conocida en cada
    bloque) para fallar en el arranque, no a mitad del pipeline.
    Las columnas se ejecutan en el orden declarado (ver ColumnEngine).
    """
    path = Path(path)
    data = _read_yaml(path)
    columns = data.get("columns")
    if not isinstance(columns, dict) or not columns:
        raise ValueError(f"Catálogo '{path}' sin bloque 'columns' válido")
    for col, spec in columns.items():
        if not isinstance(spec, dict) or spec.get("op") not in _CATALOG_OPS:
            raise ValueError(
                f"Catálogo '{path}': columna '{col}' con op inválida "
                f"{(spec or {}).get('op')!r} (válidas: {sorted(_CATALOG_OPS)})",
            )
    logger.info(
        "Catálogo de columnas cargado desde %s (%d columnas)",
        path.name, len(columns),
    )
    return data
