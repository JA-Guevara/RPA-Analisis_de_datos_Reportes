from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, TypeVar

from dotenv import load_dotenv

load_dotenv()

T = TypeVar("T")

_PROJECT_ROOT: Path = Path(__file__).resolve().parents[3]


def _get_env(
    name: str,
    default: Any = None,
    cast: Callable[[str], T] | None = None,
) -> Any:
    value = os.getenv(name, default)
    if value is None or value == "":
        return default
    if cast is None:
        return value
    try:
        return cast(value)
    except Exception as exc:
        raise ValueError(
            f"Valor invalido para variable de entorno '{name}': {value}",
        ) from exc


def _get_bool(name: str, default: str = "false") -> bool:
    value = str(os.getenv(name, default)).strip().lower()
    return value in {"1", "true", "yes", "y", "on"}


class EnvConfig:

    PROJECT_ROOT: Path = _PROJECT_ROOT

    DATA_PATH: Path = Path(
        _get_env("DATA_PATH", default=str(_PROJECT_ROOT / "storage" / "input")),
    )
    PROCESSED_PATH: Path = Path(
        _get_env("PROCESSED_PATH", default=str(_PROJECT_ROOT / "storage" / "processed")),
    )
    ARCHIVE_PATH: Path = Path(
        _get_env("ARCHIVE_PATH", default=str(_PROJECT_ROOT / "storage" / "archive")),
    )
    LOG_PATH: Path = Path(
        _get_env("LOG_PATH", default=str(_PROJECT_ROOT / "storage" / "logs")),
    )
    EXPORT_PATH: Path = Path(
        _get_env("EXPORT_PATH", default=str(_PROJECT_ROOT / "storage" / "exports")),
    )

    # URL de conexión completa (opcional). Si está definida tiene prioridad
    # sobre las variables sueltas DB_*. Admite placeholders {DB_*} que se
    # resuelven en build_connection_url().
    DATABASE_URL: str | None = _get_env("DATABASE_URL")

    DB_SERVER: str | None = _get_env("DB_SERVER")
    DB_NAME: str | None = _get_env("DB_NAME")
    DB_USER: str | None = _get_env("DB_USER")
    DB_PASSWORD: str | None = _get_env("DB_PASSWORD")
    DB_PORT: int = _get_env("DB_PORT", default="1433", cast=int)
    DB_DRIVER: str | None = _get_env("DB_DRIVER")
    DB_TRUST_CERT: bool = _get_bool("DB_TRUST_CERT", default="yes")

    LOG_LEVEL: str = _get_env("LOG_LEVEL", default="INFO")
    LOG_MAX_MB: int = _get_env("LOG_MAX_MB", default="10", cast=int)
    LOG_BACKUP_COUNT: int = _get_env("LOG_BACKUP_COUNT", default="5", cast=int)
    LOG_TO_CONSOLE: bool = _get_bool("LOG_TO_CONSOLE", default="true")
    LOG_COLORS: bool = _get_bool("LOG_COLORS", default="true")


_REQUIRED_DB_FIELDS: tuple[str, ...] = (
    "DB_SERVER",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
    "DB_DRIVER",
)


def validate_db_config() -> None:
    # Si hay DATABASE_URL explícita no exigimos las variables sueltas.
    if EnvConfig.DATABASE_URL:
        return
    missing = [name for name in _REQUIRED_DB_FIELDS if not getattr(EnvConfig, name)]
    if missing:
        raise ValueError(
            f"Config DB incompleta: define DATABASE_URL o las variables "
            f"sueltas (faltan: {', '.join(missing)})",
        )


def validate_data_paths() -> None:
    if not EnvConfig.DATA_PATH.exists():
        raise FileNotFoundError(
            f"DATA_PATH no existe: {EnvConfig.DATA_PATH}",
        )
    for path in (
        EnvConfig.PROCESSED_PATH,
        EnvConfig.ARCHIVE_PATH,
        EnvConfig.LOG_PATH,
        EnvConfig.EXPORT_PATH,
    ):
        path.mkdir(parents=True, exist_ok=True)


def validate_config() -> None:
    validate_data_paths()
    validate_db_config()
    # (export usa EXPORT_PATH, creado en validate_data_paths)
