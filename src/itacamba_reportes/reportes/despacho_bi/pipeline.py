"""Pipeline DESPACHO BI — int_query + lookups -> int_despacho_bi -> export.

DB-a-DB: no lee archivos, por lo que no usa change-detection — corre
siempre que se invoque (igual que antes del refactor).

Las fórmulas del cliente (lookups, concats, espejos) NO viven acá:
están declaradas en assets/configs/columnas/despacho_bi.yaml y las
ejecuta el ColumnEngine genérico (transforms/column_engine.py).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from time import perf_counter
from typing import Any

import pandas as pd

from itacamba_reportes.persistence.engine import engine as _engine
from itacamba_reportes.persistence.excel_report_exporter import ExcelReportExporter
from itacamba_reportes.persistence.lookups import load_lookup_df
from itacamba_reportes.persistence.models.int.cartera_model import CarteraIntModel
from itacamba_reportes.persistence.models.int.despacho_bi_model import (
    DespachoBiIntModel,
)
from itacamba_reportes.persistence.models.int.query_model import IntQueryModel
from itacamba_reportes.persistence.models.references.almacen_model import AlmacenIntModel
from itacamba_reportes.persistence.models.references.centro_model import CentroIntModel
from itacamba_reportes.persistence.models.references.equipo_model import EquipoIntModel
from itacamba_reportes.persistence.models.references.localidad_model import (
    LocalidadIntModel,
)
from itacamba_reportes.persistence.models.references.semana_model import SemanaIntModel
from itacamba_reportes.persistence.repositories.despacho_bi_repository_sql import (
    IntDespachoBiRepositoryImpl,
)
from itacamba_reportes.pipelines.runner import PipelineResult, log_summary
from itacamba_reportes.transforms.column_engine import ColumnEngine
from itacamba_reportes.reportes.despacho_bi.mapping import apply_despacho_bi_mapping

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DespachoBiPipeline:

    despacho_bi_repo: IntDespachoBiRepositoryImpl
    column_catalog: dict[str, Any]
    config: dict[str, Any] | None = None
    exporter: ExcelReportExporter | None = None

    def run(self, force: bool = False) -> PipelineResult:
        t0 = perf_counter()
        logger.info("=== DESPACHO BI pipeline start (force=%s) ===", force)

        logger.info("Stage 1 - LOAD int_query")
        t = perf_counter()
        if _engine is None:
            raise RuntimeError("Engine SQLAlchemy no inicializado")
        df_query = pd.read_sql_table(IntQueryModel.__tablename__, _engine)
        query_rows = len(df_query)
        logger.info("int_query cargado: %d filas (%.2fs)", query_rows, perf_counter() - t)
        if query_rows == 0:
            logger.warning("int_query vacio - corre 'run-query' primero.")
            return PipelineResult(
                rows={"int_query": 0, "int_despacho_bi": 0},
                duration_seconds=perf_counter() - t0,
            )

        logger.info("Stage 2 - LOAD lookups (cartera + 5 referencias)")
        t = perf_counter()
        lk = self._load_lookups()
        logger.info(
            "Lookups: %s (%.2fs)",
            ", ".join(f"{tabla}={len(df)}" for tabla, df in lk.items()),
            perf_counter() - t,
        )

        logger.info("Stage 3 - ENRICH (catálogo de columnas)")
        t = perf_counter()
        df = apply_despacho_bi_mapping(df_query, self.config)
        df = ColumnEngine(lookups=lk).apply(df, self.column_catalog)
        logger.info("Enrich: %d filas x %d cols (%.2fs)", *df.shape, perf_counter() - t)

        logger.info("Stage 4 - INT LOAD")
        t = perf_counter()
        int_rows = self.despacho_bi_repo.bulk_replace_from_df(df)
        logger.info("INT load: %d filas (%.2fs)", int_rows, perf_counter() - t)

        # Control de corrida: hash de contenido + calidad + registro en BD
        from itacamba_reportes.shared.control_corrida import (
            registrar_en_bd,
            resumen_corrida,
        )
        control = resumen_corrida(
            df, (self.config or {}).get("control"), reporte="despacho_bi")
        registrar_en_bd("despacho_bi", control)

        export_path: str | None = None
        if self.exporter is not None:
            logger.info("Stage 5 - EXPORT int_despacho_bi -> Excel")
            t = perf_counter()
            try:
                path = self.exporter.export(
                    DespachoBiIntModel.__tablename__, "DESPACHO_BI",
                    control=control,
                    encabezados=(self.config or {}).get("encabezados"),
                )
                export_path = str(path)
                logger.info("Export OK: %s (%.2fs)", export_path, perf_counter() - t)
            except Exception:
                logger.exception("Export de DESPACHO_BI fallo (datos ya en BD)")

        result = PipelineResult(
            rows={"int_query": query_rows, "int_despacho_bi": int_rows},
            duration_seconds=perf_counter() - t0,
            export_path=export_path,
        )
        log_summary("DESPACHO BI", result)
        return result

    @staticmethod
    def _load_lookups() -> dict[str, pd.DataFrame]:
        """Tablas lookup indexadas por nombre de tabla SQL (los mismos
        nombres que usa el catálogo de columnas en sus bloques lookup)."""
        modelos = (
            CarteraIntModel, EquipoIntModel, AlmacenIntModel,
            LocalidadIntModel, CentroIntModel, SemanaIntModel,
        )
        return {m.__tablename__: load_lookup_df(m) for m in modelos}


def build_pipeline(exporter: ExcelReportExporter | None = None) -> DespachoBiPipeline:
    """Composition root del reporte: carga config + catalogo del slice."""
    from itacamba_reportes.reportes.despacho_bi import load_catalog, load_config

    return DespachoBiPipeline(
        despacho_bi_repo=IntDespachoBiRepositoryImpl(),
        column_catalog=load_catalog(),
        config=load_config(),
        exporter=exporter,
    )
