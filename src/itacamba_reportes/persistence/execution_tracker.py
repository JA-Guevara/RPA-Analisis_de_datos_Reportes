"""Bitácora de ejecuciones del pipeline.

Cada llamada a un pipeline crea una entry en pipeline_executions con un UUID
único. int_ventas_bi.source_execution_id apunta a ese UUID, permitiendo
auditoría/rollback completos.

Uso típico:

    tracker = ExecutionTracker("gd20", force_rebuild=args.force_rebuild)
    with tracker.start() as execution_id:
        ...  # correr el pipeline
        tracker.record_metrics(inserted=N, updated=M, ...)
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from itacamba_reportes.persistence.engine import SessionLocal
from itacamba_reportes.persistence.session import get_session

logger = logging.getLogger(__name__)


@dataclass
class ExecutionMetrics:
    rows_processed: int = 0
    rows_inserted:  int = 0
    rows_updated:   int = 0
    rows_skipped:   int = 0
    rows_versioned: int = 0
    rows_rescued:   int = 0


@dataclass
class ExecutionTracker:
    pipeline_name: str
    force_rebuild: bool = False
    session_factory: Callable[[], Session] | None = None

    _execution_id: str = field(default="", init=False)
    _metrics: ExecutionMetrics = field(default_factory=ExecutionMetrics, init=False)
    _source_files: dict = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        if self.session_factory is None:
            self.session_factory = SessionLocal

    @property
    def execution_id(self) -> str:
        return self._execution_id

    def add_source_file(self, key: str, path: str,
                        size: int | None = None,
                        mtime: float | None = None,
                        sha: str | None = None) -> None:
        """Registra un archivo source con su fingerprint."""
        self._source_files[key] = {
            "path": path,
            "size": size,
            "mtime": mtime,
            "sha": sha,
        }

    def record_metrics(self, **kwargs: int) -> None:
        for k, v in kwargs.items():
            if hasattr(self._metrics, k):
                setattr(self._metrics, k, v)

    @contextmanager
    def start(self):
        """Context manager. Inserta row inicial, hace yield del execution_id,
        y al salir actualiza status y métricas (SUCCESS o FAILED)."""
        self._execution_id = str(uuid.uuid4())
        started_at = datetime.utcnow()

        insert_sql = text("""
            INSERT INTO pipeline_executions
              (id, pipeline_name, started_at, status, force_rebuild)
            VALUES
              (:id, :name, :started_at, 'RUNNING', :force_rebuild)
        """)
        with get_session(self.session_factory) as session:
            session.execute(insert_sql, {
                "id": self._execution_id,
                "name": self.pipeline_name,
                "started_at": started_at,
                "force_rebuild": self.force_rebuild,
            })
        logger.info(
            "Execution registered: pipeline=%s id=%s force_rebuild=%s",
            self.pipeline_name, self._execution_id, self.force_rebuild,
        )

        try:
            yield self._execution_id
            self._finish("SUCCESS")
        except Exception as e:
            self._finish("FAILED", error_message=str(e))
            raise

    def _finish(self, status: str, error_message: str | None = None) -> None:
        finished_at = datetime.utcnow()
        source_files_json = json.dumps(self._source_files) if self._source_files else None

        update_sql = text("""
            UPDATE pipeline_executions
            SET finished_at    = :finished_at,
                status         = :status,
                source_files   = :source_files,
                rows_processed = :rp,
                rows_inserted  = :ri,
                rows_updated   = :ru,
                rows_skipped   = :rs,
                rows_versioned = :rv,
                rows_rescued   = :rr,
                error_message  = :err
            WHERE id = :id
        """)
        with get_session(self.session_factory) as session:
            session.execute(update_sql, {
                "finished_at": finished_at,
                "status": status,
                "source_files": source_files_json,
                "rp": self._metrics.rows_processed,
                "ri": self._metrics.rows_inserted,
                "ru": self._metrics.rows_updated,
                "rs": self._metrics.rows_skipped,
                "rv": self._metrics.rows_versioned,
                "rr": self._metrics.rows_rescued,
                "err": error_message,
                "id": self._execution_id,
            })
        logger.info(
            "Execution %s finished status=%s metrics=%s",
            self._execution_id, status, self._metrics,
        )
