"""Carga y validación de manifest.yaml por reporte.

El manifest es la "portada técnica" de cada slice. Este validador
garantiza que NO se vuelva documentación que miente (la lección de las
claves doc-only de la auditoría 2026-07-06): cada afirmación
verificable del manifest se contrasta contra la realidad del código.

Verifica, por reporte:
  - claves mínimas presentes (reporte, entrada, salidas)
  - coherencia entrada ↔ config.yaml:source (archivo/hoja/header_row)
  - que toda tabla declarada en salidas/dependencias exista en la
    metadata SQLAlchemy (modelos reales)
  - que la llave_natural sean columnas reales de la tabla int de salida

Lo consume tools/verificar.py (gate único del proyecto).
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import Any

import yaml


def load_manifest(slice_dir: Path) -> dict[str, Any]:
    path = Path(slice_dir) / "manifest.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Manifest no encontrado: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Manifest inválido (no es dict): {path}")
    return data


def _cargar_metadata():
    """Importa todos los módulos de modelos y devuelve Base.metadata."""
    import itacamba_reportes.persistence.models as raiz
    from itacamba_reportes.persistence.base import Base

    for mod in pkgutil.walk_packages(raiz.__path__, raiz.__name__ + "."):
        importlib.import_module(mod.name)
    return Base.metadata


def _tablas_declaradas(manifest: dict[str, Any]) -> list[str]:
    tablas: list[str] = []
    salidas = manifest.get("salidas") or {}
    for v in salidas.values():
        if isinstance(v, str) and v.startswith(("stg_", "int_")):
            tablas.append(v)
        if isinstance(v, list):
            tablas += [x for x in v if isinstance(x, str)
                       and x.startswith(("stg_", "int_"))]
    for d in manifest.get("dependencias") or []:
        if isinstance(d, str) and d.startswith(("stg_", "int_")):
            tablas.append(d)
    return tablas


def validate_manifest(slice_dir: Path) -> list[str]:
    """Lista de problemas (vacía = manifest coherente con el código)."""
    problemas: list[str] = []
    slice_dir = Path(slice_dir)
    m = load_manifest(slice_dir)
    nombre = m.get("reporte", slice_dir.name)

    for clave in ("reporte", "entrada", "salidas"):
        if clave not in m:
            problemas.append(f"[{nombre}] falta clave '{clave}'")

    # entrada ↔ config.source
    entrada = m.get("entrada") or {}
    cfg_path = slice_dir / "config.yaml"
    if entrada.get("tipo") == "excel" and cfg_path.exists():
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        src = cfg.get("source") or {}
        pares = [("archivo", "file_pattern"), ("carpeta", "subdir"),
                 ("hoja", "sheet"), ("header_row", "header_row")]
        for k_man, k_src in pares:
            if k_man in entrada and k_src in src and \
                    str(entrada[k_man]) != str(src[k_src]):
                problemas.append(
                    f"[{nombre}] entrada.{k_man}={entrada[k_man]!r} != "
                    f"config source.{k_src}={src[k_src]!r}")

    # tablas declaradas existen en la metadata real
    metadata = _cargar_metadata()
    for tabla in _tablas_declaradas(m):
        if tabla not in metadata.tables:
            problemas.append(
                f"[{nombre}] tabla declarada '{tabla}' no existe en los "
                f"modelos SQLAlchemy")

    # llave_natural ⊆ columnas de la tabla int de salida
    salida_int = (m.get("salidas") or {}).get("int")
    llave = m.get("llave_natural") or []
    if salida_int and salida_int in metadata.tables and llave:
        cols = {c.name for c in metadata.tables[salida_int].columns}
        for k in llave:
            if k not in cols:
                problemas.append(
                    f"[{nombre}] llave_natural '{k}' no es columna "
                    f"de {salida_int}")
    return problemas


def validate_all(reportes_dir: Path) -> dict[str, list[str]]:
    """Valida todos los slices que tengan manifest.yaml."""
    out: dict[str, list[str]] = {}
    for d in sorted(Path(reportes_dir).iterdir()):
        if d.is_dir() and (d / "manifest.yaml").exists():
            out[d.name] = validate_manifest(d)
    return out
