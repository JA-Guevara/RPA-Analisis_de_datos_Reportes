"""Mixins reusables para modelos SQLAlchemy."""

from __future__ import annotations

from sqlalchemy import Column, DateTime, func


class TimestampsMixin:
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
