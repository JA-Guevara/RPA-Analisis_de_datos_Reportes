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
    date_from: str | None = None,
    date_to: str | None = None,
    variant: str | None = None,
    export_filename: str = "QUERY",
    target_dir: Path | str | None = None,
    config: SapDownloadConfig | None = None,
    selectors: SelectoresSAP | None = None,
) -> Path:
    if config is None:
        config = SapDownloadConfig(
            transaction=transaction,
            variant=variant,
            date_from=date_from,
            date_to=date_to,
            export_filename=export_filename,
            target_dir=target_dir,
        )

    return execute_download_report(session_manager, config, selectors=selectors)
