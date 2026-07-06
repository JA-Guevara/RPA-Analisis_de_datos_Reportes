"""Smoke test de extracción Excel (requiere DATA_PATH con archivos reales)."""

from __future__ import annotations

import sys
from pathlib import Path
from time import perf_counter

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from itacamba_reportes.config.env_config import EnvConfig
from itacamba_reportes.config.sources import load_excel_source
from itacamba_reportes.ingestion.excel_reader import ExcelReader

CONFIGS_DIR = Path(__file__).resolve().parents[1] / "assets" / "configs"


def _smoke(dataset: str) -> None:
    source = load_excel_source(CONFIGS_DIR, dataset)
    reader = ExcelReader(source=source, data_path=EnvConfig.DATA_PATH)
    t0 = perf_counter()
    df = reader.read()
    assert isinstance(df, pd.DataFrame)
    assert not df.empty, f"{dataset}: DataFrame vacio"
    print(f"{dataset}: {len(df)} filas x {len(df.columns)} cols en {perf_counter()-t0:.2f}s")


def test_cartera_extraction():
    _smoke("cartera")


def test_gd20_extraction():
    _smoke("gd20")


if __name__ == "__main__":
    test_cartera_extraction()
    test_gd20_extraction()
