from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from itacamba_reportes.config.env_config import EnvConfig


_LEVEL_COLORS: dict[int, str] = {
    logging.DEBUG:    "\033[36m",      # cyan
    logging.INFO:     "\033[32m",      # verde
    logging.WARNING:  "\033[33m",      # amarillo
    logging.ERROR:    "\033[31m",      # rojo
    logging.CRITICAL: "\033[97;41m",   # blanco/fondo rojo
}
_RESET = "\033[0m"


class _ColoredFormatter(logging.Formatter):
    """Formatter ANSI por nivel para la consola."""

    def format(self, record: logging.LogRecord) -> str:
        color = _LEVEL_COLORS.get(record.levelno, "")
        record.levelname = f"{color}{record.levelname}{_RESET}"
        return super().format(record)


def _supports_color() -> bool:
    if not sys.stdout.isatty():
        return False
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            return True
        except Exception:
            return False
    return True


def setup_logging(
    log_dir: Path | None = None,
    log_file_name: str = "itacamba_reportes.log",
) -> logging.Logger:
    root = logging.getLogger()

    if getattr(root, "_configured", False):
        return logging.getLogger("itacamba_reportes")

    log_dir = log_dir or EnvConfig.LOG_PATH
    log_dir.mkdir(parents=True, exist_ok=True)

    level_name = (EnvConfig.LOG_LEVEL or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    root.setLevel(level)

    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    file_handler = RotatingFileHandler(
        log_dir / log_file_name,
        maxBytes=EnvConfig.LOG_MAX_MB * 1024 * 1024,
        backupCount=EnvConfig.LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    root.addHandler(file_handler)

    if EnvConfig.LOG_TO_CONSOLE:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        if EnvConfig.LOG_COLORS and _supports_color():
            console_handler.setFormatter(_ColoredFormatter(fmt, datefmt=datefmt))
        else:
            console_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
        root.addHandler(console_handler)

    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    root._configured = True

    logger = logging.getLogger("itacamba_reportes")
    logger.info(
        "Logger inicializado | level=%s | file=%s",
        level_name,
        log_dir / log_file_name,
    )
    return logger
