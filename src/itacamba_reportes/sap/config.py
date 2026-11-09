from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(slots=True)
class ConfigDescargaGD20:
    transaction: str = "gd20"
    ledger: str = "VC"
    variant: str = "Prueba_GD20"
    period: str | int | None = None
    layout_row: int = 16
    export_filename: str = "GD20.xlsx"

    def to_download_config(
        self,
        target_dir: Path | str | None = None,
        period_override: str | int | None = None,
    ) -> SapDownloadConfig:
        p = period_override or self.period
        if p is None or str(p).strip() in ("", "0"):
            p = str(datetime.now().month)
        else:
            p = str(p).strip()

        return SapDownloadConfig(
            transaction=self.transaction,
            ledger=self.ledger,
            variant=self.variant,
            period_low=p,
            period_high=p,
            layout_row=self.layout_row,
            export_filename=self.export_filename,
            target_dir=target_dir,
        )


@dataclass(slots=True)
class ConfigDescargaQuery:
    transaction: str = "zbcs"
    ledger: str = ""
    variant: str = ""
    period: str | int | None = None
    layout_row: int | None = None
    export_filename: str = "QUERY.xlsx"

    def to_download_config(
        self,
        target_dir: Path | str | None = None,
        period_override: str | int | None = None,
    ) -> SapDownloadConfig:
        p = period_override or self.period
        p_val = str(p).strip() if p is not None and str(p).strip() != "" else None

        return SapDownloadConfig(
            transaction=self.transaction,
            ledger=self.ledger.strip() if self.ledger else None,
            variant=self.variant.strip() if self.variant else None,
            period_low=p_val,
            period_high=p_val,
            layout_row=self.layout_row,
            export_filename=self.export_filename,
            target_dir=target_dir,
        )


CONFIG_GD20 = ConfigDescargaGD20()
CONFIG_QUERY = ConfigDescargaQuery()
CONFIG_CARTERA = CONFIG_QUERY


@dataclass(slots=True)
class SapDownloadConfig:
    transaction: str
    ledger: str | None = None
    variant: str | None = None
    period_low: str | int | None = None
    period_high: str | int | None = None
    layout_row: int | None = None
    export_filename: str = "EXPORT.xlsx"
    target_dir: Path | str | None = None
