from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Mapping

import pandas as pd

logger = logging.getLogger(__name__)

NULL_TOKENS = frozenset({"", "#", "N/A", "NA", "nan", "NaN", "None", "null", "NULL", "00000000"})
EXCEL_EXTENSIONS: tuple[str, ...] = (".xlsx", ".xlsm", ".xlsb", ".xls")


def is_excel_file(path: Path) -> bool:
    return path.is_file() and not path.name.startswith("~$") and path.suffix.lower() in EXCEL_EXTENSIONS


def _expand_excel_patterns(pattern: str) -> tuple[str, ...]:
    low = pattern.lower()
    for ext in EXCEL_EXTENSIONS:
        if low.endswith(ext):
            stem_pat = pattern[: -len(ext)]
            return tuple(f"{stem_pat}{e}" for e in EXCEL_EXTENSIONS)
    if "." not in Path(pattern).name:
        return tuple(f"{pattern}{e}" for e in EXCEL_EXTENSIONS)
    return (pattern,)


def find_matching_excel_files(directory: Path, pattern: str, recursive: bool = False) -> list[Path]:
    if not directory.exists():
        return []
    patterns = _expand_excel_patterns(pattern)
    seen: dict[Path, Path] = {}
    for pat in patterns:
        glob_pat = f"**/{pat}" if recursive else pat
        for candidate in directory.glob(glob_pat):
            if candidate.is_file() and not candidate.name.startswith("~$"):
                seen[candidate.resolve()] = candidate
    ext_rank = {ext: idx for idx, ext in enumerate(EXCEL_EXTENSIONS)}
    return sorted(
        seen.values(),
        key=lambda p: (p.stat().st_mtime, -ext_rank.get(p.suffix.lower(), 99)),
        reverse=True,
    )


class _HtmlTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._in_table = False
        self._in_row = False
        self._in_cell = False
        self._cur_table: list[list[str]] = []
        self._cur_row: list[str] = []
        self._cur_cell: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        if t == "table" and not self._in_table:
            self._in_table = True
            self._cur_table = []
        elif self._in_table and t == "tr":
            self._in_row = True
            self._cur_row = []
        elif self._in_row and t in ("td", "th"):
            self._in_cell = True
            self._cur_cell = []

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cur_cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if self._in_cell and t in ("td", "th"):
            self._cur_row.append("".join(self._cur_cell).strip())
            self._in_cell = False
        elif self._in_row and t == "tr":
            self._cur_table.append(self._cur_row)
            self._in_row = False
        elif self._in_table and t == "table":
            if self._cur_table:
                self.tables.append(self._cur_table)
            self._in_table = False


def _rows_to_dataframe(rows: list[list[str]], header_row: int) -> pd.DataFrame:
    if not rows or header_row >= len(rows):
        return pd.DataFrame()
    width = max(len(r) for r in rows[header_row:])
    norm_rows = [r + [""] * (width - len(r)) for r in rows]
    raw_headers = norm_rows[header_row]
    headers: list[str] = []
    for idx, h in enumerate(raw_headers):
        clean_h = str(h).strip()
        headers.append(clean_h if clean_h else f"Unnamed: {idx}")
    data_rows = norm_rows[header_row + 1 :]
    return pd.DataFrame(data_rows, columns=headers)


def _parse_spreadsheetml(path: Path) -> dict[str, list[list[str]]]:
    tree = ET.parse(path)
    root = tree.getroot()
    sheets: dict[str, list[list[str]]] = {}
    for elem in root.iter():
        if elem.tag.split("}")[-1] != "Worksheet":
            continue
        sheet_name = None
        for ak, av in elem.attrib.items():
            if ak.split("}")[-1] == "Name":
                sheet_name = av
                break
        sheet_name = sheet_name or f"Sheet{len(sheets) + 1}"
        rows: list[list[str]] = []
        for row_el in elem.iter():
            if row_el.tag.split("}")[-1] != "Row":
                continue
            r_idx_attr = next((v for k, v in row_el.attrib.items() if k.split("}")[-1] == "Index"), None)
            if r_idx_attr:
                target_row = max(0, int(r_idx_attr) - 1)
                while len(rows) < target_row:
                    rows.append([])
            cur_row: list[str] = []
            for cell_el in list(row_el):
                if cell_el.tag.split("}")[-1] != "Cell":
                    continue
                idx_attr = next((v for k, v in cell_el.attrib.items() if k.split("}")[-1] == "Index"), None)
                if idx_attr:
                    target_idx = max(0, int(idx_attr) - 1)
                    while len(cur_row) < target_idx:
                        cur_row.append("")
                val_text = ""
                for d_el in cell_el.iter():
                    if d_el.tag.split("}")[-1] == "Data" and d_el.text is not None:
                        val_text = d_el.text.strip()
                        break
                cur_row.append(val_text)
            if cur_row:
                rows.append(cur_row)
        sheets[sheet_name] = rows
    return sheets


