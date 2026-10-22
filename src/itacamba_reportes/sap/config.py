from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


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
        date_from: str | None = None,
        date_to: str | None = None,
        export_filename: str = "QUERY",
        target_dir: Path | str | None = None,
    ) -> SapDownloadConfig:
        return cls(
            transaction=transaction,
            variant=variant,
            date_from=date_from,
            date_to=date_to,
            export_filename=export_filename,
            target_dir=target_dir,
        )
