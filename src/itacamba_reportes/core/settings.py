from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TypeVar

from dotenv import dotenv_values, load_dotenv

_PROJECT_ROOT: Path = Path(__file__).resolve().parents[3]
_DEFAULT_ENV_FILE: Path = _PROJECT_ROOT / ".env"
if _DEFAULT_ENV_FILE.exists():
    load_dotenv(_DEFAULT_ENV_FILE)
else:
    load_dotenv()

T = TypeVar("T")

PROJECT_ROOT: Path = _PROJECT_ROOT
STATE_PATH: Path = PROJECT_ROOT / "storage" / "state" / "pipeline_state.json"
LOG_PATH: Path = PROJECT_ROOT / "storage" / "logs"

_SYNCED_ENV_KEYS: tuple[str, ...] = (
    "PATH_INSUMOS_FIJOS",
    "PATH_INSUMOS_DINAMICOS",
    "PATH_REPORTES_SALIDA",
    "PATH_LOGS_STORAGE",
    "LOG_PATH",
    "DATA_PATH",
    "EXPORT_PATH",
    "SAP_LOGON_PATH",
    "SAP_URL",
    "SAP_AMBIENT",
    "SAP_SISTEMA",
    "SAP_SYSTEM",
    "SAP_USER",
    "SAP_USUARIO",
    "SAP_PASSWORD",
    "SAP_MANDANTE",
    "SAP_IDIOMA",
    "DATABASE_URL",
    "DB_SERVER",
    "DB_PORT",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
    "DB_DRIVER",
    "DB_TRUST_CERT",
    "MAIL_WEBHOOK_URL",
    "MAIL_WEBHOOK_KEY",
    "MAIL_WEBHOOK_TIMEOUT",
    "MAIL_SOPORTE",
    "MAIL_COPIA_SOPORTE",
    "MAIL_GENERAL",
    "MAIL_COPIA_GENERAL",
    "MAIL_ALERT_ON_ERROR",
)


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


def _resolve_env_path(key: str) -> Path | None:
    value = (os.getenv(key) or "").strip()
    return Path(value) if value else None


