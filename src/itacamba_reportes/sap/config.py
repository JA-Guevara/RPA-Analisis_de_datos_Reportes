from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


@dataclass(slots=True)
class ConfigDescargaGD20:
    transaction: str = "gd20"
    ledger: str = "VC"
    variant: str = "Prueba_GD20"
    period: str | int = 10
    layout_row: int = 16
    export_filename: str = "GD20.xlsx"

    def to_download_config(self, target_dir: Path | str | None = None) -> SapDownloadConfig:
        p = str(self.period).strip() if str(self.period).strip() else time.strftime("%m")
        return SapDownloadConfig(
            transaction=self.transaction,
            variant=self.variant or None,
            ledger=self.ledger or None,
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
    period: str | int = ""
    layout_row: int | None = None
    export_filename: str = "QUERY.xlsx"

    def to_download_config(self, target_dir: Path | str | None = None) -> SapDownloadConfig:
        p = str(self.period).strip() or None if self.period != "" else None
        return SapDownloadConfig(
            transaction=self.transaction,
            variant=self.variant.strip() or None if isinstance(self.variant, str) else self.variant,
            ledger=self.ledger.strip() or None if isinstance(self.ledger, str) else self.ledger,
            period_low=p,
            period_high=p,
            layout_row=self.layout_row,
            export_filename=self.export_filename,
            target_dir=target_dir,
        )


@dataclass(slots=True)
class ConfigDescargaCartera:
    transaction: str = "zsdi"
    ledger: str = ""
    variant: str = "CAD_CLIENTE"
    period: str | int = ""
    layout_row: int | None = None
    export_filename: str = "CARTERA.xlsx"

    def to_download_config(self, target_dir: Path | str | None = None) -> SapDownloadConfig:
        p = str(self.period).strip() or None if self.period != "" else None
        return SapDownloadConfig(
            transaction=self.transaction,
            variant=self.variant.strip() or None if isinstance(self.variant, str) else self.variant,
            ledger=self.ledger.strip() or None if isinstance(self.ledger, str) else self.ledger,
            period_low=p,
            period_high=p,
            layout_row=self.layout_row,
            export_filename=self.export_filename,
            target_dir=target_dir,
        )


CONFIG_GD20 = ConfigDescargaGD20()
CONFIG_QUERY = ConfigDescargaQuery()
CONFIG_CARTERA = ConfigDescargaCartera()


@dataclass(slots=True)
class SapDownloadConfig:
    transaction: str
    variant: str | None = None
    ledger: str | None = None
    period_low: str | int | None = None
    period_high: str | int | None = None
    year: str | int | None = None
    date_from: str | None = None
    date_to: str | None = None
    layout_name: str | None = None
    layout_row: int | None = None
    export_filename: str = "EXPORT"
    target_dir: Path | str | None = None
    custom_inputs: Mapping[str, str] = field(default_factory=dict)

    @classmethod
    def for_gd20(
        cls,
        transaction: str = "gd20",
        ledger: str = "VC",
        variant: str = "Prueba_GD20",
        period: str | int | None = None,
        year: str | int | None = None,
        layout_row: int = 16,
        export_filename: str = "GD20",
        target_dir: Path | str | None = None,
    ) -> SapDownloadConfig:
        return cls(
            transaction=transaction,
            variant=variant,
            ledger=ledger,
            period_low=period,
            period_high=period,
            year=year,
            layout_row=layout_row,
            export_filename=export_filename,
            target_dir=target_dir,
        )

    @classmethod
    def for_query(
        cls,
        transaction: str = "zbcs",
        variant: str | None = None,
        ledger: str | None = None,
        period: str | int | None = None,
        layout_row: int | None = None,
        export_filename: str = "QUERY",
        target_dir: Path | str | None = None,
    ) -> SapDownloadConfig:
        return cls(
            transaction=transaction,
            variant=variant,
            ledger=ledger,
            period_low=period,
            period_high=period,
            layout_row=layout_row,
            export_filename=export_filename,
            target_dir=target_dir,
        )
