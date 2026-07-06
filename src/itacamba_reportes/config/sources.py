"""Construcción de ExcelSource desde los YAML de assets/configs.

Única fuente de verdad de QUÉ archivo/hoja/renames lee cada dataset:
- cartera.yaml / query.yaml / gd20.yaml → sección `source:`
- references.yaml → `source:` común + un `catalogs:<key>` por catálogo
"""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType

from itacamba_reportes.config.yaml_loader import load_pipeline_config
from itacamba_reportes.ingestion.excel_source import ExcelSource


def excel_source_from_cfg(name: str, cfg: dict) -> ExcelSource:
    return ExcelSource(
        name=name,
        file_pattern=cfg["file_pattern"],
        subdir=cfg.get("subdir"),
        sheet=cfg.get("sheet", 0),
        header_row=int(cfg.get("header_row", 0)),
        metadata_rows_to_skip=int(cfg.get("metadata_rows_to_skip", 0)),
        column_renames=MappingProxyType(dict(cfg.get("column_renames") or {})),
        dedupe_on=tuple(cfg.get("dedupe_on") or ()),
        dedupe_case_insensitive=bool(cfg.get("dedupe_case_insensitive", False)),
    )


# Datasets cuya config vive en su slice (reportes/<slice>/config.yaml).
# Al migrar un reporte al patron por-carpeta, agregarlo aca.
_SLICE_DE_DATASET: dict[str, str] = {
    "gd20": "gd20_ventas_bi",
    "despacho_bi": "despacho_bi",
    "despacho_mes": "despacho_mes",
}


def _load_dataset_config(configs_dir: Path, dataset: str) -> dict:
    """Config del dataset: slice si esta migrado, assets/configs si no."""
    slice_name = _SLICE_DE_DATASET.get(dataset)
    if slice_name is not None:
        slice_cfg = (Path(__file__).resolve().parents[1]
                     / "reportes" / slice_name / "config.yaml")
        if slice_cfg.exists():
            from itacamba_reportes.config.yaml_loader import _read_yaml
            return _read_yaml(slice_cfg)
    return load_pipeline_config(configs_dir, dataset)


def load_excel_source(configs_dir: Path, dataset: str) -> ExcelSource:
    cfg = _load_dataset_config(configs_dir, dataset)
    source = cfg.get("source")
    if not source:
        raise ValueError(f"config de '{dataset}' no define sección 'source'")
    return excel_source_from_cfg(dataset, source)


def load_reference_sources(configs_dir: Path) -> dict[str, ExcelSource]:
    """Un ExcelSource por catálogo de references.yaml (key → ref_<key>)."""
    cfg = load_pipeline_config(configs_dir, "references")
    catalogs = cfg.get("catalogs") or {}
    if not catalogs:
        raise ValueError("references.yaml no define 'catalogs'")
    return {
        key: excel_source_from_cfg(f"ref_{key}", cat_cfg)
        for key, cat_cfg in catalogs.items()
    }


def load_all_excel_sources(configs_dir: Path) -> dict[str, ExcelSource]:
    """Todos los sources del proyecto, indexados por name (= snapshot)."""
    out: dict[str, ExcelSource] = {}
    for ds in ("cartera", "query", "gd20"):
        out[ds] = load_excel_source(configs_dir, ds)
    for key, src in load_reference_sources(configs_dir).items():
        out[src.name] = src
    return out
