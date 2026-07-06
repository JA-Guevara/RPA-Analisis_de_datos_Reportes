from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True, slots=True)
class ExcelSource:

    name: str
    file_pattern: str
    subdir: str | None
    sheet: str
    header_row: int = 0
    metadata_rows_to_skip: int = 0
    column_renames: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
    dedupe_on: tuple[str, ...] = ()
    # Si True, el dedupe normaliza upper+strip antes de drop_duplicates.
    # Necesario cuando la BD destino usa collation case-insensitive
    # (ej: SQL Server Latin1_General_CI_AS), donde "SAN MATIAS" y
    # "San Matias" violan UNIQUE constraint aunque en pandas sean distintos.
    dedupe_case_insensitive: bool = False
