from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from time import perf_counter

import pandas as pd

logger = logging.getLogger(__name__)


class ExcelReportExporter:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = Path(output_dir)

    def export(self, df: pd.DataFrame, report_name: str, control_info: dict | None = None) -> Path:
        t0 = perf_counter()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
        target = self.output_dir / f"{report_name}_{timestamp}.xlsx"

        try:
            self._write(df, target, control_info, engine="xlsxwriter")
        except Exception:
            self._write(df, target, control_info, engine="openpyxl")

        logger.info("Export Excel exitoso: %s (%d filas, %.2fs)", target.name, len(df), perf_counter() - t0)
        return target

    @staticmethod
    def _write(df: pd.DataFrame, target: Path, control_info: dict | None, engine: str) -> None:
        with pd.ExcelWriter(target, engine=engine) as writer:
            df.to_excel(writer, index=False, sheet_name="DATOS")
            if control_info:
                ctrl_df = pd.DataFrame(
                    [{"Metrica": k, "Valor": str(v)} for k, v in control_info.items()]
                )
                ctrl_df.to_excel(writer, index=False, sheet_name="CONTROL")
