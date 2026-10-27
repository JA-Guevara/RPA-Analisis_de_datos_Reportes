from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from itacamba_reportes.core.settings import STATE_PATH

logger = logging.getLogger(__name__)


def compute_file_signature(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    stat = path.stat()
    try:
        with open(path, "rb") as f:
            head = f.read(1024 * 1024)
            if stat.st_size > 1024 * 1024:
                f.seek(max(0, stat.st_size - 1024 * 1024))
                tail = f.read(1024 * 1024)
            else:
                tail = b""
        quick_hash = hashlib.md5(head + tail).hexdigest()
    except Exception:
        quick_hash = ""

    return {
        "size": stat.st_size,
        "mtime": stat.st_mtime,
        "hash": quick_hash,
    }


def load_pipeline_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {}
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("No se pudo leer pipeline_state.json: %s", exc)
        return {}


def save_pipeline_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as exc:
        logger.warning("No se pudo guardar pipeline_state.json: %s", exc)


def has_file_changed(key: str, file_path: Path) -> bool:
    if not file_path.exists():
        return True
    state = load_pipeline_state()
    stored_sig = state.get("files", {}).get(key)
    if not stored_sig:
        return True
    current_sig = compute_file_signature(file_path)
    return current_sig != stored_sig


def save_file_signature(key: str, file_path: Path) -> None:
    if not file_path.exists():
        return
    state = load_pipeline_state()
    if "files" not in state:
        state["files"] = {}
    state["files"][key] = compute_file_signature(file_path)
    save_pipeline_state(state)


def clear_pipeline_state() -> None:
    if STATE_PATH.exists():
        try:
            STATE_PATH.unlink()
            logger.info("Estado de pipeline_state.json reseteado exitosamente.")
        except Exception as exc:
            logger.warning("No se pudo eliminar pipeline_state.json: %s", exc)

