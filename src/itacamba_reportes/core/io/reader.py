from __future__ import annotations

import ctypes
import email
import html
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

import pandas as pd

logger = logging.getLogger(__name__)

NULL_TOKENS = frozenset({"", "#", "N/A", "NA", "nan", "NaN", "None", "null", "NULL", "00000000"})
EXCEL_EXTENSIONS: tuple[str, ...] = (".xlsx", ".xlsm", ".xlsb", ".xls")

_TR_RE = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
_TD_RE = re.compile(r"<t[dh]\b([^>]*)>(.*?)</t[dh]>", re.IGNORECASE | re.DOTALL)
_COLSPAN_RE = re.compile(r"colspan\s*=\s*[\"']?(\d+)", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_X_NAME_RE = re.compile(r"<x:Name>(.*?)</x:Name>", re.IGNORECASE | re.DOTALL)

_ONEDRIVE_CLOUD_MASK = 0x1000 | 0x40000 | 0x400000


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


def ensure_onedrive_file_ready(path: Path, max_wait_s: float = 20.0) -> None:
    if os.name != "nt" or not path.exists():
        return
    try:
        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
    except Exception:
        return

    is_cloud = attrs != -1 and bool(attrs & _ONEDRIVE_CLOUD_MASK)
    if is_cloud:
        logger.info("Archivo '%s' en modo nube OneDrive; descargando copia local antes de leer...", path.name)

    deadline = time.perf_counter() + max_wait_s
    last_size = -1
    stable_hits = 0
    while True:
        try:
            with open(path, "rb") as f:
                f.read(1)
            cur_size = path.stat().st_size
            cur_attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
            still_cloud = cur_attrs != -1 and bool(cur_attrs & _ONEDRIVE_CLOUD_MASK)
            if not is_cloud and not still_cloud:
                return
            if not still_cloud and cur_size > 0 and cur_size == last_size:
                stable_hits += 1
                if stable_hits >= 1:
                    return
            else:
                stable_hits = 0
            last_size = cur_size
        except PermissionError:
            if not is_cloud and time.perf_counter() >= deadline:
                return
        except OSError:
            if time.perf_counter() >= deadline:
                return

        if time.perf_counter() >= deadline:
            return
        time.sleep(0.35)


def _read_head_bytes(path: Path, size: int = 8192) -> bytes:
    with open(path, "rb") as f:
        return f.read(size)


def _decode_text_bytes(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "utf-16", "latin-1"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("latin-1", errors="replace")


def _extract_html_rows_fast(html_text: str) -> list[list[str]]:
    if "&#32;" in html_text:
        html_text = html_text.replace("&#32;", " ")
    if "&#160;" in html_text:
        html_text = html_text.replace("&#160;", " ")
    if "\xa0" in html_text:
        html_text = html_text.replace("\xa0", " ")

    rows: list[list[str]] = []
    for m_tr in _TR_RE.finditer(html_text):
        r_html = m_tr.group(1)
        has_cs = "colspan" in r_html.lower()
        row_cells: list[str] = []
        for m_td in _TD_RE.finditer(r_html):
            attrs, inner = m_td.group(1), m_td.group(2)
            if "<" in inner:
                inner = _TAG_RE.sub("", inner)
            if "&" in inner:
                inner = html.unescape(inner)
            row_cells.append(inner.strip())
            if has_cs and "colspan" in attrs.lower():
                cs_m = _COLSPAN_RE.search(attrs)
                if cs_m:
                    extra = int(cs_m.group(1)) - 1
                    if extra > 0:
                        row_cells.extend([""] * extra)
        rows.append(row_cells)
    return rows


def _rows_to_dataframe(rows: list[list[str]], header_row: int | None) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    if header_row is None:
        width = max(len(r) for r in rows)
        norm_rows = [r + [""] * (width - len(r)) for r in rows]
        return pd.DataFrame(norm_rows)
    if header_row >= len(rows):
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


def _extract_mhtml_html(path: Path) -> str | None:
    with open(path, "rb") as f:
        msg = email.message_from_binary_file(f)

    html_parts: list[bytes] = []
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    html_parts.append(payload)
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            html_parts.append(payload)

    if not html_parts:
        return None
    best = max(html_parts, key=len)
    return _decode_text_bytes(best)


def _is_text_like_head(head_bytes: bytes) -> bool:
    low = head_bytes[:1024].lstrip(b"\xef\xbb\xbf\xff\xfe\r\n\t ").lower()
    return (
        b"mime-version:" in low
        or low.startswith((b"<html", b"<!doctype", b"<table", b"<?xml", b"<workbook"))
        or (not low.startswith((b"pk\x03\x04", b"\xd0\xcf\x11\xe0")) and b"\t" in head_bytes[:2048])
    )


def _read_text_spreadsheet_fallback(path: Path, sheet: str | int, header_row: int | None) -> pd.DataFrame | None:
    head = _read_head_bytes(path, 8192)
    low_head = head[:2048].lstrip(b"\xef\xbb\xbf\xff\xfe\r\n\t ").lower()

    if b"mime-version:" in low_head:
        mhtml_text = _extract_mhtml_html(path)
        if mhtml_text:
            rows = _extract_html_rows_fast(mhtml_text)
            if rows:
                return _rows_to_dataframe(rows, header_row)
        return None

    if not low_head.startswith(b"<") and b"\t" not in head[:2048]:
        return None

    raw = path.read_bytes()
    text = _decode_text_bytes(raw)
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
        rows = _extract_html_rows_fast(text)
        if rows:
            return _rows_to_dataframe(rows, header_row)

    if "\t" in text[:4096]:
        try:
            return pd.read_csv(path, sep="\t", header=header_row, encoding="latin-1")
        except Exception:
            pass
    return None


def list_excel_sheets(path: Path) -> list[str]:
    try:
        head = _read_head_bytes(path, 8192)
    except Exception:
        return []

    low_head = head.decode("utf-8", errors="ignore").lower()
    if "mime-version:" in low_head:
        names = [n.strip() for n in _X_NAME_RE.findall(head.decode("utf-8", errors="ignore")) if n.strip()]
        if names:
            return names
        return [path.stem or "Data"]

    if low_head.lstrip().startswith(("<?xml", "<workbook")) and "spreadsheet" in low_head:
        try:
            return list(_parse_spreadsheetml(path).keys())
        except Exception:
            return []

    if low_head.lstrip().startswith(("<html", "<!doctype", "<table")):
        return [path.stem or "Data"]

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
        return []


def read_excel_sheet(path: Path, sheet: str | int = 0, header_row: int | None = 0) -> pd.DataFrame:
    ensure_onedrive_file_ready(path)
    try:
        head = _read_head_bytes(path, 8192)
    except Exception:
        head = b""

    last_exc: Exception | None = None
    if not _is_text_like_head(head):
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
    sheet_aliases: tuple[str, ...] = field(default_factory=tuple)


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

    def _resolve_target_sheet(self, path: Path) -> str | int:
        if not isinstance(self.spec.sheet, str):
            return self.spec.sheet
        if not self.spec.sheet_aliases:
            return self.spec.sheet

        available = list_excel_sheets(path)
        if not available:
            return self.spec.sheet

        candidates = (self.spec.sheet, *self.spec.sheet_aliases)
        for cand in candidates:
            if cand in available:
                return cand
        low_map = {s.lower(): s for s in available}
        for cand in candidates:
            if cand.lower() in low_map:
                return low_map[cand.lower()]
        if len(available) == 1:
            return available[0]
        return self.spec.sheet

    def read_raw(self) -> pd.DataFrame:
        path = self.resolve_path()
        target_sheet = self._resolve_target_sheet(path)
        logger.info("Leyendo Excel crudo %s (hoja=%s, fila=%d)", path.name, target_sheet, self.spec.header_row)
        df = read_excel_sheet(path, sheet=target_sheet, header_row=self.spec.header_row)

        if self.spec.column_renames:
            df.columns = [str(c).strip() for c in df.columns]
            df = df.rename(columns=dict(self.spec.column_renames))

        if self.spec.required_columns:
            missing = [c for c in self.spec.required_columns if c not in df.columns]
            if missing:
                raise MissingColumnsError(
                    f"El archivo '{path.name}' (hoja '{target_sheet}') no contiene las columnas requeridas: {missing}"
                )

        df = df.dropna(how="all")

        if self.spec.dedupe_keys:
            valid_keys = [k for k in self.spec.dedupe_keys if k in df.columns]
            if valid_keys:
                df = df.drop_duplicates(subset=valid_keys, keep="first")

        logger.info("%s validado y leido: %d filas x %d columnas", self.spec.name, len(df), len(df.columns))
        return df
