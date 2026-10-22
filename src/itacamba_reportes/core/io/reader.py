from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

import pandas as pd

logger = logging.getLogger(__name__)

NULL_TOKENS = frozenset({"", "#", "N/A", "NA", "nan", "NaN", "None", "null", "NULL", "00000000"})


@dataclass(frozen=True, slots=True)
class ExcelSourceSpec:
    name: str
    file_pattern: str
    sheet: str | int = 0
    header_row: int = 0
    subdir: str | None = None
    column_renames: Mapping[str, str] = field(default_factory=dict)
    dedupe_keys: tuple[str, ...] = field(default_factory=tuple)
    required_columns: tuple[str, ...] = field(default_factory=tuple)


class FastExcelReader:
    def __init__(self, spec: ExcelSourceSpec, base_path: Path):
        self.spec = spec
        self.base_path = Path(base_path)

    def resolve_path(self) -> Path:
        search_dir = self.base_path
        if self.spec.subdir:
            search_dir = search_dir / self.spec.subdir

        matches = sorted(search_dir.glob(self.spec.file_pattern)) if search_dir.exists() else []

        if not matches and self.base_path.exists():
            matches = sorted(self.base_path.glob(f"**/{self.spec.file_pattern}"))

        if not matches:
            raise FileNotFoundError(
                f"No se encontró archivo '{self.spec.file_pattern}' en {search_dir} ni en {self.base_path}"
            )
        return max(matches, key=lambda p: p.stat().st_mtime)

    def read_raw(self) -> pd.DataFrame:
        path = self.resolve_path()
        logger.info("Leyendo Excel crudo %s (hoja=%s, fila=%d)", path.name, self.spec.sheet, self.spec.header_row)

        df = None
        for engine in ("calamine", "openpyxl"):
            for sheet in (self.spec.sheet, 0):
                try:
                    df = pd.read_excel(
                        path,
                        sheet_name=sheet,
                        header=self.spec.header_row,
                        engine=engine,
                    )
                    break
                except Exception:
                    continue
            if df is not None:
                break

        if df is None:
            raise ValueError(f"No se pudo leer el archivo Excel {path.name}")

        if self.spec.column_renames:
            df.columns = [str(c).strip() for c in df.columns]
            df = df.rename(columns=dict(self.spec.column_renames))

        df = df.dropna(how="all")

        if self.spec.dedupe_keys:
            valid_keys = [k for k in self.spec.dedupe_keys if k in df.columns]
            if valid_keys:
                df = df.drop_duplicates(subset=valid_keys, keep="first")

        logger.info("%s leido: %d filas x %d columnas", self.spec.name, len(df), len(df.columns))
        return df
