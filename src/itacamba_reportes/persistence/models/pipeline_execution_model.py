"""Tabla pipeline_executions - bitácora de cada corrida del bot.

Cada ejecución de un pipeline registra UN row aquí. Funciones:
  - Trazabilidad: int_ventas_bi.source_execution_id apunta a este id.
  - Auditoría: saber qué corrida insertó/modificó qué.
  - Rollback selectivo: borrar registros de una corrida específica.
  - Métricas: rows_inserted, rows_versioned, rows_rescued, etc.

Granularidad: 1 fila por (pipeline_name + start_time). Si una corrida falla,
se queda en status='FAILED' con error_message para diagnóstico.
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
)

from itacamba_reportes.persistence.base import Base


class PipelineExecutionModel(Base):
    __tablename__ = "pipeline_executions"
    __table_args__ = (
        Index("ix_pipeline_executions_pipeline_started",
              "pipeline_name", "started_at"),
    )

    id              = Column(String(36), primary_key=True)  # UUID4
    pipeline_name   = Column(String(50), nullable=False)
    started_at      = Column(DateTime, nullable=False)
    finished_at     = Column(DateTime, nullable=True)
    status          = Column(String(20), nullable=False, default="RUNNING")
    # RUNNING, SUCCESS, FAILED, ROLLED_BACK

    source_files    = Column(Text, nullable=True)   # JSON: {gd20: {path, hash, mtime}}
    rows_processed  = Column(Integer, nullable=True)
    rows_inserted   = Column(Integer, nullable=True)  # nuevos docs v1
    rows_updated    = Column(Integer, nullable=True)  # rescates in-place
    rows_skipped    = Column(Integer, nullable=True)  # sin cambios (idempotente)
    rows_versioned  = Column(Integer, nullable=True)  # SAP corrigió → SCD2
    rows_rescued    = Column(Integer, nullable=True)  # CD pasó de OTROS a real
    error_message   = Column(Text, nullable=True)
    force_rebuild   = Column(Boolean, nullable=False, default=False)
