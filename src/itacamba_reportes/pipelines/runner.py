"""Runner común de pipelines file-driven.

Encapsula el ciclo que TODOS los pipelines con archivo fuente repiten:

    fingerprint → skip si no cambió → stages() → save state → summary

Cada pipeline aporta solo sus stages (una función que devuelve el
conteo de filas por tabla). El formato de pipeline_state.json y los
mensajes de log se preservan tal cual eran.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from time import perf_counter

from itacamba_reportes.pipelines.file_state import (
    FileFingerprint,
    FileStateTracker,
    StateEntry,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """Resultado único para todos los pipelines.

    `rows` usa las mismas claves que rows_loaded en pipeline_state.json
    (p. ej. {"stg_cartera": 1200, "int_cartera": 1180}).
    """

    rows: dict[str, int]
    duration_seconds: float
    skipped: bool = False
    export_path: str | None = None

    def total_rows(self) -> int:
        return sum(self.rows.values())


def run_file_pipeline(
    *,
    name: str,
    dataset_key: str,
    source_path: Path,
    state_tracker: FileStateTracker,
    force: bool,
    stages: Callable[[], dict[str, int]],
    post_state: Callable[[], str | None] | None = None,
) -> PipelineResult:
    """Ejecuta un pipeline con change-detection por fingerprint.

    Args:
        name:        etiqueta para logs (p. ej. "CARTERA").
        dataset_key: clave en pipeline_state.json.
        stages:      ejecuta las etapas y devuelve filas por tabla.
        post_state:  opcional, corre DESPUÉS de guardar el state
                     (p. ej. export a Excel); devuelve la ruta exportada.
    """
    t0 = perf_counter()
    logger.info("=== %s pipeline start (force=%s) ===", name, force)

    if not source_path.exists():
        raise FileNotFoundError(f"Archivo {name} no encontrado: {source_path}")

    actual = FileFingerprint.from_path(source_path)
    previous = state_tracker.get(dataset_key)
    previous_fp = previous.fingerprint if previous else None

    if not force and not state_tracker.has_changed(actual, previous_fp):
        logger.info(
            "Sin cambios en %s desde el ultimo run (%s). Skip.",
            source_path.name,
            previous.last_run_at if previous else "?",
        )
        return PipelineResult(
            rows=dict(previous.rows_loaded) if previous else {},
            duration_seconds=perf_counter() - t0,
            skipped=True,
        )

    if previous_fp is None:
        logger.info("Sin state previo, primera corrida")
    else:
        logger.info(
            "Cambios detectados (mtime: %s -> %s, size: %d -> %d)",
            previous_fp.mtime, actual.mtime,
            previous_fp.size, actual.size,
        )

    rows = stages()

    state_tracker.save(
        dataset_key,
        StateEntry(
            fingerprint=actual,
            last_run_at=datetime.now().isoformat(timespec="seconds"),
            rows_loaded=rows,
        ),
    )

    export_path = post_state() if post_state is not None else None

    duration = perf_counter() - t0
    result = PipelineResult(rows=rows, duration_seconds=duration,
                            export_path=export_path)
    log_summary(name, result)
    return result


def log_summary(name: str, result: PipelineResult) -> None:
    sep = "=" * 72
    logger.info(sep)
    logger.info("%s PIPELINE - RESUMEN", name)
    logger.info(sep)
    for table, n in result.rows.items():
        logger.info("%-18s %d filas", table + ":", n)
    if result.export_path:
        logger.info("export:            %s", result.export_path)
    logger.info("Duracion:          %.2fs", result.duration_seconds)
    logger.info(sep)