class EnvConfig:
    PROJECT_ROOT: Path = _PROJECT_ROOT

    # Las 3 rutas operativas deben definirse explicitamente en .env (cero rutas fijas ni respaldos locales).
    DATA_PATH: Path | None = None
    FIXED_INPUTS_PATH: Path | None = _resolve_env_path("PATH_INSUMOS_FIJOS")
    DYNAMIC_INPUTS_PATH: Path | None = _resolve_env_path("PATH_INSUMOS_DINAMICOS")
    LOG_PATH: Path = _resolve_env_path("PATH_LOGS_STORAGE") or _resolve_env_path("LOG_PATH") or LOG_PATH
    REPORTS_OUTPUT_PATH: Path | None = _resolve_env_path("PATH_REPORTES_SALIDA")
    EXPORT_PATH: Path | None = REPORTS_OUTPUT_PATH

    DATABASE_URL: str | None = _get_env("DATABASE_URL")
    DB_SERVER: str | None = _get_env("DB_SERVER")
    DB_PORT: int = _get_env("DB_PORT", default=1433, cast=int)
    DB_NAME: str | None = _get_env("DB_NAME")
    DB_USER: str | None = _get_env("DB_USER")
    DB_PASSWORD: str | None = _get_env("DB_PASSWORD")
    DB_DRIVER: str = _get_env("DB_DRIVER", default="SQL Server")
    DB_TRUST_CERT: bool = _get_bool("DB_TRUST_CERT", default="yes")

    # SAP GUI Scripting & RPA (definidos en .env)
    SAP_LOGON_PATH: str = str(_get_env("SAP_LOGON_PATH", default=_get_env("SAP_URL", default="")) or "").strip()
    SAP_AMBIENT: str = str(_get_env("SAP_AMBIENT", default="") or "").strip()
    SAP_SISTEMA: str = str(_get_env("SAP_SISTEMA", default=_get_env("SAP_SYSTEM", default="")) or "").strip()
    SAP_USER: str | None = _get_env("SAP_USER", default=_get_env("SAP_USUARIO"))
    SAP_PASSWORD: str | None = _get_env("SAP_PASSWORD")
    SAP_MANDANTE: str | None = _get_env("SAP_MANDANTE")
    SAP_IDIOMA: str | None = _get_env("SAP_IDIOMA")

    # Notificaciones por Webhook Power Automate (compatible con Bot Itacamba v3.0)
    MAIL_WEBHOOK_URL: str | None = _get_env("MAIL_WEBHOOK_URL")
    MAIL_WEBHOOK_KEY: str | None = _get_env("MAIL_WEBHOOK_KEY")
    MAIL_WEBHOOK_TIMEOUT: int = _get_env("MAIL_WEBHOOK_TIMEOUT", default=30, cast=int)
    MAIL_SOPORTE: str | None = _get_env("MAIL_SOPORTE")
    MAIL_COPIA_SOPORTE: str | None = _get_env("MAIL_COPIA_SOPORTE")
    MAIL_GENERAL: str | None = _get_env("MAIL_GENERAL")
    MAIL_COPIA_GENERAL: str | None = _get_env("MAIL_COPIA_GENERAL")
    MAIL_ALERT_ON_ERROR: bool = _get_bool("MAIL_ALERT_ON_ERROR", default="yes")

    @classmethod
    def require_fixed_inputs_path(cls) -> Path:
        if cls.FIXED_INPUTS_PATH is None:
            raise ValueError("La variable PATH_INSUMOS_FIJOS no está definida en el archivo .env.")
        return cls.FIXED_INPUTS_PATH

    @classmethod
    def require_dynamic_inputs_path(cls) -> Path:
        if cls.DYNAMIC_INPUTS_PATH is None:
            raise ValueError("La variable PATH_INSUMOS_DINAMICOS no está definida en el archivo .env.")
        return cls.DYNAMIC_INPUTS_PATH

    @classmethod
    def require_reports_output_path(cls) -> Path:
        if cls.REPORTS_OUTPUT_PATH is None:
            raise ValueError("La variable PATH_REPORTES_SALIDA no está definida en el archivo .env.")
        return cls.REPORTS_OUTPUT_PATH

    @classmethod
    def sync_from_env_file(cls, env_file: Path | str | None = None) -> None:
        target_env = Path(env_file) if env_file else _DEFAULT_ENV_FILE
        disk_values = dotenv_values(target_env) if target_env.exists() else {}
        for key in _SYNCED_ENV_KEYS:
            val = disk_values.get(key)
            if val is None or not str(val).strip():
                os.environ.pop(key, None)
        cls.reload(target_env if target_env.exists() else None)

    @classmethod
    def reload(cls, env_file: Path | str | None = None) -> None:
        target_env = Path(env_file) if env_file else _DEFAULT_ENV_FILE
        if target_env.exists():
            load_dotenv(target_env, override=True)
        cls.DATA_PATH = None
        cls.FIXED_INPUTS_PATH = _resolve_env_path("PATH_INSUMOS_FIJOS")
        cls.DYNAMIC_INPUTS_PATH = _resolve_env_path("PATH_INSUMOS_DINAMICOS")
        cls.LOG_PATH = _resolve_env_path("PATH_LOGS_STORAGE") or _resolve_env_path("LOG_PATH") or (_PROJECT_ROOT / "storage" / "logs")
        cls.REPORTS_OUTPUT_PATH = _resolve_env_path("PATH_REPORTES_SALIDA")
        cls.EXPORT_PATH = cls.REPORTS_OUTPUT_PATH
        cls.DATABASE_URL = _get_env("DATABASE_URL")
        cls.DB_SERVER = _get_env("DB_SERVER")
        cls.DB_PORT = _get_env("DB_PORT", default=1433, cast=int)
        cls.DB_NAME = _get_env("DB_NAME")
        cls.DB_USER = _get_env("DB_USER")
        cls.DB_PASSWORD = _get_env("DB_PASSWORD")
        cls.DB_DRIVER = _get_env("DB_DRIVER", default="SQL Server")
        cls.DB_TRUST_CERT = _get_bool("DB_TRUST_CERT", default="yes")
        cls.SAP_LOGON_PATH = str(_get_env("SAP_LOGON_PATH", default=_get_env("SAP_URL", default="")) or "").strip()
        cls.SAP_AMBIENT = str(_get_env("SAP_AMBIENT", default="") or "").strip()
        cls.SAP_SISTEMA = str(_get_env("SAP_SISTEMA", default=_get_env("SAP_SYSTEM", default="")) or "").strip()
        cls.SAP_USER = _get_env("SAP_USER", default=_get_env("SAP_USUARIO"))
        cls.SAP_PASSWORD = _get_env("SAP_PASSWORD")
        cls.SAP_MANDANTE = _get_env("SAP_MANDANTE")
        cls.SAP_IDIOMA = _get_env("SAP_IDIOMA")
        cls.MAIL_WEBHOOK_URL = _get_env("MAIL_WEBHOOK_URL")
        cls.MAIL_WEBHOOK_KEY = _get_env("MAIL_WEBHOOK_KEY")
        cls.MAIL_WEBHOOK_TIMEOUT = _get_env("MAIL_WEBHOOK_TIMEOUT", default=30, cast=int)
        cls.MAIL_SOPORTE = _get_env("MAIL_SOPORTE")
        cls.MAIL_COPIA_SOPORTE = _get_env("MAIL_COPIA_SOPORTE")
        cls.MAIL_GENERAL = _get_env("MAIL_GENERAL")
        cls.MAIL_COPIA_GENERAL = _get_env("MAIL_COPIA_GENERAL")
        cls.MAIL_ALERT_ON_ERROR = _get_bool("MAIL_ALERT_ON_ERROR", default="yes")
