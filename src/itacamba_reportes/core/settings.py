from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TypeVar

from dotenv import load_dotenv

load_dotenv()

T = TypeVar("T")

_PROJECT_ROOT: Path = Path(__file__).resolve().parents[3]
PROJECT_ROOT: Path = _PROJECT_ROOT
STATE_PATH: Path = PROJECT_ROOT / "storage" / "state" / "pipeline_state.json"
LOG_PATH: Path = PROJECT_ROOT / "storage" / "logs"


def _get_env(name: str, default: Any = None, cast: Callable[[str], T] | None = None) -> Any:
    value = os.getenv(name, default)
    if value is None or value == "":
        return default
    if cast is None:
        return value
    try:
        return cast(value)
    except Exception as exc:
        raise ValueError(f"Valor invalido para variable de entorno '{name}': {value}") from exc


def _get_bool(name: str, default: str = "false") -> bool:
    value = str(os.getenv(name, default)).strip().lower()
    return value in {"1", "true", "yes", "y", "on"}


class EnvConfig:
    PROJECT_ROOT: Path = _PROJECT_ROOT

    _default_data_path = str(_PROJECT_ROOT / "storage" / "input")
    _candidates = [
        os.getenv("DATA_PATH"),
        r"C:\Users\joseg_iog5jdg\OneDrive - Tecorp\Documentos ITACAMBA\Archivos",
        r"C:\Users\joseg_iog5jdg\OneDrive - Tecorp\Documentos ITACAMBA",
        r"C:\Users\joseg_iog5jdg\OneDrive - Tecorp\Documentos\Archivos",
        _default_data_path,
    ]
    _found_data_path = next((p for p in _candidates if p and Path(p).exists()), _default_data_path)

    DATA_PATH: Path = Path(_found_data_path)
    PROCESSED_PATH: Path = Path(_get_env("PROCESSED_PATH", default=str(_PROJECT_ROOT / "storage" / "processed")))
    ARCHIVE_PATH: Path = Path(_get_env("ARCHIVE_PATH", default=str(_PROJECT_ROOT / "storage" / "archive")))
    LOG_PATH: Path = Path(_get_env("LOG_PATH", default=str(LOG_PATH)))

    _default_export = DATA_PATH / "reports" if (DATA_PATH / "reports").exists() else _PROJECT_ROOT / "storage" / "exports"
    _env_export = os.getenv("EXPORT_PATH")
    if _env_export:
        try:
            p = Path(_env_export)
            if not p.exists() and not p.parent.exists():
                _env_export = None
        except Exception:
            _env_export = None

    EXPORT_PATH: Path = Path(_env_export or str(_default_export))

    DATABASE_URL: str | None = _get_env("DATABASE_URL")
    DB_SERVER: str | None = _get_env("DB_SERVER")
    DB_PORT: int = _get_env("DB_PORT", default=1433, cast=int)
    DB_NAME: str | None = _get_env("DB_NAME")
    DB_USER: str | None = _get_env("DB_USER")
    DB_PASSWORD: str | None = _get_env("DB_PASSWORD")
    DB_DRIVER: str = _get_env("DB_DRIVER", default="SQL Server")
    DB_TRUST_CERT: bool = _get_bool("DB_TRUST_CERT", default="yes")

    # SAP GUI Scripting & RPA
    SAP_LOGON_PATH: str = str(_get_env("SAP_LOGON_PATH", default=_get_env("SAP_URL", default=r"C:\Program Files (x86)\SAP\FrontEnd\SAPgui\saplogon.exe")))
    SAP_PROCESS: str = str(_get_env("SAP_PROCESS", default=_get_env("SAP_PROCCESS", default="saplogon.exe")))
    SAP_WINDOW_TITLE: str = str(_get_env("SAP_WINDOW_TITLE", default="SAP Logon 770"))
    SAP_AMBIENT: str = str(_get_env("SAP_AMBIENT", default="# -E05 - S4 RISE - Produção SSO"))
    SAP_SISTEMA: str = str(_get_env("SAP_SISTEMA", default="E05"))
    SAP_USER: str | None = _get_env("SAP_USER", default=_get_env("SAP_USUARIO"))
    SAP_PASSWORD: str | None = _get_env("SAP_PASSWORD")
    SAP_MANDANTE: str | None = _get_env("SAP_MANDANTE")
    SAP_IDIOMA: str | None = _get_env("SAP_IDIOMA")
