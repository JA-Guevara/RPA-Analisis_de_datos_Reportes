"""Control de corrida — el mismo control para TODOS los reportes.

Unifica lo que antes solo tenía VENTAS BI (auditoría + hashes) en un
concepto simple aplicable a cualquier pipeline:

  resumen_corrida(df, monitoreo)  →  dict con:
      filas, columnas, hash_contenido (sha256 estable del dataframe:
      si dos corridas producen bytes idénticos, mismo hash) y el % de
      valores "default" por columna monitoreada con estado OK/ALERTA.

  registrar_en_bd(pipeline, resumen, ...) → fila en pipeline_executions
      (misma bitácora que usa el SCD2 de ventas), a prueba de fallos:
      si la BD no está disponible NO rompe el pipeline, solo avisa.

El QUÉ monitorear (columnas, literales default, umbrales) vive en el
config.yaml de cada reporte (bloque `control:`) — datos, no código.

Nota de diseño: los despachos son fotos del mes (TRUNCATE+INSERT); un
hash POR FILA como el de ventas solo aporta si se guarda historia
(SCD2). El hash DE CONTENIDO por corrida da el control equivalente
(detectar si algo cambió entre corridas) sin duplicar el mecanismo de
historia. Si negocio pide historia de despachos, se replica el SCD2 de
ventas — decisión de negocio documentada, no limitación técnica.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


def hash_contenido(df: pd.DataFrame) -> str:
    """SHA-256 determinístico del contenido (independiente del orden de filas)."""
    if df.empty:
        return "vacio"
    s = df.astype("string").fillna("<NA>")
    s = s.sort_values(list(s.columns), na_position="last").reset_index(drop=True)
    datos = s.to_csv(index=False).encode("utf-8")
    return hashlib.sha256(datos).hexdigest()[:16]


def resumen_corrida(
    df: pd.DataFrame,
    monitoreo: dict[str, Any] | None = None,
    reporte: str = "",
) -> dict[str, Any]:
    """Resumen de control de una corrida.

    monitoreo (del bloque `control:` del config.yaml del reporte):
        columnas:
          equipo:        {defaults: ["No encontrado"], umbral_pct: 15}
          semana:        {defaults: ["<NA>"], umbral_pct: 5}
    """
    resumen: dict[str, Any] = {
        "reporte": reporte,
        "fecha_corrida": datetime.now().isoformat(timespec="seconds"),
        "filas": len(df),
        "columnas": len(df.columns),
        "hash_contenido": hash_contenido(df),
        "calidad": [],
        "alertas": 0,
    }
    columnas = (monitoreo or {}).get("columnas") or {}
    for col, regla in columnas.items():
        if col not in df.columns or len(df) == 0:
            continue
        defaults = [str(v) for v in (regla.get("defaults") or [])]
        s = df[col].astype("string")
        n = int(s.isin(defaults).sum())
        if "<NA>" in defaults:
            n += int(s.isna().sum())
        pct = round(100.0 * n / len(df), 1)
        umbral = float(regla.get("umbral_pct", 100))
        estado = "OK" if pct <= umbral else "ALERTA"
        if estado == "ALERTA":
            resumen["alertas"] += 1
            logger.warning(
                "CONTROL %s: %s con %.1f%% de defaults %s (umbral %.0f%%)",
                reporte, col, pct, defaults, umbral,
            )
        resumen["calidad"].append({
            "columna": col, "defaults": ", ".join(defaults),
            "sin_match_pct": pct, "umbral_pct": umbral, "estado": estado,
        })
    return resumen


def registrar_en_bd(
    pipeline: str,
    resumen: dict[str, Any],
    source_path: str | None = None,
) -> None:
    """Registra la corrida en pipeline_executions. NUNCA rompe el pipeline."""
    try:
        from itacamba_reportes.persistence.execution_tracker import ExecutionTracker

        tracker = ExecutionTracker(pipeline_name=pipeline)
        if source_path:
            tracker.add_source_file(pipeline, source_path,
                                    sha=resumen.get("hash_contenido"))
        else:
            tracker.add_source_file(
                pipeline, f"db://{pipeline}", sha=resumen.get("hash_contenido"))
        with tracker.start():
            tracker.record_metrics(rows_processed=resumen.get("filas", 0),
                                   rows_inserted=resumen.get("filas", 0))
        logger.info("Corrida registrada en pipeline_executions (%s, hash %s)",
                    pipeline, resumen.get("hash_contenido"))
    except Exception as exc:  # control jamás tumba producción
        logger.warning("No se pudo registrar la corrida de %s en BD: %s",
                       pipeline, exc)
