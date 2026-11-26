from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(slots=True)
class ConfigDescargaGD20:
    transaction: str = "gd20"
    ledger: str = "VC"
    variant: str = "BOT_GD20"
    period: str | int | None = None
    year: str | int | None = None
    layout_name: str | None = "//AVRILGD20"
    layout_row: int | None = None
    export_filename: str = "GD20.xlsx"

    def to_download_config(
        self,
        target_dir: Path | str | None = None,
        period_override: str | int | None = None,
        period_high_override: str | int | None = None,
        year_override: str | int | None = None,
        year_high_override: str | int | None = None,
    ) -> SapDownloadConfig:
        p = period_override or self.period
        if p is None or str(p).strip() in ("", "0"):
            p_low = str(datetime.now().month)
        else:
            p_low = str(p).strip()

        p_high_raw = period_high_override
        if p_high_raw is None or str(p_high_raw).strip() in ("", "0"):
            p_high = p_low
        else:
            p_high = str(p_high_raw).strip()

        y = year_override or self.year
        if y is None or str(y).strip() in ("", "0"):
            y_low = str(datetime.now().year)
        else:
            y_low = str(y).strip()

        y_high_raw = year_high_override
        if y_high_raw is not None and str(y_high_raw).strip() not in ("", "0", y_low):
            y_high: str | None = str(y_high_raw).strip()
        else:
            y_high = None

        return SapDownloadConfig(
            transaction=self.transaction,
            ledger=self.ledger,
            variant=self.variant,
            period_low=p_low,
            period_high=p_high,
            year_low=y_low,
            year_high=y_high,
            layout_name=self.layout_name,
            layout_row=self.layout_row,
            export_filename=self.export_filename,
            target_dir=target_dir,
        )


@dataclass(slots=True)
class ConfigDescargaQuery:
    transaction: str = "ZVCSD381"
    sociedad: str = "4253"
    variant: str = "/IM"
    months_back: int = 3
    date_from: str | None = None
    date_to: str | None = None
    ledger: str = ""
    period: str | int | None = None
    layout_name: str | None = ""
    layout_row: int | None = None
    export_filename: str = "QUERY.xlsx"

    def to_download_config(
        self,
        target_dir: Path | str | None = None,
        period_override: str | int | None = None,
        date_from_override: str | None = None,
        date_to_override: str | None = None,
    ) -> SapDownloadConfig:
        import calendar

        # Fecha hasta: por defecto hoy (formato DD.MM.YYYY para SAP)
        d_to_str = date_to_override or self.date_to
        if not d_to_str:
            now = datetime.now()
            d_to_str = now.strftime("%d.%m.%Y")
            d_to_dt = now
        else:
            try:
                if "-" in d_to_str:
                    parts = d_to_str.split("-")
                    d_to_dt = datetime(int(parts[0]), int(parts[1]), int(parts[2]))
                    d_to_str = d_to_dt.strftime("%d.%m.%Y")
                else:
                    parts = d_to_str.split(".")
                    d_to_dt = datetime(int(parts[2]), int(parts[1]), int(parts[0]))
            except Exception:
                d_to_dt = datetime.now()
                d_to_str = d_to_dt.strftime("%d.%m.%Y")

        # Fecha desde: por defecto 3 meses atras exactos para Query
        d_from_str = date_from_override or self.date_from
        if not d_from_str:
            y = d_to_dt.year
            m = d_to_dt.month - self.months_back
            while m <= 0:
                m += 12
                y -= 1
            max_day = calendar.monthrange(y, m)[1]
            day = min(d_to_dt.day, max_day)
            d_from_dt = datetime(y, m, day)
            d_from_str = d_from_dt.strftime("%d.%m.%Y")
        elif "-" in d_from_str:
            parts = d_from_str.split("-")
            d_from_str = f"{parts[2]}.{parts[1]}.{parts[0]}"

        p = period_override or self.period
        p_val = str(p).strip() if p is not None and str(p).strip() != "" else None

        return SapDownloadConfig(
            transaction=self.transaction,
            sociedad=self.sociedad,
            variant=self.variant,
            date_from=d_from_str,
            date_to=d_to_str,
            ledger=self.ledger.strip() if self.ledger else None,
            period_low=p_val,
            period_high=p_val,
            layout_name=self.layout_name.strip() if self.layout_name else None,
            layout_row=self.layout_row,
            export_filename=self.export_filename,
            target_dir=target_dir,
        )


@dataclass(slots=True)
class ConfigDescargaCartera:
    available_in_sap_gui: bool = False
    source_note: str = "CARTERA.xlsx llega por correo automático (Q_VCBO_ZSDI_I03_CAD_CLIENTE_000), sin script SAP GUI."

    def to_download_config(self, target_dir: Path | str | None = None) -> SapDownloadConfig:
        from itacamba_reportes.sap.exceptions import SapAutomationError
        raise SapAutomationError(self.source_note)


CONFIG_GD20 = ConfigDescargaGD20()
CONFIG_QUERY = ConfigDescargaQuery()
CONFIG_CARTERA = ConfigDescargaCartera()


@dataclass(slots=True)
class SapDownloadConfig:
    transaction: str
    ledger: str | None = None
    variant: str | None = None
    sociedad: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    period_low: str | int | None = None
    period_high: str | int | None = None
    year_low: str | int | None = None
    year_high: str | int | None = None
    layout_name: str | None = None
    layout_row: int | None = None
    export_filename: str = "EXPORT.xlsx"
    target_dir: Path | str | None = None

    @classmethod
    def for_gd20(
        cls,
        transaction: str = "gd20",
        ledger: str = "VC",
        variant: str = "BOT_GD20",
        period: str | int | None = None,
        year: str | int | None = None,
        layout_name: str | None = "//AVRILGD20",
        layout_row: int | None = None,
        export_filename: str = "GD20.xlsx",
        target_dir: Path | str | None = None,
    ) -> SapDownloadConfig:
        return cls(
            transaction=transaction,
            ledger=ledger,
            variant=variant,
            period_low=period,
            period_high=period,
            year_low=year,
            layout_name=layout_name,
            layout_row=layout_row,
            export_filename=export_filename,
            target_dir=target_dir,
        )

    @classmethod
    def for_query(
        cls,
        transaction: str = "ZVCSD381",
        sociedad: str = "4253",
        date_from: str | None = None,
        date_to: str | None = None,
        variant: str | None = "/IM",
        period: str | int | None = None,
        layout_row: int | None = None,
        export_filename: str = "QUERY.xlsx",
        target_dir: Path | str | None = None,
    ) -> SapDownloadConfig:
        return cls(
            transaction=transaction,
            sociedad=sociedad,
            date_from=date_from,
            date_to=date_to,
            variant=variant,
            period_low=period,
            period_high=period,
            layout_row=layout_row,
            export_filename=export_filename,
            target_dir=target_dir,
        )
