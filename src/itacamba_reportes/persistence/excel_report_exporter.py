"""Adaptador Excel del puerto `ReportExporter`.

Vuelca el contenido COMPLETO de una tabla SQL a un archivo .xlsx, generando
un archivo por ejecución con timestamp en el nombre:

    {report_name}_{YYYY-MM-DD_HHMM}.xlsx

Pensado para entregar el snapshot de un reporte (VENTAS_BI, DESPACHO_BI, …)
tras cada corrida del pipeline correspondiente.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from time import perf_counter

import pandas as pd
from sqlalchemy.engine import Engine

from itacamba_reportes.persistence.engine import engine as _default_engine

logger = logging.getLogger(__name__)


class ExcelReportExporter:
    """Exporta una tabla SQL completa a un .xlsx con timestamp."""

    def __init__(self, output_dir: Path, engine: Engine | None = None) -> None:
        self._output_dir = output_dir
        # Permite inyectar un engine en tests; por defecto usa el del proyecto.
        self._engine = engine if engine is not None else _default_engine

    def export(
        self,
        table_name: str,
        report_name: str,
        control: dict | None = None,
        encabezados: dict[str, str] | None = None,
    ) -> Path:
        """Exporta la tabla a .xlsx con timestamp.

        control:     resumen de shared.control_corrida — agrega una hoja
                     "CONTROL" (fecha, filas, hash de contenido, calidad
                     por columna). La hoja de DATOS no cambia.
        encabezados: renombres snake_case -> encabezado del cliente para
                     la hoja de datos (opcional; sin configurar = igual
                     que siempre).
        """
        if self._engine is None:
            raise RuntimeError(
                "Engine SQL no inicializado; no se puede exportar "
                "(revisar variables DB_* / DATABASE_URL en .env)",
            )

        t0 = perf_counter()
        df = pd.read_sql_table(table_name, self._engine)
        if encabezados:
            df = df.rename(columns=encabezados)

        self._output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
        target = self._output_dir / f"{report_name}_{timestamp}.xlsx"

        # xlsxwriter escribe 3-5x mas rapido que openpyxl (mismo .xlsx).
        # Fallback a openpyxl si xlsxwriter no esta instalado.
        try:
            self._escribir(df, target, control, engine="xlsxwriter")
        except ModuleNotFoundError:
            logger.warning(
                "xlsxwriter no instalado (pip install xlsxwriter) - "
                "usando openpyxl (mas lento)",
            )
            self._escribir(df, target, control, engine="openpyxl")

        logger.info(
            "Export Excel: %s -> %s (%d filas x %d cols%s, %.2fs)",
            table_name, target.name, df.shape[0], df.shape[1],
            ", +hoja CONTROL" if control else "", perf_counter() - t0,
        )
        return target

    @staticmethod
    def _escribir(df: pd.DataFrame, target: Path,
                  control: dict | None, engine: str) -> None:
        if not control:
            df.to_excel(target, index=False, engine=engine)
            return
        with pd.ExcelWriter(target, engine=engine) as writer:
            df.to_excel(writer, index=False, sheet_name="DATOS")
            encabezado = pd.DataFrame({
                "campo": ["reporte", "fecha_corrida", "filas", "columnas",
                          "hash_contenido", "alertas"],
                "valor": [control.get("reporte", ""),
                          control.get("fecha_corrida", ""),
                          control.get("filas", ""),
                          control.get("columnas", ""),
                          control.get("hash_contenido", ""),
                          control.get("alertas", 0)],
            })
            encabezado.to_excel(writer, index=False, sheet_name="CONTROL",
                                startrow=0)
            calidad = pd.DataFrame(control.get("calidad") or [])
            if not calidad.empty:
                calidad.to_excel(writer, index=False, sheet_name="CONTROL",
                                 startrow=len(encabezado) + 2)
