from __future__ import annotations

import logging
from pathlib import Path

from itacamba_reportes.sap.actions.download_action import execute_download_report
from itacamba_reportes.sap.config import SapDownloadConfig
from itacamba_reportes.sap.selectors import SelectoresSAP
from itacamba_reportes.sap.session import SapSessionManager

logger = logging.getLogger(__name__)


def execute_download_gd20(
    session_manager: SapSessionManager,
    transaction: str = "gd20",
    month: int | None = None,
    period_low: str | int | None = None,
    period_high: str | int | None = None,
    year: str | int | None = None,
    year_high: str | int | None = None,
    ledger: str = "VC",
    variant: str = "BOT_GD20",
    layout_name: str | None = "//AVRILGD20",
    layout_row: int | None = None,
    export_filename: str = "GD20.xlsx",
    target_dir: Path | str | None = None,
    config: SapDownloadConfig | None = None,
    selectors: SelectoresSAP | None = None,
) -> Path:
    if config is None:
        p_low = period_low if period_low is not None else month
        p_high = period_high if period_high is not None else month
        config = SapDownloadConfig.for_gd20(
            transaction=transaction,
            variant=variant,
            ledger=ledger,
            period=p_low if p_low is not None else p_high,
            year=year,
            layout_name=layout_name,
            layout_row=layout_row,
            export_filename=export_filename,
            target_dir=target_dir,
        )
        if p_high is not None:
            config.period_high = p_high
        if year_high is not None:
            config.year_high = year_high

    return execute_download_report(session_manager, config, selectors=selectors)
