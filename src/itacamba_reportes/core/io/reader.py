from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

import pandas as pd

logger = logging.getLogger(__name__)

NULL_TOKENS = frozenset({"", "#", "N/A", "NA", "nan", "NaN", "None", "null", "NULL", "00000000"})


def coerce_numeric_series(
    series: pd.Series,
    col_name: str,
    *,
    context: str = "",
    as_int: bool = False,
    fill_zero: bool = True,
) -> pd.Series:
    parsed = pd.to_numeric(series, errors="coerce")
    invalid_mask = series.notna() & parsed.isna()
    if invalid_mask.any():
        raw_bad = series[invalid_mask].astype(str).str.strip()
        real_bad = raw_bad[~raw_bad.isin(NULL_TOKENS)]
        if not real_bad.empty:
            samples = real_bad.unique()[:5].tolist()
            prefix = f"[{context}] " if context else ""
            logger.warning(
                "%sColumna '%s': %d valor(es) no numérico(s) convertido(s) a %s (ejemplos: %s)",
                prefix,
                col_name,
                len(real_bad),
                "0" if fill_zero else "NULL",
                samples,
            )
    if fill_zero:
        parsed = parsed.fillna(0)
        return parsed.astype("int64") if as_int else parsed.astype(float)
    return parsed


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
        candidates_dirs: list[Path] = []
        if self.spec.subdir:
            sub_dir = self.base_path / self.spec.subdir
            if sub_dir.exists() and self.base_path.name.lower() != self.spec.subdir.lower():
                candidates_dirs.append(sub_dir)
        candidates_dirs.append(self.base_path)

        for search_dir in candidates_dirs:
            matches = sorted(search_dir.glob(self.spec.file_pattern)) if search_dir.exists() else []
            if matches:
                return max(matches, key=lambda p: p.stat().st_mtime)

        if self.base_path.exists():
            matches = sorted(self.base_path.glob(f"**/{self.spec.file_pattern}"))
            if matches:
                return max(matches, key=lambda p: p.stat().st_mtime)

        raise FileNotFoundError(
            f"No se encontró archivo '{self.spec.file_pattern}' en {self.base_path}"
        )

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

        # Paso 1: Lectura directa de una sola pasada (inspeccionar hojas solo si falla)
        df = None
        last_exc: Exception | None = None
        for engine in ("calamine", "openpyxl"):
            try:
                df = pd.read_excel(
                    path,
                    sheet_name=self.spec.sheet,
                    header=self.spec.header_row,
                    engine=engine,
                )
                break
            except Exception as exc:
                last_exc = exc
                continue

        if df is None:
            if isinstance(self.spec.sheet, str):
                sheet_names = self.get_sheet_names(path)
                if sheet_names and self.spec.sheet not in sheet_names:
                    raise SheetNotFoundError(
                        f"La hoja requerida '{self.spec.sheet}' no existe en el archivo '{path.name}'. "
                        f"Hojas encontradas en el libro: {sheet_names}"
                    )
            raise ValueError(f"No se pudo leer la hoja '{self.spec.sheet}' del archivo Excel {path.name}: {last_exc}")

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
