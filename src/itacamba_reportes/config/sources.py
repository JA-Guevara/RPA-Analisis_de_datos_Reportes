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


def load_excel_source(configs_dir: Path, dataset: str) -> ExcelSource:
    cfg = load_pipeline_config(configs_dir, dataset)
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
