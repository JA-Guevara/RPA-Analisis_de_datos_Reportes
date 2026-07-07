"""Pipeline GD20 — Excel SAP -> stg_gd20 -> enrich -> int_gd20
-> UPSERT SCD2 int_ventas_bi (REPORTE VENTAS BI) -> export Excel.

La lógica calibrada vive en el slice: columnas.yaml (lookups simples,
ColumnEngine) + reglas.py (CD/ZE, overrides, fórmulas numéricas),
orquestadas por enriquecimiento.enrich_gd20. El merge SCD2 es
mecanismo de persistencia (ventas_bi_repository_sql).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd

from itacamba_reportes.ingestion.excel_reader import ExcelReader
from itacamba_reportes.persistence.excel_report_exporter import ExcelReportExporter
from itacamba_reportes.persistence.lookups import load_lookup_df
from itacamba_reportes.persistence.execution_tracker import ExecutionTracker
from itacamba_reportes.persistence.models.int.cartera_model import CarteraIntModel
from itacamba_reportes.persistence.models.int.ventas_bi_model import VentasBiIntModel
from itacamba_reportes.persistence.models.references.almacen_model import AlmacenIntModel
from itacamba_reportes.persistence.models.references.centro_model import CentroIntModel
from itacamba_reportes.persistence.models.references.equipo_model import EquipoIntModel
from itacamba_reportes.persistence.models.references.localidad_model import (
    LocalidadIntModel,
)
from itacamba_reportes.persistence.models.references.material_model import (
    MaterialIntModel,
)
from itacamba_reportes.persistence.models.stg.stg_gd20_model import StgGd20Model
from itacamba_reportes.persistence.models.stg.stg_query_model import StgQueryModel
from itacamba_reportes.persistence.repositories.gd20_repository_sql import (
    Gd20IntRepositoryImpl,
)
from itacamba_reportes.persistence.repositories.stg_repository import StgRepository
from itacamba_reportes.persistence.repositories.ventas_bi_repository_sql import (
    VentasBiIntRepositoryImpl,
)
from itacamba_reportes.pipelines.file_state import FileFingerprint, FileStateTracker
from itacamba_reportes.pipelines.runner import PipelineResult, run_file_pipeline
from itacamba_reportes.reportes.gd20_ventas_bi.enriquecimiento import enrich_gd20
from itacamba_reportes.reportes.gd20_ventas_bi.mapping import apply_gd20_mapping

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Gd20Pipeline:

    reader: ExcelReader
    stg_repo: StgRepository
    gd20_repo: Gd20IntRepositoryImpl
    ventas_bi_repo: VentasBiIntRepositoryImpl
    source_path: Path
    state_tracker: FileStateTracker
    config: dict[str, Any] | None = None
    exporter: ExcelReportExporter | None = None
    _control: dict | None = None

    DATASET_KEY: str = "gd20"

    def run(self, force: bool = False, force_rebuild: bool = False) -> PipelineResult:
        return run_file_pipeline(
            name="GD20",
            dataset_key=self.DATASET_KEY,
            source_path=self.source_path,
            state_tracker=self.state_tracker,
            force=force,
            stages=lambda: self._stages(force_rebuild),
            post_state=self._export,
        )

    # ── stages ────────────────────────────────────────────────────────

    def _stages(self, force_rebuild: bool) -> dict[str, int]:
        logger.info("Stage 1 - EXTRACT")
        t = perf_counter()
        df_raw = self.reader.read()
        logger.info("Excel leido: %d filas x %d cols (%.2fs)",
                    *df_raw.shape, perf_counter() - t)

        logger.info("Stage 2 - STG LOAD")
        t = perf_counter()
        self.stg_repo.clean_all()
        stg_rows = self.stg_repo.bulk_insert(df_raw)
        logger.info("STG load: %d filas (%.2fs)", stg_rows, perf_counter() - t)

        logger.info("Stage 3 - LOOKUPS LOAD")
        t = perf_counter()
        lk = self._load_lookups()
        logger.info("Lookups: cartera=%d equipo=%d almacen=%d material=%d "
                    "centro=%d query=%d localidad=%d (%.2fs)",
                    len(lk["cartera"]), len(lk["equipo"]), len(lk["almacen"]),
                    len(lk["material"]), len(lk["centro"]), len(lk["query"]),
                    len(lk["localidad"]), perf_counter() - t)

        logger.info("Stage 4 - ENRICH (catalogo + reglas del slice)")
        t = perf_counter()
        df = apply_gd20_mapping(df_raw, self.config)
        df = enrich_gd20(
            df, self.config,
            cartera_df=lk["cartera"], equipo_df=lk["equipo"],
            almacen_df=lk["almacen"], material_df=lk["material"],
            centro_df=lk["centro"], query_df=lk["query"],
            localidad_df=lk["localidad"],
        )
        logger.info("Enrich completo: %d filas x %d cols (%.2fs)",
                    *df.shape, perf_counter() - t)

        from itacamba_reportes.shared.control_corrida import resumen_corrida
        self._control = resumen_corrida(
            df, (self.config or {}).get("control"), reporte="gd20_ventas_bi")
        # (la corrida ya queda auditada por el ExecutionTracker del SCD2)

        logger.info("Stage 5 - LOAD int_gd20")
        t = perf_counter()
        int_rows = self.gd20_repo.bulk_replace_from_df(df)
        logger.info("INT load: %d filas (%.2fs)", int_rows, perf_counter() - t)

        logger.info("Stage 6 - UPSERT int_ventas_bi (SCD2 by-hash)")
        t = perf_counter()
        vb_rows = self._upsert_ventas_bi(force_rebuild)
        logger.info("VentasBi SCD2 total afectadas: %d (%.2fs)",
                    vb_rows, perf_counter() - t)

        return {
            "stg_gd20": stg_rows,
            "int_gd20": int_rows,
            "int_ventas_bi": vb_rows,
        }

    def _upsert_ventas_bi(self, force_rebuild: bool) -> int:
        """SCD2 merge auditado en pipeline_executions (execution_id por fila)."""
        actual = FileFingerprint.from_path(self.source_path)
        tracker = ExecutionTracker(
            pipeline_name="gd20",
            force_rebuild=force_rebuild,
        )
        tracker.add_source_file(
            "gd20", str(self.source_path),
            size=actual.size, mtime=actual.mtime,
        )
        with tracker.start() as execution_id:
            m = self.ventas_bi_repo.upsert_scd2_from_int_gd20(
                execution_id=execution_id,
                force_rebuild=force_rebuild,
            )
            tracker.record_metrics(**m)
        logger.info(
            "VentasBi SCD2: inserted=%d versioned=%d rescued=%d updated=%d skipped=%d",
            m["inserted"], m["versioned"], m["rescued"], m["updated"], m["skipped"],
        )
        return m["inserted"] + m["versioned"] + m["rescued"] + m["updated"]

    def _export(self) -> str | None:
        if self.exporter is None:
            return None
        logger.info("Stage 7 - EXPORT int_ventas_bi -> Excel")
        t = perf_counter()
        try:
            path = self.exporter.export(
                VentasBiIntModel.__tablename__, "VENTAS_BI",
                control=self._control,
                encabezados=(self.config or {}).get("encabezados"),
            )
            logger.info("Export OK: %s (%.2fs)", path, perf_counter() - t)
            return str(path)
        except Exception:
            # El reporte ya está persistido en BD; un fallo de export no
            # debe abortar el pipeline.
            logger.exception("Export de VENTAS_BI fallo (datos ya en BD)")
            return None

    @staticmethod
    def _load_lookups() -> dict[str, pd.DataFrame]:
        return {
            "cartera":   load_lookup_df(CarteraIntModel),
            "equipo":    load_lookup_df(EquipoIntModel),
            "almacen":   load_lookup_df(AlmacenIntModel),
            "material":  load_lookup_df(MaterialIntModel),
            "centro":    load_lookup_df(CentroIntModel),
            "query":     load_lookup_df(StgQueryModel),
            "localidad": load_lookup_df(LocalidadIntModel),
        }


def build_pipeline(
    exporter: ExcelReportExporter | None = None,
    state_tracker: FileStateTracker | None = None,
) -> Gd20Pipeline:
    """Composition root del reporte: config + reader del slice."""
    from itacamba_reportes.config.paths import DataPaths
    from itacamba_reportes.config.sources import excel_source_from_cfg
    from itacamba_reportes.reportes.gd20_ventas_bi import SLICE_DIR, load_config

    cfg = load_config()
    source = excel_source_from_cfg("gd20", cfg["source"])
    reader = ExcelReader(source=source, data_path=DataPaths.from_env().inbox)
    if state_tracker is None:
        state_path = SLICE_DIR.parents[3] / "storage" / "state" / "pipeline_state.json"
        state_tracker = FileStateTracker(state_path)
    return Gd20Pipeline(
        reader=reader,
        stg_repo=StgRepository(StgGd20Model),
        gd20_repo=Gd20IntRepositoryImpl(),
        ventas_bi_repo=VentasBiIntRepositoryImpl(),
        source_path=reader.resolve_path(),
        state_tracker=state_tracker,
        config=cfg,
        exporter=exporter,
    )
