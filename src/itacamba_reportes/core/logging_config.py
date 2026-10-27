from __future__ import annotations

import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from itacamba_reportes.core.settings import EnvConfig

_configured = False


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    global _configured
    root_logger = logging.getLogger()
    app_logger = logging.getLogger("itacamba_reportes")

    if _configured:
        return app_logger

    log_dir = EnvConfig.LOG_PATH
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        print(f"[AVISO] No se pudo crear directorio de logs {log_dir}: {exc}")

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handlers: list[logging.Handler] = []

    # Handler 1: Consola
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    handlers.append(console_handler)

    # Handler 2: Archivo rotativo itacamba_reportes.log
    file_handlers: list[logging.Handler] = []
    try:
        main_log_file = log_dir / "itacamba_reportes.log"
        file_handler = RotatingFileHandler(
            str(main_log_file),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        handlers.append(file_handler)
        file_handlers.append(file_handler)

        # Handler 3: Archivo fechado diario ejecucion_YYYY-MM-DD.log
        today_str = datetime.now().strftime("%Y-%m-%d")
        daily_log_file = log_dir / f"ejecucion_{today_str}.log"
        daily_handler = logging.FileHandler(
            str(daily_log_file),
            mode="a",
            encoding="utf-8",
        )
        daily_handler.setFormatter(formatter)
        daily_handler.setLevel(level)
        handlers.append(daily_handler)
        file_handlers.append(daily_handler)
    except Exception as exc:
        print(f"[AVISO] No se pudieron inicializar archivos de log en {log_dir}: {exc}")

    # Configurar app logger
    app_logger.setLevel(level)
    app_logger.handlers.clear()
    for h in handlers:
        app_logger.addHandler(h)
    app_logger.propagate = False

    # Configurar alembic logger para guardar migraciones en los archivos de log
    alembic_logger = logging.getLogger("alembic")
    for fh in file_handlers:
        alembic_logger.addHandler(fh)

    # Configurar root logger
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    for h in handlers:
        root_logger.addHandler(h)

    _configured = True
    return app_logger
