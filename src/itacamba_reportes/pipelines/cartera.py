"""Pipeline CARTERA — Excel SAP -> stg_cartera -> normalize/mapping/rules -> int_cartera.

Spec-driven: rename posicional, dtypes, transforms, mapping y contract
salen de cartera.yaml. STG audita cada corrida con run_id + row_index.
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from itacamba_reportes.config.dataset_spec import DatasetSpec
from itacamba_reportes.ingestion.excel_reader import ExcelReader
from itacamba_reportes.persistence.df_to_rows import df_to_records_nullable
from itacamba_reportes.persistence.repositories.cartera_repository_sql import (
    CarteraIntRepositoryImpl,
)
from itacamba_reportes.persistence.repositories.stg_cartera_repository_sql import (
    StgCarteraIntRepositoryImpl,
)
from itacamba_reportes.pipelines.file_state import FileStateTracker
from itacamba_reportes.pipelines.runner import PipelineResult, run_file_pipeline
from itacamba_reportes.transforms.cartera_normalize import NormalizeCarteraFromSpec
from itacamba_reportes.transforms.common import BusinessRule, apply_column_mapping

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CarteraPipeline:

    spec: DatasetSpec
    reader: ExcelReader
    stg_repo: StgCarteraIntRepositoryImpl
    cartera_repo: CarteraIntRepositoryImpl
    rules: list[BusinessRule]
    source_path: Path
    state_tracker: FileStateTracker

    DATASET_KEY: str = "cartera"

    def run(self, run_id: datetime | None = None, force: bool = False) -> PipelineResult:
        run_id = run_id or datetime.now()
        return run_file_pipeline(
            name="CARTERA",
            dataset_key=self.DATASET_KEY,
            source_path=self.source_path,
            state_tracker=self.state_tracker,
            force=force,
            stages=lambda: self._stages(run_id),
        )

    # ── stages ────────────────────────────────────────────────────────

    def _stages(self, run_id: datetime) -> dict[str, int]:
        logger.info("Stage 1 - EXTRACT")
        df = self.reader.read()
        logger.info("Excel leido: %d filas x %d cols", *df.shape)

        logger.info("Stage 2 - STG SQL (run_id=%s)", run_id.isoformat())
        working = self._persist_stg(df, run_id)
        stg_rows = len(working)

        logger.info("Stage 3 - NORMALIZE")
        normalized = NormalizeCarteraFromSpec(self.spec).execute(working)

        logger.info("Stage 4 - MAPPING (snake_case)")
        mapped = apply_column_mapping(
            normalized,
            rename=self.spec.to_int_model.rename,
            drop=self.spec.to_int_model.drop,
            dataset="cartera",
        )

        logger.info("Stage 5 - RULES (%d)", len(self.rules))
        for rule in self.rules:
            mapped = rule.apply(mapped)

        logger.info("Stage 6 - VALIDATE")
        validated = self._validate(mapped)

        logger.info("Stage 7 - LOAD int_cartera")
        loaded = self.cartera_repo.bulk_replace_from_df(validated)

        return {"stg_cartera": stg_rows, "int_cartera": loaded}

    def _persist_stg(self, df: pd.DataFrame, run_id: datetime) -> pd.DataFrame:
        self.stg_repo.clean_all()
        rows = df_to_records_nullable(df)
        self.stg_repo.bulk_insert(rows, run_id=run_id)
        logger.info("STG: %d filas, %d cols (reusing in-memory df)", *df.shape)
        # Mismo dataset que se persistió: NaN -> None para las stages siguientes.
        return df.astype(object).where(df.notna(), None)

    def _validate(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self.spec.output_contract:
            return df
        module_path, _, class_name = self.spec.output_contract.rpartition(".")
        contract = getattr(importlib.import_module(module_path), class_name)
        return contract.validate(df)
