"""State tracker para detectar cambios en archivos de entrada.

Persiste un "fingerprint" (mtime + size) por dataset en un JSON local.
Permite saltar pipelines cuando el archivo fuente no ha cambiado.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FileFingerprint:
    path: str
    mtime: float
    size: int

    @classmethod
    def from_path(cls, path: Path) -> "FileFingerprint":
        stat = path.stat()
        return cls(
            path=str(path),
            mtime=stat.st_mtime,
            size=stat.st_size,
        )


@dataclass(frozen=True, slots=True)
class StateEntry:
    fingerprint: FileFingerprint
    last_run_at: str
    rows_loaded: dict[str, int]


class FileStateTracker:
    """Lee/escribe el state JSON. Una clave por dataset."""

    def __init__(self, state_path: Path) -> None:
        self._path = state_path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def get(self, dataset: str) -> StateEntry | None:
        if not self._path.exists():
            return None
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("state ilegible (%s), tratando como vacio: %s", self._path, exc)
            return None
        entry = data.get(dataset)
        if not entry:
            return None
        return StateEntry(
            fingerprint=FileFingerprint(**entry["fingerprint"]),
            last_run_at=entry["last_run_at"],
            rows_loaded=entry.get("rows_loaded", {}),
        )

    def save(self, dataset: str, entry: StateEntry) -> None:
        data = {}
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                data = {}
        data[dataset] = {
            "fingerprint": asdict(entry.fingerprint),
            "last_run_at": entry.last_run_at,
            "rows_loaded": entry.rows_loaded,
        }
        self._path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("state guardado: %s -> %s", dataset, self._path.name)

    @staticmethod
    def has_changed(actual: FileFingerprint, previous: FileFingerprint | None) -> bool:
        if previous is None:
            return True
        return (
            actual.path != previous.path
            or actual.mtime != previous.mtime
            or actual.size != previous.size
        )
