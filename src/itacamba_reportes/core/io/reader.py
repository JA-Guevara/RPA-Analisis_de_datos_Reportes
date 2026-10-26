from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

import pandas as pd

logger = logging.getLogger(__name__)

NULL_TOKENS = frozenset({"", "#", "N/A", "NA", "nan", "NaN", "None", "null", "NULL", "00000000"})


class ExcelReaderError(Exception):
    pass


class SheetNotFoundError(ExcelReaderError):
    pass


class MissingColumnsError(ExcelReaderError):
    pass


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

    def get_sheet_names(self, path: Path) -> list[str]:
        try:
            import python_calamine
            wb = python_calamine.CalamineWorkbook.from_path(path)
            return wb.sheet_names
        except Exception:
            try:
                import openpyxl
                wb = openpyxl.load_workbook(path, read_only=True)
                return wb.sheetnames
            except Exception:
                return []

    def read_raw(self) -> pd.DataFrame:
        path = self.resolve_path()
        logger.info("Leyendo Excel crudo %s (hoja=%s, fila=%d)", path.name, self.spec.sheet, self.spec.header_row)

        # Paso 1: Validacion estricta de existencia de hoja solicitada
        if isinstance(self.spec.sheet, str):
            sheet_names = self.get_sheet_names(path)
            if sheet_names and self.spec.sheet not in sheet_names:
                raise SheetNotFoundError(
                    f"La hoja requerida '{self.spec.sheet}' no existe en el archivo '{path.name}'. "
                    f"Hojas encontradas en el libro: {sheet_names}"
                )

        df = None
        for engine in ("calamine", "openpyxl"):
            try:
                df = pd.read_excel(
                    path,
                    sheet_name=self.spec.sheet,
                    header=self.spec.header_row,
                    engine=engine,
                )
                break
            except Exception:
                continue

        if df is None:
            raise ValueError(f"No se pudo leer la hoja '{self.spec.sheet}' del archivo Excel {path.name}")

        # Paso 2: Normalizacion de nombres de columnas y renombrado
        if self.spec.column_renames:
            df.columns = [str(c).strip() for c in df.columns]
            df = df.rename(columns=dict(self.spec.column_renames))

        # Paso 3: Validacion defensiva de columnas obligatorias
        if self.spec.required_columns:
            missing = [c for c in self.spec.required_columns if c not in df.columns]
            if missing:
                raise MissingColumnsError(
                    f"El archivo '{path.name}' (hoja '{self.spec.sheet}') no contiene las columnas requeridas: {missing}"
                )

        df = df.dropna(how="all")

        # Paso 4: Deduplicacion si aplica
        if self.spec.dedupe_keys:
            valid_keys = [k for k in self.spec.dedupe_keys if k in df.columns]
            if valid_keys:
                df = df.drop_duplicates(subset=valid_keys, keep="first")

        logger.info("%s validado y leido: %d filas x %d columnas", self.spec.name, len(df), len(df.columns))
        return df
