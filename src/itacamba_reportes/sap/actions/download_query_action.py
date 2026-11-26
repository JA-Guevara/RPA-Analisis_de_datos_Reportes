from __future__ import annotations

import logging
from pathlib import Path

from itacamba_reportes.sap.actions.download_action import execute_download_report
from itacamba_reportes.sap.config import ConfigDescargaQuery, SapDownloadConfig
from itacamba_reportes.sap.selectors import SelectoresSAP
from itacamba_reportes.sap.session import SapSessionManager

logger = logging.getLogger(__name__)


def execute_download_query(
    session_manager: SapSessionManager,
    transaction: str = "ZVCSD381",
    sociedad: str = "4253",
    variant: str | None = "/IM",
    date_from: str | None = None,
    date_to: str | None = None,
    months_back: int = 3,
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
        cfg_builder = ConfigDescargaQuery(
            transaction=transaction,
            sociedad=sociedad,
            variant=variant or "/IM",
            months_back=months_back,
            export_filename=export_filename,
        )
        config = cfg_builder.to_download_config(
            target_dir=target_dir,
            date_from_override=date_from,
            date_to_override=date_to,
            period_override=period_low,
        )
        if period_high is not None and str(period_high).strip():
            config.period_high = str(period_high).strip()
        if ledger:
            config.ledger = ledger
        if layout_row is not None:
            config.layout_row = layout_row

    return execute_download_report(session_manager, config, selectors=selectors)
