"""Pipeline QUERY — SAP raw -> stg_query -> [mapping+normalize+rules] -> int_query.

int_query es el insumo del pipeline DESPACHO BI. Se regenera completo
en cada corrida (solo representa el mes objetivo del reporte).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from itacamba_reportes.ingestion.excel_reader import ExcelReader
from itacamba_reportes.persistence.models.stg.stg_query_model import StgQueryModel
from itacamba_reportes.persistence.repositories.query_repository_sql import (
    IntQueryRepositoryImpl,
)
from itacamba_reportes.persistence.repositories.stg_repository import StgRepository
from itacamba_reportes.pipelines.file_state import FileStateTracker
from itacamba_reportes.pipelines.runner import PipelineResult, run_file_pipeline
from itacamba_reportes.reportes.query.mapping import apply_query_mapping
from itacamba_reportes.reportes.query.reglas import (
    QueryBusinessRulesUseCase,
    QueryNormalizeUseCase,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class QueryPipeline:

    reader: ExcelReader
    stg_repo: StgRepository
    int_repo: IntQueryRepositoryImpl
    source_path: Path
    state_tracker: FileStateTracker
    config: dict[str, Any] | None = None

    DATASET_KEY: str = "query"

    def run(self, force: bool = False) -> PipelineResult:
        return run_file_pipeline(
            name="QUERY",
            dataset_key=self.DATASET_KEY,
            source_path=self.source_path,
            state_tracker=self.state_tracker,
            force=force,
            stages=self._stages,
        )

    def _stages(self) -> dict[str, int]:
        logger.info("Stage 1 - EXTRACT")
        t = perf_counter()
        df_raw = self.reader.read()
        logger.info("Excel leido: %d filas x %d cols (%.2fs)",
                    *df_raw.shape, perf_counter() - t)

        logger.info("Stage 2 - STG LOAD (TRUNCATE + INSERT stg_query)")
        t = perf_counter()
        self.stg_repo.clean_all()
        stg_rows = self.stg_repo.bulk_insert(df_raw)
        logger.info("STG load: %d filas (%.2fs)", stg_rows, perf_counter() - t)

        logger.info("Stage 3 - ENRICH (mapping + normalize + rules)")
        t = perf_counter()
        df = apply_query_mapping(df_raw, self.config)
        df = QueryNormalizeUseCase(config=self.config).execute(df)
        df = QueryBusinessRulesUseCase(config=self.config).execute(df)
        logger.info("Enrich completo: %d filas x %d cols (%.2fs)",
                    *df.shape, perf_counter() - t)

        logger.info("Stage 4 - INT LOAD (TRUNCATE + INSERT int_query)")
        t = perf_counter()
        int_rows = self.int_repo.bulk_replace_from_df(df)

        from itacamba_reportes.shared.control_corrida import (
            registrar_en_bd,
            resumen_corrida,
        )
        registrar_en_bd(
            "query",
            resumen_corrida(df, (self.config or {}).get("control"), "query"),
            source_path=str(self.source_path),
        )
        logger.info("INT load: %d filas (%.2fs)", int_rows, perf_counter() - t)

        return {"stg_query": stg_rows, "int_query": int_rows}


def build_pipeline(state_tracker=None) -> QueryPipeline:
    """Composition root del reporte: config + reader del slice."""
    from itacamba_reportes.config.paths import DataPaths
    from itacamba_reportes.config.sources import excel_source_from_cfg
    from itacamba_reportes.pipelines.file_state import FileStateTracker
    from itacamba_reportes.reportes.query import SLICE_DIR, load_config

    cfg = load_config()
    source = excel_source_from_cfg("query", cfg["source"])
    reader = ExcelReader(source=source, data_path=DataPaths.from_env().inbox)
    if state_tracker is None:
        state_path = SLICE_DIR.parents[3] / "storage" / "state" / "pipeline_state.json"
        state_tracker = FileStateTracker(state_path)
    return QueryPipeline(
        reader=reader,
        stg_repo=StgRepository(StgQueryModel),
        int_repo=IntQueryRepositoryImpl(),
        source_path=reader.resolve_path(),
        state_tracker=state_tracker,
        config=cfg,
    )
