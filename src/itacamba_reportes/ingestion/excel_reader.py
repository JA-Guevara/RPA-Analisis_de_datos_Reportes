from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from itacamba_reportes.ingestion.excel_source import ExcelSource
from itacamba_reportes.shared.null_tokens import NULL_TOKENS

logger = logging.getLogger(__name__)


def _is_null_like(value: object) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    if isinstance(value, str) and value.strip() in NULL_TOKENS:
        return True
    return False


class ExcelReader:
    """Lector configurable de Excel (sheet, header, renames, dedupe).

    Toda la variación entre datasets vive en el ExcelSource (YAML);
    no hacen falta subclases por dataset.
    """

    def __init__(self, source: ExcelSource, data_path: Path):
        self.source = source
        self.data_path = Path(data_path)

    def read(self) -> pd.DataFrame:
        path = self.resolve_path()
        logger.info("Leyendo %s hoja=%s", path.name, self.source.sheet)

        df = self._read_excel(path)
        df = self._apply_metadata_skip(df)
        df = self._apply_column_renames(df)
        df = self._drop_rows_with_null_key(df)
        df = self._apply_dedupe(df)

        logger.info(
            "%s leido: %d filas x %d cols",
            self.source.name,
            len(df),
            len(df.columns),
        )
        return df

    def resolve_path(self) -> Path:
        base = self.data_path
        if self.source.subdir:
            base = base / self.source.subdir
        matches = sorted(base.glob(self.source.file_pattern))
        if not matches:
            raise FileNotFoundError(
                f"No se encontro archivo '{self.source.file_pattern}' en {base}"
            )
        return max(matches, key=lambda p: p.stat().st_mtime)

    def _read_excel(self, path: Path) -> pd.DataFrame:
        return pd.read_excel(
            path,
            sheet_name=self.source.sheet,
            header=self.source.header_row,
            engine="calamine",
        )

    def _apply_metadata_skip(self, df: pd.DataFrame) -> pd.DataFrame:
        skip = self.source.metadata_rows_to_skip
        if skip <= 0:
            return df
        if len(df) <= skip:
            logger.warning(
                "%s tiene %d filas pero se piden %d skips - devolviendo vacio",
                self.source.name, len(df), skip,
            )
            return df.iloc[0:0]
        return df.iloc[skip:].reset_index(drop=True)

    def _apply_column_renames(self, df: pd.DataFrame) -> pd.DataFrame:
        renames = self.source.column_renames
        if not renames:
            return df
        return df.rename(columns=dict(renames))

    def _drop_rows_with_null_key(self, df: pd.DataFrame) -> pd.DataFrame:
        keys = self.source.dedupe_on
        if not keys:
            return df
        existing = [k for k in keys if k in df.columns]
        if not existing:
            return df

        before = len(df)
        mask_invalid = pd.Series(False, index=df.index)
        for col in existing:
            mask_invalid = mask_invalid | df[col].apply(_is_null_like)

        df = df.loc[~mask_invalid].reset_index(drop=True)
        removed = before - len(df)
        if removed > 0:
            logger.warning(
                "%s: %d filas con clave invalida en %s descartadas (null/token SAP)",
                self.source.name, removed, existing,
            )
        return df

    def _apply_dedupe(self, df: pd.DataFrame) -> pd.DataFrame:
        keys = self.source.dedupe_on
        before = len(df)
        ci = getattr(self.source, "dedupe_case_insensitive", False)

        if keys:
            missing = [k for k in keys if k not in df.columns]
            if missing:
                logger.warning(
                    "%s dedupe_on apunta a columnas inexistentes %s, skip dedupe",
                    self.source.name, missing,
                )
                return df

            if ci:
                # Normaliza upper+strip en cols-key para dedupe consistente
                # con collation case-insensitive de SQL Server.
                norm_cols = [f"_dedupe_norm_{k}" for k in keys]
                for k, nc in zip(keys, norm_cols):
                    df[nc] = df[k].astype("string").str.upper().str.strip()
                df = df.drop_duplicates(subset=norm_cols, keep="first").reset_index(drop=True)
                df = df.drop(columns=norm_cols, errors="ignore")
            else:
                df = df.drop_duplicates(subset=list(keys), keep="first").reset_index(drop=True)

            removed = before - len(df)
            if removed > 0:
                logger.warning(
                    "%s: %d filas duplicadas en %s eliminadas (kept first%s)",
                    self.source.name, removed, list(keys),
                    ", case-insensitive" if ci else "",
                )
            return df

        df = df.drop_duplicates(keep="first").reset_index(drop=True)
        removed = before - len(df)
        if removed > 0:
            logger.warning(
                "%s: %d filas 100%% duplicadas eliminadas (full-row dedupe)",
                self.source.name, removed,
            )
        return df
