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

    @staticmethod
    def _write(
        df: pd.DataFrame,
        target: Path,
        control_info: dict | None,
        include_control_sheet: bool,
        engine: str,
    ) -> None:
        with pd.ExcelWriter(target, engine=engine) as writer:
            df.to_excel(writer, index=False, sheet_name="Data")
            if include_control_sheet and control_info:
                ctrl_df = pd.DataFrame(
                    [{"Metrica": k, "Valor": str(v)} for k, v in control_info.items()]
                )
                ctrl_df.to_excel(writer, index=False, sheet_name="CONTROL")
