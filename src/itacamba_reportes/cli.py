"""CLI entrypoint - itacamba-reportes.

Composition root: aquí (y solo aquí) se cablean configs, readers,
repos y pipelines. Agregar un pipeline = un builder + una entry en
PIPELINES.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from itacamba_reportes.config.env_config import validate_config
from itacamba_reportes.config.paths import DataPaths
from itacamba_reportes.persistence.excel_report_exporter import ExcelReportExporter
from itacamba_reportes.reportes.cartera.pipeline import (
    CarteraPipeline,
    build_pipeline as build_cartera,
)
from itacamba_reportes.reportes.despacho_bi.pipeline import (
    DespachoBiPipeline,
    build_pipeline as build_despacho_bi,
)
from itacamba_reportes.reportes.despacho_mes.pipeline import (
    DespachoMesPipeline,
    build_pipeline as build_despacho_mes,
)
from itacamba_reportes.pipelines.file_state import FileStateTracker
from itacamba_reportes.reportes.gd20_ventas_bi.pipeline import (
    Gd20Pipeline,
    build_pipeline as build_gd20,
)
from itacamba_reportes.reportes.query.pipeline import (
    QueryPipeline,
    build_pipeline as build_query,
)
from itacamba_reportes.reportes.referencias.pipeline import (
    ReferencesPipeline,
    build_pipeline as build_referencias,
)
from itacamba_reportes.pipelines.run_all import RunAllOrchestrator
from itacamba_reportes.pipelines.runner import PipelineResult
from itacamba_reportes.shared.logging_setup import setup_logging
from itacamba_reportes.transforms.common import BusinessRule

logger = logging.getLogger(__name__)


_PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
_CONFIGS_DIR: Path = _PROJECT_ROOT / "assets" / "configs"
_STATE_PATH: Path = _PROJECT_ROOT / "storage" / "state" / "pipeline_state.json"


# ── Builders ──────────────────────────────────────────────────────────

def _state_tracker() -> FileStateTracker:
    return FileStateTracker(_STATE_PATH)


def _build_exporter() -> ExcelReportExporter:
    return ExcelReportExporter(output_dir=DataPaths.from_env().exports)


def _build_cartera_pipeline() -> CarteraPipeline:
    return build_cartera(state_tracker=_state_tracker())


def _build_references_pipeline() -> ReferencesPipeline:
    return build_referencias(state_tracker=_state_tracker())


def _build_query_pipeline() -> QueryPipeline:
    return build_query(state_tracker=_state_tracker())


def _build_gd20_pipeline() -> Gd20Pipeline:
    return build_gd20(exporter=_build_exporter(), state_tracker=_state_tracker())


def _build_despacho_bi_pipeline() -> DespachoBiPipeline:
    return build_despacho_bi(exporter=_build_exporter())


def _build_despacho_mes_pipeline() -> DespachoMesPipeline:
    return build_despacho_mes(exporter=_build_exporter())


def _build_run_all_orchestrator() -> RunAllOrchestrator:
    return RunAllOrchestrator(
        references_pipeline=_build_references_pipeline(),
        cartera_pipeline=_build_cartera_pipeline(),
        query_pipeline=_build_query_pipeline(),
        gd20_pipeline=_build_gd20_pipeline(),
        despacho_bi_pipeline=_build_despacho_bi_pipeline(),
        despacho_mes_pipeline=_build_despacho_mes_pipeline(),
    )


# ── Runners ───────────────────────────────────────────────────────────

def _run_cartera(args: argparse.Namespace):
    run_id = datetime.combine(args.execution_date, datetime.min.time())
    return _build_cartera_pipeline().run(run_id=run_id, force=args.force)


def _run_referencias(args: argparse.Namespace):
    return _build_references_pipeline().run(force=args.force)


def _run_query(args: argparse.Namespace):
    return _build_query_pipeline().run(force=args.force)


def _run_despacho_bi(args: argparse.Namespace):
    return _build_despacho_bi_pipeline().run(force=args.force)


def _run_despacho_mes(args: argparse.Namespace):
    return _build_despacho_mes_pipeline().run(force=args.force)


def _run_gd20(args: argparse.Namespace):
    return _build_gd20_pipeline().run(
        force=args.force,
        force_rebuild=getattr(args, "force_rebuild", False),
    )


def _run_all(args: argparse.Namespace):
    run_id = datetime.combine(args.execution_date, datetime.min.time())
    return _build_run_all_orchestrator().run(run_id=run_id, force=args.force)


# ── Extra args ────────────────────────────────────────────────────────

def _date_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--date",
        dest="execution_date",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=date.today(),
        help="Fecha de ejecucion (YYYY-MM-DD). Default: hoy.",
    )


def _gd20_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--force-rebuild",
        dest="force_rebuild",
        action="store_true",
        help=(
            "Ignora el sticky CD/ZE y re-aplica los derivados a TODAS las filas "
            "vigentes de int_ventas_bi. Uso administrativo cuando se necesita "
            "recalcular con datos nuevos de QUERY/CARTERA/REFERENCIAS. "
            "NO afecta SAP raw (sigue versionando por SCD2)."
        ),
    )


# ── Registry ──────────────────────────────────────────────────────────

@dataclass(slots=True)
class PipelineSpec:
    name: str
    help: str
    runner: Callable[[argparse.Namespace], object]
    extra_args: Callable[[argparse.ArgumentParser], None] | None = None


PIPELINES: dict[str, PipelineSpec] = {
    "run-cartera": PipelineSpec(
        name="cartera",
        help="Pipeline CARTERA -> int_cartera.",
        runner=_run_cartera,
        extra_args=_date_arg,
    ),
    "run-referencias": PipelineSpec(
        name="referencias",
        help="Pipeline REFERENCIAS -> tablas int_ref_*.",
        runner=_run_referencias,
    ),
    "run-query": PipelineSpec(
        name="query",
        help="Pipeline QUERY -> stg_query + int_query (mes objetivo).",
        runner=_run_query,
    ),
    "run-despacho-bi": PipelineSpec(
        name="despacho_bi",
        help="Pipeline DESPACHO BI (int_query + lookups -> int_despacho_bi).",
        runner=_run_despacho_bi,
    ),
    "run-despacho-mes": PipelineSpec(
        name="despacho_mes",
        help="Pipeline DESPACHO MES (int_despacho_bi -> agregado mensual).",
        runner=_run_despacho_mes,
    ),
    "run-gd20": PipelineSpec(
        name="gd20",
        help="Pipeline GD20 (Excel SAP + lookups -> int_gd20 + int_ventas_bi).",
        runner=_run_gd20,
        extra_args=_gd20_args,
    ),
    "run-all": PipelineSpec(
        name="run-all",
        help="Ejecuta TODOS los pipelines en orden secuencial con fail-fast.",
        runner=_run_all,
        extra_args=_date_arg,  # cartera necesita --date
    ),
}


# ── argparse + main ───────────────────────────────────────────────────

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="itacamba-reportes",
        description="Pipeline ETL declarativo Itacamba Reportes.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for cmd, spec in PIPELINES.items():
        p = sub.add_parser(cmd, help=spec.help)
        p.add_argument("--force", action="store_true",
                       help="Forzar ejecucion aunque el archivo no haya cambiado.")
        if spec.extra_args is not None:
            spec.extra_args(p)

    return parser.parse_args(argv)


def _log_result(name: str, result: object) -> None:
    if getattr(result, "skipped", False):
        logger.info("%s skip (sin cambios)", name.upper())
        return
    if isinstance(result, PipelineResult):
        rows = ", ".join(f"{k}={v}" for k, v in result.rows.items())
        logger.info("OK %s: %s, %.2fs", name.upper(), rows, result.duration_seconds)
    else:  # RunAllResult
        logger.info("OK %s: %.2fs total", name.upper(),
                    getattr(result, "total_seconds", 0.0))


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    args = _parse_args(argv)

    try:
        validate_config()
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Config invalida: %s", exc)
        return 1

    spec = PIPELINES[args.command]
    logger.info("Construyendo pipeline %s", spec.name.upper())
    try:
        result = spec.runner(args)
    except Exception as exc:
        logger.exception("Pipeline %s fallo: %s", spec.name.upper(), exc)
     