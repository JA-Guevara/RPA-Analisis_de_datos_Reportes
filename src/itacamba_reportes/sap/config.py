"""Configuración dinámica de tareas y descargas de SAP GUI (puro valor dinámico).

En este archivo se definen ÚNICAMENTE las variables de negocio que cambian entre corridas
(códigos de transacción, libros ledger, variantes grabadas, períodos, fechas y nombres de archivo).
Los selectores técnicos y controles de SAP GUI residen de forma separada en `selectors.py`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


@dataclass(slots=True)
class ConfigDescargaGD20:
    """Parámetros dinámicos para la descarga de Ventas Contables (GD20 / BASE PANEL)."""

    transaction: str = "gd20"
    ledger: str = "VC"
    variant: str = "Prueba_GD20"
    period_low: str | int = 10
    period_high: str | int = 10
    layout_row: int = 16
    layout_name: str | None = "/DEFAULT"
    export_filename: str = "GD20.xlsx"

    def to_download_config(self, target_dir: Path | str | None = None) -> SapDownloadConfig:
        periodo = str(self.period_low).strip() if str(self.period_low).strip() else time.strftime("%m")
        return SapDownloadConfig(
            transaction=self.transaction,
            variant=self.variant or None,
            ledger=self.ledger or None,
            period_low=periodo,
            period_high=periodo,
            layout_row=self.layout_row,
            layout_name=self.layout_name or None,
            export_filename=self.export_filename,
            target_dir=target_dir,
        )


@dataclass(slots=True)
class ConfigDescargaQuery:
    """Parámetros dinámicos para la descarga de Despachos (Query / ZBCS).

    Edita los valores directamente en esta clase cuando tengas la parametrización final de SAP.
    Los campos vacíos ("") se ignoran automáticamente durante la ejecución sin generar errores.
    """

    transaction: str = "zbcs"
    ledger: str = ""                # <-- Ingresar libro/ledger si aplica (ej: "VC")
    variant: str = ""               # <-- Ingresar nombre de la variante grabada (ej: "IM")
    period_low: str | int = ""      # <-- Ingresar período inicio si aplica
    period_high: str | int = ""     # <-- Ingresar período fin si aplica
    layout_name: str = ""           # <-- Ingresar disposición ALV si aplica (ej: "/DESPACHOS")
    layout_row: int | None = None   # <-- Fila en la grilla ALV si aplica (ej: 16)
    date_from: str = ""             # <-- Fecha inicio (formato YYYY-MM-DD, ej: "2026-10-01")
    date_to: str = ""               # <-- Fecha fin (formato YYYY-MM-DD, ej: "2026-10-25")
    export_filename: str = "QUERY.xlsx"

    def to_download_config(self, target_dir: Path | str | None = None) -> SapDownloadConfig:
        return SapDownloadConfig(
            transaction=self.transaction,
            variant=self.variant.strip() or None if isinstance(self.variant, str) else self.variant,
            ledger=self.ledger.strip() or None if isinstance(self.ledger, str) else self.ledger,
            period_low=str(self.period_low).strip() or None if self.period_low != "" else None,
            period_high=str(self.period_high).strip() or None if self.period_high != "" else None,
            layout_name=self.layout_name.strip() or None if isinstance(self.layout_name, str) else self.layout_name,
            layout_row=self.layout_row,
            date_from=self.date_from.strip() or None if isinstance(self.date_from, str) else self.date_from,
            date_to=self.date_to.strip() or None if isinstance(self.date_to, str) else self.date_to,
            export_filename=self.export_filename,
            target_dir=target_dir,
        )


@dataclass(slots=True)
class ConfigDescargaCartera:
    """Parámetros dinámicos para la descarga de Cartera de Clientes & Cadena (ZSDI)."""

    transaction: str = "zsdi"
    ledger: str = ""
    variant: str = "CAD_CLIENTE"
    period_low: str | int = ""
    period_high: str | int = ""
    layout_name: str = "/CARTERA"
    layout_row: int | None = None
    date_from: str = ""
    date_to: str = ""
    export_filename: str = "CARTERA.xlsx"

    def to_download_config(self, target_dir: Path | str | None = None) -> SapDownloadConfig:
        return SapDownloadConfig(
            transaction=self.transaction,
            variant=self.variant.strip() or None if isinstance(self.variant, str) else self.variant,
            ledger=self.ledger.strip() or None if isinstance(self.ledger, str) else self.ledger,
            period_low=str(self.period_low).strip() or None if self.period_low != "" else None,
            period_high=str(self.period_high).strip() or None if self.period_high != "" else None,
            layout_name=self.layout_name.strip() or None if isinstance(self.layout_name, str) else self.layout_name,
            layout_row=self.layout_row,
            date_from=self.date_from.strip() or None if isinstance(self.date_from, str) else self.date_from,
            date_to=self.date_to.strip() or None if isinstance(self.date_to, str) else self.date_to,
            export_filename=self.export_filename,
            target_dir=target_dir,
        )


# ==============================================================================
# INSTANCIAS GLOBALES POR DEFECTO (CONFIGURACIÓN EDITABLE)
# ==============================================================================
CONFIG_GD20 = ConfigDescargaGD20()
CONFIG_QUERY = ConfigDescargaQuery()
CONFIG_CARTERA = ConfigDescargaCartera()


@dataclass(slots=True)
class SapDownloadConfig:
    """Objeto estándar de parámetros consumido por execute_download_report."""

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
