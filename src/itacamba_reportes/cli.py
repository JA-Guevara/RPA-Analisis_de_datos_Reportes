from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from time import perf_counter

src_path = str(Path(__file__).resolve().parents[1])
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from itacamba_reportes.core.db.schema import ensure_schema_current, upgrade_db
from itacamba_reportes.inputs.referencias.pipeline import run_pipeline as run_referencias
from itacamba_reportes.inputs.cartera.pipeline import run_pipeline as run_cartera
from itacamba_reportes.inputs.query.pipeline import run_pipeline as run_query
from itacamba_reportes.inputs.proyeccion.pipeline import run_pipeline as run_proyeccion
from itacamba_reportes.inputs.gd20.pipeline import run_pipeline as run_gd20
from itacamba_reportes.outputs.ventas_bi.pipeline import run_pipeline as run_ventas_bi
from itacamba_reportes.outputs.despacho_bi.pipeline import run_pipeline as run_despacho_bi
from itacamba_reportes.outputs.despacho_mes.pipeline import run_pipeline as run_despacho_mes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("itacamba_reportes")


def run_all(is_fin_de_mes: bool = False) -> int:
    t0 = perf_counter()
    logger.info("==================================================")
    logger.info("=== EJECUCIÓN GENERAL DE TODOS LOS PIPELINES   ===")
    logger.info("==================================================")
    
    steps = [
        ("REFERENCIAS", lambda: run_referencias()),
        ("CARTERA", lambda: run_cartera()),
        ("QUERY", lambda: run_query()),
        ("PROYECCION", lambda: run_proyeccion()),
        ("GD20", lambda: run_gd20(is_fin_de_mes=is_fin_de_mes)),
        ("VENTAS BI", lambda: run_ventas_bi()),
        ("DESPACHO BI", lambda: run_despacho_bi()),
        ("DESPACHO MES", lambda: run_despacho_mes()),
    ]

    for name, func in steps:
        logger.info("--> Ejecutando etapa: %s", name)
        try:
            func()
        except Exception as exc:
            logger.error("Fallo crítico en etapa %s: %s", name, exc)
            return 1

    logger.info("==================================================")
    logger.info("=== TODOS LOS PIPELINES COMPLETADOS EN %.2fs ===", perf_counter() - t0)
    logger.info("==================================================")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="itacamba-reportes",
        description="Pipeline ETL Database-First Itacamba Reportes.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("test-db", help="Verifica la conexión a SQL Server y muestra diagnóstico detallado.")
    subparsers.add_parser("init-db", help="Aplica las migraciones Alembic pendientes (alembic upgrade head).")
    subparsers.add_parser("run-referencias", help="Pipeline REFERENCIAS -> tablas int_ref_*.")
    subparsers.add_parser("run-cartera", help="Pipeline CARTERA -> stg_cartera + int_cartera.")
    subparsers.add_parser("run-query", help="Pipeline QUERY ZBCS -> stg_query + int_query.")
    subparsers.add_parser("run-proyeccion", help="Pipeline PROYECCIÓN -> stg_proyeccion.")

    p_gd20 = subparsers.add_parser("run-gd20", help="Pipeline GD20 (BASE PANEL) -> int_gd20 + int_ventas_bi.")
    p_gd20.add_argument("--fin-de-mes", action="store_true", help="Conserva las filas de la fecha actual para cierre.")
    p_gd20.add_argument("--force", action="store_true", help="Fuerza la ejecución completa (compatibilidad).")

    subparsers.add_parser("run-ventas-bi", help="Pipeline VENTAS BI -> acumula histórico SCD2.")
    subparsers.add_parser("run-despacho-bi", help="Pipeline DESPACHO BI -> acumula histórico real de despachos.")
    subparsers.add_parser("run-despacho-mes", help="Pipeline DESPACHO MES -> resumen mensual y proyección.")

    p_all = subparsers.add_parser("run-all", help="Ejecuta todos los pipelines en orden secuencial.")
    p_all.add_argument("--fin-de-mes", action="store_true", help="Conserva las filas de la fecha actual para cierre.")
    p_all.add_argument("--force", action="store_true", help="Fuerza la ejecución completa (compatibilidad).")

    p_sap = subparsers.add_parser("download-sap", help="Descarga un reporte parametrizado desde SAP GUI.")
    p_sap.add_argument("--transaction", "-t", required=True, help="Código de transacción SAP (ej: gd20, zbcs, sq01).")
    p_sap.add_argument("--variant", "-v", default=None, help="Nombre de la variante guardada en SAP.")
    p_sap.add_argument("--ledger", "-l", default=None, help="Ledger contable (ej: VC).")
    p_sap.add_argument("--period-low", "-p", default=None, help="Periodo/mes inicio (ej: 9).")
    p_sap.add_argument("--period-high", default=None, help="Periodo/mes fin (ej: 9).")
    p_sap.add_argument("--year", "-y", default=None, help="Año de ejercicio contable (ej: 2026).")
    p_sap.add_argument("--date-from", default=None, help="Fecha inicio para transacciones tipo query/despachos.")
    p_sap.add_argument("--date-to", default=None, help="Fecha fin para transacciones tipo query/despachos.")
    p_sap.add_argument("--layout-row", type=int, default=None, help="Fila de layout ALV a seleccionar.")
    p_sap.add_argument("--filename", "-f", default="EXPORT", help="Nombre base del archivo a exportar.")
    p_sap.add_argument("--target-dir", "-d", default=None, help="Directorio destino donde ubicar el archivo.")

    args = parser.parse_args(argv)

    try:
        if args.command == "download-sap":
            from itacamba_reportes.sap import SapDownloadConfig, SapSessionManager
            from itacamba_reportes.sap.actions import execute_download_report

            cfg = SapDownloadConfig(
                transaction=args.transaction,
                variant=args.variant,
                ledger=args.ledger,
                period_low=args.period_low,
                period_high=args.period_high,
                year=args.year,
                date_from=args.date_from,
                date_to=args.date_to,
                layout_row=args.layout_row,
                export_filename=args.filename,
                target_dir=args.target_dir,
            )
            session_mgr = SapSessionManager()
            execute_download_report(session_mgr, cfg)
            return 0

        if args.command == "test-db":
            from itacamba_reportes.core.db.connection import get_engine
            from sqlalchemy import text
            eng = get_engine()
            with eng.connect() as conn:
                row = conn.execute(text("SELECT @@SERVERNAME, DB_NAME(), SUSER_SNAME(), @@VERSION")).fetchone()
                logger.info("==================================================")
                logger.info("=== CONEXIÓN A BASE DE DATOS EXITOSA           ===")
                logger.info("==================================================")
                logger.info("Servidor SQL      : %s", row[0])
                logger.info("Base de Datos     : %s", row[1])
                logger.info("Usuario Conectado : %s", row[2])
                v_str = str(row[3]).splitlines()[0] if row[3] else "Desconocida"
                logger.info("Versión           : %s", v_str)
                logger.info("==================================================")
            return 0

        if args.command == "init-db":
            upgrade_db()
            return 0

        ensure_schema_current()

        if args.command == "run-referencias":
            run_referencias()
        elif args.command == "run-cartera":
            run_cartera()
        elif args.command == "run-query":
            run_query()
        elif args.command == "run-proyeccion":
            run_proyeccion()
        elif args.command == "run-gd20":
            run_gd20(is_fin_de_mes=args.fin_de_mes)
            run_ventas_bi()
        elif args.command == "run-ventas-bi":
            run_ventas_bi()
        elif args.command == "run-despacho-bi":
            run_despacho_bi()
        elif args.command == "run-despacho-mes":
            run_despacho_mes()
        elif args.command == "run-all":
            return run_all(is_fin_de_mes=args.fin_de_mes)
        return 0
    except Exception as exc:
        logger.exception("Error en ejecución de %s: %s", args.command, exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
