from __future__ import annotations

import logging
from datetime import datetime
from sqlalchemy import BigInteger, Column, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Session

from itacamba_reportes.core.db.base import Base
from itacamba_reportes.core.db.connection import get_session

logger = logging.getLogger(__name__)


class PipelineExecutionModel(Base):
    __tablename__ = "pipeline_executions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_name = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)  # SUCCESS, FAILED
    rows_processed = Column(Integer, default=0)
    duration_seconds = Column(Numeric(10, 2), default=0)
    details = Column(Text, nullable=True)
    executed_at = Column(DateTime, nullable=False, default=func.now())


def record_execution(report_name: str, status: str, rows: int, duration: float, details: str = "") -> None:
    try:
        with get_session() as session:
            exec_log = PipelineExecutionModel(
                report_name=report_name,
                status=status,
                rows_processed=rows,
                duration_seconds=round(duration, 2),
                details=details,
            )
            session.add(exec_log)
    except Exception as exc:
        logger.warning("No se pudo registrar la ejecucion en BD: %s", exc)
