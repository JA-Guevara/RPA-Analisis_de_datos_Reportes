"""Verifica que el código vigente reproduce exactamente los goldens.

Correr con:  pytest tests/characterization/ -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
sys.path.insert(0, str(HERE))

from scenarios import compute_scenarios, get_world  # noqa: E402

GOLDEN_PATH = HERE / "golden" / "goldens.json"


@pytest.fixture(scope="module")
def golden() -> dict:
    if not GOLDEN_PATH.exists():
        pytest.skip("Goldens no capturados (correr capture_goldens.py --write)")
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def actual() -> dict:
    return compute_scenarios(get_world())


def test_same_scenarios(golden, actual):
    assert sorted(golden.keys()) == sorted(actual.keys())


@pytest.mark.parametrize("key", [
    "excel_sources",
    "mapping_cartera",
    "mapping_query_cfg", "mapping_query_none",
    "mapping_gd20_cfg", "mapping_gd20_none",
    "mapping_despacho_bi_cfg", "mapping_despacho_bi_none",
    "reference_clean_almacen", "reference_clean_centro",
    "reference_clean_equipo", "reference_clean_localidad",
    "reference_clean_material", "reference_clean_semana",
    "reader_pipeline_cs", "reader_pipeline_ci",
    "cartera_normalize", "cartera_rules",
    "state_json", "state_roundtrip",
])
def test_scenario(golden, actual, key):
    assert key in actual, f"escenario '{key}' no computado"
    assert actual[key] == golden[key], (
        f"DIVERGENCIA en '{key}': el refactor cambió el comportamiento.\n"
        f"esperado: {json.dumps(golden[key], ensure_ascii=False)[:800]}\n"
        f"obtenido: {json.dumps(actual[key], ensure_ascii=False)[:800]}"
    )
