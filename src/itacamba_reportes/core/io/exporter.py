from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from time import perf_counter

import pandas as pd

logger = logging.getLogger(__name__)

# Columnas tecnicas internas del bot a excluir de reportes finales de negocio
TECHNICAL_COLUMNS = frozenset({
    "id",
    "created_at",
    "updated_at",
    "version",
    "is_current",
    "valid_from",
    "valid_to",
    "source_hash",
    "derived_hash",
    "full_hash",
    "full_row_hash",
    "cd_status",
})


class ExcelReportExporter:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = Path(output_dir)

    def export(
        self,
        df: pd.DataFrame,
        report_name: str,
        control_info: dict | None = None,
        include_control_sheet: bool = False,
    ) -> Path:
        t0 = perf_counter()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
        target = self.output_dir / f"{report_name}_{timestamp}.xlsx"

        # Paso 1: Filtrar columnas tecnicas de auditoria interna para entrega limpia a negocio
        business_cols = [c for c in df.columns if c not in TECHNICAL_COLUMNS]
        clean_df = df[business_cols]

        try:
            self._write(clean_df, target, control_info, include_control_sheet=include_control_sheet, engine="xlsxwriter")
        except Exception:
            self._write(clean_df, target, control_info, include_control_sheet=include_control_sheet, engine="openpyxl")

        logger.info("Export Excel exitoso: %s (%d filas, %d columnas, %.2fs)", target.name, len(clean_df), len(clean_df.columns), perf_counter() - t0)
        return target

    def export_multi_sheet(
        self,
        sheets: dict[str, pd.DataFrame],
        file_name: str,
        timestamped: bool = False,
    ) -> Path:
        t0 = perf_counter()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        stem = Path(file_name).stem
        if timestamped:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
            target = self.output_dir / f"{stem}_{timestamp}.xlsx"
        else:
            target = self.output_dir / f"{stem}.xlsx"

        clean_sheets = {}
        for sname, df in sheets.items():
            business_cols = [c for c in df.columns if c not in TECHNICAL_COLUMNS]
            clean_sheets[sname] = df[business_cols]

        try:
            self._write_multi(clean_sheets, target, engine="xlsxwriter")
        except Exception:
            self._write_multi(clean_sheets, target, engine="openpyxl")

        summary = ", ".join(f"{k}: {len(v)} filas" for k, v in clean_sheets.items())
        logger.info("Export Multi-Sheet Excel exitoso: %s (%s, %.2fs)", target.name, summary, perf_counter() - t0)
        return target

    @staticmethod
    def _write_multi(
        sheets: dict[str, pd.DataFrame],
        target: Path,
        engine: str,
    ) -> None:
        kwargs = {}
        if engine == "xlsxwriter":
            kwargs["engine_kwargs"] = {"options": {"constant_memory": True}}
        with pd.ExcelWriter(target, engine=engine, **kwargs) as writer:
            for sname, df in sheets.items():
                df.to_excel(writer, index=False, sheet_name=sname)

    @staticmethod
    def _write(
        df: pd.DataFrame,
        target: Path,
        control_info: dict | None,
        include_control_sheet: bool,
        engine: str,
    ) -> None:
        kwargs = {}
        if engine == "xlsxwriter":
            kwargs["engine_kwargs"] = {"options": {"constant_memory": True}}
        with pd.ExcelWriter(target, engine=engine, **kwargs) as writer:
            df.to_excel(writer, index=False, sheet_name="Data")
            if include_control_sheet and control_info:
                ctrl_df = pd.DataFrame(
                    [{"Metrica": k, "Valor": str(v)} for k, v in control_info.items()]
                )
                ctrl_df.to_excel(writer, index=False, sheet_name="CONTROL")
