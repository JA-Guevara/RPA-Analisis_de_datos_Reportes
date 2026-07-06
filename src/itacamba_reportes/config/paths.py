"""Rutas de datos del proyecto, derivadas del entorno (.env)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from itacamba_reportes.config.env_config import EnvConfig


@dataclass(frozen=True, slots=True)
class DataPaths:

    inbox: Path
    processed: Path
    archive: Path
    exports: Path

    @classmethod
    def from_env(cls) -> "DataPaths":
        return cls(
            inbox=EnvConfig.DATA_PATH,
            processed=EnvConfig.PROCESSED_PATH,
            archive=EnvConfig.ARCHIVE_PATH,
            exports=EnvConfig.EXPORT_PATH,
        )
