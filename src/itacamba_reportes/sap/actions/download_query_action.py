from __future__ import annotations

import logging
from pathlib import Path

from itacamba_reportes.sap.actions.download_action import execute_download_report
from itacamba_reportes.sap.config import SapDownloadConfig
from itacamba_reportes.sap.selectors import SelectoresSAP
from itacamba_reportes.sap.session import SapSessionManager

logger = logging.getLogger(__name__)


def execute_download_query(
    session_manager: SapSessionManager,
    transaction: str = "zbcs",
    variant: str | None = None,
    ledger: str | None = None,
    period_low: str | int | None = None,
    period_high: str | int | None = None,
    layout_row: int | None = None,
    export_filename: str = "QUERY.xlsx",
    target_dir: Path | str | None = None,
    config: SapDownloadConfig | None = None,
    selectors: SelectoresSAP | None = None,
) -> Path:
    if config is None:
        config = SapDownloadConfig(
            transaction=transaction,
            variant=variant,
            ledger=ledger,
            period_low=period_low,
            period_high=period_high,
            layout_row=layout_row,
            export_filename=export_filename,
            target_dir=target_dir,
        )

    return execute_download_report(session_manager, config, selectors=selectors)
