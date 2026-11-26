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


def _resolve_data_path() -> Path:
    default_data_path = str(_PROJECT_ROOT / "storage" / "input")
    env_dinamicos = os.getenv("PATH_INSUMOS_DINAMICOS")
    parent_from_dinamicos = str(Path(env_dinamicos).parent) if env_dinamicos else None
    candidates = [
        os.getenv("DATA_PATH"),
        parent_from_dinamicos,
        r"C:\Users\joseg_iog5jdg\OneDrive - Tecorp\Documentos ITACAMBA\Archivos",
        r"C:\Users\joseg_iog5jdg\OneDrive - Tecorp\Documentos ITACAMBA",
        r"C:\Users\joseg_iog5jdg\OneDrive - Tecorp\Documentos\Archivos",
        default_data_path,
    ]
    found = next((p for p in candidates if p and Path(p).exists()), default_data_path)
    return Path(found)


def _resolve_export_path(data_path: Path) -> Path:
    default_export = data_path / "reports" if (data_path / "reports").exists() else _PROJECT_ROOT / "storage" / "exports"
    env_export = os.getenv("EXPORT_PATH") or os.getenv("PATH_REPORTES_SALIDA")
    if env_export:
        try:
            p = Path(env_export)
            if not p.exists() and not p.parent.exists():
                env_export = None
        except Exception:
            env_export = None
    return Path(env_export or str(default_export))


class EnvConfig:
    PROJECT_ROOT: Path = _PROJECT_ROOT

    DATA_PATH: Path = _resolve_data_path()
    PROCESSED_PATH: Path = Path(_get_env("PROCESSED_PATH", default=str(_PROJECT_ROOT / "storage" / "processed")))
    ARCHIVE_PATH: Path = Path(_get_env("ARCHIVE_PATH", default=str(_PROJECT_ROOT / "storage" / "archive")))
    LOG_PATH: Path = Path(_get_env("LOG_PATH", default=str(LOG_PATH)))
    EXPORT_PATH: Path = _resolve_export_path(DATA_PATH)

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
    SAP_SISTEMA: str = str(_get_env("SAP_SISTEMA", default=_get_env("SAP_SYSTEM", default="E05")))
    SAP_USER: str | None = _get_env("SAP_USER", default=_get_env("SAP_USUARIO"))
    SAP_PASSWORD: str | None = _get_env("SAP_PASSWORD")
    SAP_MANDANTE: str | None = _get_env("SAP_MANDANTE")
    SAP_IDIOMA: str | None = _get_env("SAP_IDIOMA")

    @classmethod
    def reload(cls, env_file: Path | str | None = None) -> None:
        if env_file:
            load_dotenv(env_file, override=True)
        else:
            load_dotenv(override=True)
        cls.DATA_PATH = _resolve_data_path()
        cls.PROCESSED_PATH = Path(_get_env("PROCESSED_PATH", default=str(_PROJECT_ROOT / "storage" / "processed")))
        cls.ARCHIVE_PATH = Path(_get_env("ARCHIVE_PATH", default=str(_PROJECT_ROOT / "storage" / "archive")))
        cls.LOG_PATH = Path(_get_env("LOG_PATH", default=str(LOG_PATH)))
        cls.EXPORT_PATH = _resolve_export_path(cls.DATA_PATH)
        cls.DATABASE_URL = _get_env("DATABASE_URL")
        cls.DB_SERVER = _get_env("DB_SERVER")
        cls.DB_PORT = _get_env("DB_PORT", default=1433, cast=int)
        cls.DB_NAME = _get_env("DB_NAME")
        cls.DB_USER = _get_env("DB_USER")
        cls.DB_PASSWORD = _get_env("DB_PASSWORD")
        cls.DB_DRIVER = _get_env("DB_DRIVER", default="SQL Server")
        cls.DB_TRUST_CERT = _get_bool("DB_TRUST_CERT", default="yes")
        cls.SAP_LOGON_PATH = str(_get_env("SAP_LOGON_PATH", default=_get_env("SAP_URL", default=r"C:\Program Files (x86)\SAP\FrontEnd\SAPgui\saplogon.exe")))
        cls.SAP_PROCESS = str(_get_env("SAP_PROCESS", default=_get_env("SAP_PROCCESS", default="saplogon.exe")))
        cls.SAP_WINDOW_TITLE = str(_get_env("SAP_WINDOW_TITLE", default="SAP Logon 770"))
        cls.SAP_AMBIENT = str(_get_env("SAP_AMBIENT", default="# -E05 - S4 RISE - Produção SSO"))
        cls.SAP_SISTEMA = str(_get_env("SAP_SISTEMA", default=_get_env("SAP_SYSTEM", default="E05")))
        cls.SAP_USER = _get_env("SAP_USER", default=_get_env("SAP_USUARIO"))
        cls.SAP_PASSWORD = _get_env("SAP_PASSWORD")
        cls.SAP_MANDANTE = _get_env("SAP_MANDANTE")
        cls.SAP_IDIOMA = _get_env("SAP_IDIOMA")