def _read_text_spreadsheet_fallback(path: Path, sheet: str | int, header_row: int) -> pd.DataFrame | None:
    raw = path.read_bytes()
    head = raw[:512].lstrip(b"\xef\xbb\xbf\xff\xfe\r\n\t ")
    if not head.startswith(b"<") and b"\t" not in raw[:2048]:
        return None

    for enc in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except Exception:
            text = ""
    if not text:
        return None

    low = text[:4096].lower()
    if "workbook" in low and "spreadsheet" in low:
        try:
            sheets = _parse_spreadsheetml(path)
            if isinstance(sheet, int):
                key = list(sheets.keys())[sheet]
            else:
                key = sheet if sheet in sheets else next((k for k in sheets if k.lower() == sheet.lower()), "")
            if key and key in sheets:
                return _rows_to_dataframe(sheets[key], header_row)
            if isinstance(sheet, str) and sheets:
                raise SheetNotFoundError(
                    f"La hoja requerida '{sheet}' no existe en el archivo '{path.name}'. "
                    f"Hojas encontradas en el libro: {list(sheets.keys())}"
                )
        except SheetNotFoundError:
            raise
        except Exception:
            pass

    if "<table" in low or "<html" in low:
        parser = _HtmlTableParser()
        parser.feed(text)
        if parser.tables:
            best_table = max(parser.tables, key=len)
            return _rows_to_dataframe(best_table, header_row)

    if "\t" in text[:4096]:
        try:
            return pd.read_csv(path, sep="\t", header=header_row, encoding="latin-1")
        except Exception:
            pass
    return None


def list_excel_sheets(path: Path) -> list[str]:
    try:
        import python_calamine
        wb = python_calamine.CalamineWorkbook.from_path(path)
        return list(wb.sheet_names)
    except Exception:
        pass
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True)
        try:
            return list(wb.sheetnames)
        finally:
            wb.close()
    except Exception:
        pass
    try:
        raw_head = path.read_bytes()[:4096].decode("utf-8-sig", errors="ignore").lower()
        if "workbook" in raw_head and "spreadsheet" in raw_head:
            return list(_parse_spreadsheetml(path).keys())
        if "<table" in raw_head or "<html" in raw_head:
            return ["Data"]
    except Exception:
        pass
    return []


def read_excel_sheet(path: Path, sheet: str | int = 0, header_row: int = 0) -> pd.DataFrame:
    last_exc: Exception | None = None
    engines = ("calamine", "openpyxl") if path.suffix.lower() in (".xlsx", ".xlsm") else ("calamine",)
    for engine in engines:
        try:
            return pd.read_excel(
                path,
                sheet_name=sheet,
                header=header_row,
                engine=engine,
            )
        except Exception as exc:
            last_exc = exc

    fallback_df = _read_text_spreadsheet_fallback(path, sheet=sheet, header_row=header_row)
    if fallback_df is not None:
        return fallback_df

    if isinstance(sheet, str):
        sheet_names = list_excel_sheets(path)
        if sheet_names and sheet not in sheet_names:
            raise SheetNotFoundError(
                f"La hoja requerida '{sheet}' no existe en el archivo '{path.name}'. "
                f"Hojas encontradas en el libro: {sheet_names}"
            )
    raise ValueError(f"No se pudo leer la hoja '{sheet}' del archivo Excel {path.name}: {last_exc}")


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
            matches = find_matching_excel_files(search_dir, self.spec.file_pattern, recursive=False)
            if matches:
                return matches[0]

        matches = find_matching_excel_files(self.base_path, self.spec.file_pattern, recursive=True)
        if matches:
            return matches[0]

        pat_hint = ", ".join(_expand_excel_patterns(self.spec.file_pattern))
        raise FileNotFoundError(
            f"No se encontró archivo ({pat_hint}) en {self.base_path}"
        )

    def get_sheet_names(self, path: Path) -> list[str]:
        return list_excel_sheets(path)

    def read_raw(self) -> pd.DataFrame:
        path = self.resolve_path()
        logger.info("Leyendo Excel crudo %s (hoja=%s, fila=%d)", path.name, self.spec.sheet, self.spec.header_row)
        df = read_excel_sheet(path, sheet=self.spec.sheet, header_row=self.spec.header_row)

        if self.spec.column_renames:
            df.columns = [str(c).strip() for c in df.columns]
            df = df.rename(columns=dict(self.spec.column_renames))

        if self.spec.required_columns:
            missing = [c for c in self.spec.required_columns if c not in df.columns]
            if missing:
                raise MissingColumnsError(
                    f"El archivo '{path.name}' (hoja '{self.spec.sheet}') no contiene las columnas requeridas: {missing}"
                )

        df = df.dropna(how="all")

        if self.spec.dedupe_keys:
            valid_keys = [k for k in self.spec.dedupe_keys if k in df.columns]
            if valid_keys:
                df = df.drop_duplicates(subset=valid_keys, keep="first")

        logger.info("%s validado y leido: %d filas x %d columnas", self.spec.name, len(df), len(df.columns))
        return df
