"""Pipeline REFERENCIAS — sincronización data-driven de catálogos SAP.

Lee REFERENCIAS.xlsx (una hoja por catálogo declarado en
references.yaml) y hace TRUNCATE+INSERT de cada tabla int_ref_*.
El registro de catálogos vive en reference_loader.CATALOGS:
agregar uno = 1 modelo + 1 entrada YAML + 1 línea en CATALOGS.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from itacamba_reportes.ingestion.excel_reader import ExcelReader
from itacamba_reportes.persistence.repositories.reference_loader import (
    CATALOGS,
    ReferenceLoader,
    df_to_clean_rows,
)
from itacamba_reportes.pipelines.file_state import FileStateTracker
from itacamba_reportes.pipelines.runner import PipelineResult, run_file_pipeline

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ReferencesPipeline:

    readers: dict[str, ExcelReader]   # key de catálogo -> reader de su hoja
    loader: ReferenceLoader
    source_path: Path
    state_tracker: FileStateTracker

    DATASET_KEY: str = "references"

    def __post_init__(self) -> None:
        missing = [c.key for c in CATALOGS if c.key not in self.readers]
        if missing:
            raise ValueError(
                f"references.yaml no define catalogs para: {missing}",
            )

    def run(self, force: bool = False) -> PipelineResult:
        return run_file_pipeline(
            name="REFERENCIAS",
            dataset_key=self.DATASET_KEY,
            source_path=self.source_path,
            state_tracker=self.state_tracker,
            force=force,
            stages=self._stages,
        )

    def _stages(self) -> dict[str, int]:
        rows_loaded: dict[str, int] = {}
        logger.info("Carga de %d catalogos (extract -> clean -> replace_all)",
                    len(CATALOGS))
        for catalog in CATALOGS:
            df = self.readers[catalog.key].read()
            rows = df_to_clean_rows(df, catalog.model)
            rows_loaded[catalog.key] = self.loader.replace_all(catalog.model, rows)
        return rows_loaded


def build_pipeline(state_tracker=None) -> "ReferencesPipeline":
    """Composition root del reporte: sources de los 6 catalogos."""
    from itacamba_reportes.config.paths import DataPaths
    from itacamba_reportes.config.sources import load_reference_sources
    from itacamba_reportes.ingestion.excel_reader import ExcelReader
    from itacamba_reportes.persistence.repositories.reference_loader import (
        ReferenceLoader,
    )
    from itacamba_reportes.pipelines.file_state import FileStateTracker
    from itacamba_reportes.reportes.referencias import SLICE_DIR

    inbox = DataPaths.from_env().inbox
    sources = load_reference_sources(SLICE_DIR)   # registro resuelve slice
    readers = {
        key: ExcelReader(source=src, data_path=inbox)
        for key, src in sources.items()
    }
    any_reader = next(iter(readers.values()))
    if state_tracker is None:
        state_path = SLICE_DIR.parents[3] / "storage" / "state" / "pipeline_state.json"
        state_tracker = FileStateTracker(state_path)
    return ReferencesPipeline(
        readers=readers,
        loader=ReferenceLoader(),
        source_path=any_reader.resolve_path(),
        state_tracker=state_tracker,
    )
