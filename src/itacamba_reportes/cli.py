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
from itacamba_reportes.core.logging_config import setup_logging
from itacamba_reportes.outputs.ventas_bi.pipeline import run_pipeline as run_ventas_bi
from itacamba_reportes.outputs.despacho_bi.pipeline import run_pipeline as run_despacho_bi
from itacamba_reportes.outputs.despacho_mes.pipeline import run_pipeline as run_despacho_mes
from itacamba_reportes.outputs.historial_ventas.export import export_historial_ventas

logger = setup_logging()


def export_all_reports_parallel(corte_fecha: str | None = None) -> None:
    logger.info("--> Iniciando EXPORTACIONES en paralelo (reutilizando DataFrames en memoria)...")
    t_exp = perf_counter()
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from itacamba_reportes.outputs.ventas_bi.export import export_ventas_bi
    from itacamba_reportes.outputs.despacho_bi.export import export_despacho_bi
    from itacamba_reportes.outputs.despacho_mes.export import export_despacho_mes
    from itacamba_reportes.outputs.historial_ventas.export import export_historial_ventas

    tasks = {
        "VENTAS BI": lambda: export_ventas_bi(return_df=True),
        "DESPACHO BI": lambda: export_despacho_bi(return_df=True),
        "DESPACHO MES": lambda: export_despacho_mes(corte_fecha=corte_fecha) if corte_fecha else export_despacho_mes(),
    }

    results: dict[str, object] = {}
    with ThreadPoolExecutor(max_workers=3, thread_name_prefix="ExportWorker") as executor:
        future_to_name = {executor.submit(fn): name for name, fn in tasks.items()}
        for future in as_completed(future_to_name):
            name = future_to_name[future]
            try:
                res = future.result()
                results[name] = res
                out_file = res[0] if isinstance(res, tuple) else res
                logger.info("Exportación completada: %s -> %s", name, getattr(out_file, "name", out_file))
            except Exception as exc:
                logger.error("Fallo crítico en exportación %s: %s", name, exc)
                raise

    _, df_ventas = results["VENTAS BI"]  # type: ignore[misc]
    _, df_despachos = results["DESPACHO BI"]  # type: ignore[misc]
    hist_path = export_historial_ventas(df_ventas=df_ventas, df_despachos=df_despachos)
    logger.info("Exportación completada: HISTORIAL VENTAS -> %s", getattr(hist_path, "name", hist_path))
    logger.info("Todas las exportaciones paralelas completadas exitosamente en %.2fs", perf_counter() - t_exp)


def run_all(
    force: bool = False,
    force_cartera: bool = False,
    is_fin_de_mes: bool = False,
    corte_fecha: str | None = None,
) -> int:
    t0 = perf_counter()
    logger.info("==================================================")
    logger.info("=== EJECUCIÓN GENERAL DE TODOS LOS PIPELINES   ===")
    logger.info("==================================================")

    steps = [
        ("REFERENCIAS", lambda: run_referencias(force=force)),
        ("CARTERA", lambda: run_cartera(force=force or force_cartera)),
        ("QUERY", lambda: run_query(corte_fecha=corte_fecha, is_fin_de_mes=is_fin_de_mes, force=force)),
        ("PROYECCION", lambda: run_proyeccion(force=force)),
        ("GD20", lambda: run_gd20(is_fin_de_mes=is_fin_de_mes, corte_fecha=corte_fecha, force=force)),
        ("VENTAS BI (Transformación BD)", lambda: run_ventas_bi(do_export=False)),
        ("DESPACHO BI (Transformación BD)", lambda: run_despacho_bi(do_export=False)),
        ("DESPACHO MES (Transformación BD)", lambda: run_despacho_mes(corte_fecha=corte_fecha, is_fin_de_mes=is_fin_de_mes, do_export=False)),
        ("EXPORTACIONES (En Paralelo)", lambda: export_all_reports_parallel(corte_fecha=corte_fecha) if corte_fecha else export_all_reports_parallel()),
    ]

    for name, func in steps:
        logger.info("--> Ejecutando etapa: %s", name)
        try:
            func()
        except Exception as exc:
            logger.error("Fallo crítico en etapa %s: %s", name, exc)
            try:
                from itacamba_reportes.core.notifications import notify_error_alert_from_env
                notify_error_alert_from_env(stage=f"CLI run-all: {name}", error_message=str(exc))
            except Exception:
                pass
            return 1

    logger.info("==================================================")
    logger.info("=== TODOS LOS PIPELINES COMPLETADOS EN %.2fs ===", perf_counter() - t0)
    logger.info("==================================================")
    return 0


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = list(sys.argv[1:])
    if not argv:
        argv = ["run-all"]
    elif len(argv) >= 2 and argv[0] == "run" and argv[1] == "all":
        argv = ["run-all"] + argv[2:]
    elif len(argv) >= 2 and argv[0] == "clean" and argv[1] == "db":
        argv = ["clean-db"] + argv[2:]
    elif len(argv) >= 2 and argv[0] == "init" and argv[1] == "db":
        argv = ["init-db"] + argv[2:]
    elif len(argv) >= 2 and argv[0] == "test" and argv[1] == "db":
        argv = ["test-db"] + argv[2:]
    elif len(argv) >= 2 and argv[0] == "test" and argv[1] == "sap":
        argv = ["test-sap"] + argv[2:]
    elif argv and argv[0] in ("run_all", "all"):
        argv = ["run-all"] + argv[1:]
    elif argv and argv[0] in ("clean_db", "cleandb"):
        argv = ["clean-db"] + argv[1:]
    elif argv and argv[0] in ("init_db", "initdb"):
        argv = ["init-db"] + argv[1:]
    elif argv and argv[0] in ("test_db", "testdb"):
        argv = ["test-db"] + argv[1:]
    elif argv and argv[0] in ("test_sap", "testsap"):
        argv = ["test-sap"] + argv[1:]

    parser = argparse.ArgumentParser(
        prog="itacamba-reportes",
        description="Pipeline ETL Database-First Itacamba Reportes.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("test-db", help="Verifica la conexión a SQL Server y muestra diagnóstico detallado.")
    p_test_sap = subparsers.add_parser("test-sap", help="Verifica la conexión a SAP GUI y realiza diagnóstico o prueba de descarga.")
    p_test_sap.add_argument(
        "--action",
        choices=["diagnostic", "launch", "login", "logout", "full-auth", "kill", "download", "batch", "validate-config"],
        default=None,
        help="Acción específica a ejecutar.",
    )
    p_test_sap.add_argument("--check-only", action="store_true", help="Solo verifica la conexión sin descargar.")
    p_test_sap.add_argument("--task", choices=["gd20", "zbcs", "query", "all", "batch", "cartera"], default=None, help="Tarea a descargar (gd20, zbcs, query, all, cartera).")
    p_test_sap.add_argument("--out-dir", default=None, help="Carpeta de destino para el archivo descargado.")
    p_test_sap.add_argument("--period-low", "-p", default=None, help="Periodo/mes inicio para GD20.")
    p_test_sap.add_argument("--period-high", default=None, help="Periodo/mes fin para GD20.")
    p_test_sap.add_argument("--year", "-y", default=None, help="Ejercicio / Año contable para GD20.")
    p_test_sap.add_argument("--date-from", default=None, help="Fecha inicio para Query (DD.MM.YYYY o YYYY-MM-DD).")
    p_test_sap.add_argument("--date-to", default=None, help="Fecha fin para Query (DD.MM.YYYY o YYYY-MM-DD).")
    p_test_sap.add_argument("--keep-open", action="store_true", help="Deja la sesión SAP abierta en Easy Access al finalizar.")
    p_test_sap.add_argument("--kill", action="store_true", help="Cierra procesos de SAPGUI/SAP Logon activos.")
    p_test_sap.add_argument("--launch", action="store_true", help="Inicia SAP Logon y conecta al ambiente automáticamente.")
    p_clean = subparsers.add_parser("clean-db", help="Limpia/vacia todas las tablas de la base de datos y resetea firmas de estado.")
    p_clean.add_argument("--force", "-y", action="store_true", help="Omite la confirmación interactiva.")
    p_clean.add_argument("--drop", action="store_true", help="Elimina las tablas por completo (DROP) en lugar de solo vaciarlas (TRUNCATE/DELETE).")
    p_init = subparsers.add_parser("init-db", help="Aplica las migraciones Alembic pendientes y asegura todas las tablas.")
    p_init.add_argument("--reset-alembic", action="store_true", help="Reinicia tabla de versiones de Alembic para forzar ejecución limpia.")
    p_ref = subparsers.add_parser("run-referencias", help="Pipeline REFERENCIAS -> tablas int_ref_*.")
    p_ref.add_argument("--force", action="store_true", help="Fuerza re-ingesta ignorando cache.")
    p_cartera = subparsers.add_parser("run-cartera", help="Pipeline CARTERA -> stg_cartera + int_cartera.")
    p_cartera.add_argument("--force", action="store_true", help="Fuerza re-ingesta aunque el archivo no haya cambiado.")
    p_qry = subparsers.add_parser("run-query", help="Pipeline QUERY ZVCSD381 -> stg_query + int_query.")
    p_qry.add_argument("--fin-de-mes", action="store_true", help="Conserva las filas del día de corte para cierre.")
    p_qry.add_argument("--corte-fecha", default=None, help="Fecha de corte YYYY-MM-DD.")
    p_qry.add_argument("--force", action="store_true", help="Fuerza re-ingesta ignorando cache.")
    p_proy = subparsers.add_parser("run-proyeccion", help="Pipeline PROYECCIÓN -> stg_proyeccion.")
    p_proy.add_argument("--force", action="store_true", help="Fuerza re-ingesta ignorando cache.")

    p_gd20 = subparsers.add_parser("run-gd20", help="Pipeline GD20 (BASE PANEL) -> int_gd20 + int_ventas_bi.")
    p_gd20.add_argument("--fin-de-mes", action="store_true", help="Conserva las filas de la fecha actual para cierre.")
    p_gd20.add_argument("--force", action="store_true", help="Fuerza la ejecución completa (compatibilidad).")
    p_gd20.add_argument("--corte-fecha", default=None, help="Fecha de corte YYYY-MM-DD para excluir filas de esa fecha en adelante.")

    subparsers.add_parser("run-ventas-bi", help="Pipeline VENTAS BI -> acumula histórico SCD2 y exporta.")
    subparsers.add_parser("run-despacho-bi", help="Pipeline DESPACHO BI -> acumula histórico real y exporta.")
    p_dmes = subparsers.add_parser("run-despacho-mes", help="Pipeline DESPACHO MES -> resumen mensual y proyección.")
    p_dmes.add_argument("--fin-de-mes", action="store_true", help="Incluye todos los días hasta el cierre.")
    p_dmes.add_argument("--corte-fecha", default=None, help="Fecha de corte YYYY-MM-DD.")
    subparsers.add_parser("export-historial", help="Exporta HISTORIAL VENTAS.xlsx (hojas VENTAS y DESPACHOS) para Power BI.")

    p_all = subparsers.add_parser("run-all", help="Ejecuta todos los pipelines con exportaciones en paralelo.")
    p_all.add_argument("--fin-de-mes", action="store_true", help="Conserva las filas de la fecha actual para cierre.")
    p_all.add_argument("--force", action="store_true", help="Fuerza la ejecución completa (compatibilidad).")
    p_all.add_argument("--force-cartera", action="store_true", help="Fuerza re-ingesta de cartera ignorando cache.")
    p_all.add_argument("--corte-fecha", default=None, help="Fecha de corte YYYY-MM-DD para excluir filas de esa fecha en adelante.")

    p_sap = subparsers.add_parser("download-sap", help="Descarga un reporte parametrizado desde SAP GUI.")
    p_sap.add_argument("--transaction", "-t", required=True, help="Código de transacción SAP (ej: gd20, zbcs, sq01).")
    p_sap.add_argument("--variant", "-v", default=None, help="Nombre de la variante guardada en SAP.")
    p_sap.add_argument("--ledger", "-l", default=None, help="Ledger contable (ej: VC).")
    p_sap.add_argument("--period-low", "-p", default=None, help="Periodo/mes inicio (ej: 9).")
    p_sap.add_argument("--period-high", default=None, help="Periodo/mes fin (ej: 9).")
    p_sap.add_argument("--year", "-y", default=None, help="Año de ejercicio contable (ej: 2026).")
    p_sap.add_argument("--date-from", default=None, help="Fecha inicio para transacciones tipo query/despachos.")
    p_sap.add_argument("--date-to", default=None, help="Fecha fin para transacciones tipo query/despachos.")
    p_sap.add_argument("--layout", default=None, help="Nombre de layout ALV (ej: //AVRILGD20).")
    p_sap.add_argument("--layout-row", type=int, default=None, help="Fila de layout ALV a seleccionar.")
    p_sap.add_argument("--filename", "-f", default="EXPORT", help="Nombre base del archivo a exportar.")
    p_sap.add_argument("--target-dir", "-d", default=None, help="Directorio destino donde ubicar el archivo.")
    p_sap.add_argument("--keep-open", action="store_true", help="Mantiene abierta la sesión SAP en Easy Access sin ejecutar /nex ni cerrar saplogon.exe.")

    subparsers.add_parser("ui", help="Inicia la interfaz gráfica de usuario en ventana de escritorio.")

    args = parser.parse_args(argv)

    try:
        if args.command == "ui":
            from itacamba_reportes.ui import launch_gui
            return launch_gui()

        if args.command == "download-sap":
            from itacamba_reportes.core.settings import EnvConfig
            from itacamba_reportes.sap import SapDownloadConfig, SapSessionManager, CONFIG_CARTERA, CONFIG_GD20, CONFIG_QUERY
            from itacamba_reportes.sap.actions import (
                execute_download_all_sap,
                execute_download_report,
                finalize_sap_session,
            )

            session_mgr = SapSessionManager()
            tx = (args.transaction or "").strip().lower()
            close_at_end = not bool(args.keep_open)
            resolved_target_dir = args.target_dir or EnvConfig.require_dynamic_inputs_path()

            if tx == "cartera":
                CONFIG_CARTERA.to_download_config(target_dir=resolved_target_dir)
                return 1

            if tx in ("all", "batch", "todos"):
                execute_download_all_sap(
                    session_manager=session_mgr,
                    target_dir=resolved_target_dir,
                    period_gd20=args.period_low,
                    period_high_gd20=args.period_high,
                    year_gd20=args.year,
                    date_from_query=args.date_from,
                    date_to_query=args.date_to,
                    close_at_end=close_at_end,
                )
                return 0

            if tx in ("zvcsd381", "zbcs", "query"):
                cfg = CONFIG_QUERY.to_download_config(
                    target_dir=resolved_target_dir,
                    date_from_override=args.date_from,
                    date_to_override=args.date_to,
                    period_override=args.period_low,
                )
                if args.variant:
                    cfg.variant = args.variant
                if args.layout_row is not None:
                    cfg.layout_row = args.layout_row
                if args.filename and args.filename != "EXPORT":
                    cfg.export_filename = args.filename
            elif tx == "gd20":
                cfg = CONFIG_GD20.to_download_config(
                    target_dir=resolved_target_dir,
                    period_override=args.period_low,
                    period_high_override=args.period_high,
                    year_override=args.year,
                )
                if args.variant:
                    cfg.variant = args.variant
                if args.ledger:
                    cfg.ledger = args.ledger
                if args.layout:
                    cfg.layout_name = args.layout
                if args.layout_row is not None:
                    cfg.layout_row = args.layout_row
                if args.filename and args.filename != "EXPORT":
                    cfg.export_filename = args.filename
            else:
                cfg = SapDownloadConfig(
                    transaction=args.transaction,
                    variant=args.variant,
                    ledger=args.ledger,
                    period_low=args.period_low,
                    period_high=args.period_high,
                    year_low=args.year,
                    date_from=args.date_from,
                    date_to=args.date_to,
                    layout_name=args.layout,
                    layout_row=args.layout_row,
                    export_filename=args.filename,
                    target_dir=resolved_target_dir,
                )

            session_mgr.ensure_connected_and_ready(auto_launch=True)
            try:
                execute_download_report(session_mgr, cfg)
            finally:
                finalize_sap_session(session_mgr, close_at_end=close_at_end)
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

        if args.command == "test-sap":
            root_dir = Path(__file__).resolve().parents[2]
            scripts_dir = root_dir / "scripts"
            if str(scripts_dir) not in sys.path:
                sys.path.insert(0, str(scripts_dir))
            from test_sap import main as run_test_sap
            test_args = []
            if getattr(args, "action", None):
                test_args.extend(["--action", args.action])
            if getattr(args, "check_only", False):
                test_args.append("--check-only")
            if getattr(args, "task", None):
                test_args.extend(["--task", args.task])
            if getattr(args, "out_dir", None):
                test_args.extend(["--out-dir", args.out_dir])
            if getattr(args, "period_low", None):
                test_args.extend(["--period-low", args.period_low])
            if getattr(args, "period_high", None):
                test_args.extend(["--period-high", args.period_high])
            if getattr(args, "year", None):
                test_args.extend(["--year", args.year])
            if getattr(args, "date_from", None):
                test_args.extend(["--date-from", args.date_from])
            if getattr(args, "date_to", None):
                test_args.extend(["--date-to", args.date_to])
            if getattr(args, "keep_open", False):
                test_args.append("--keep-open")
            if getattr(args, "kill", False):
                test_args.append("--kill")
            if getattr(args, "launch", False):
                test_args.append("--launch")
            return run_test_sap(test_args)

        if args.command == "init-db":
            upgrade_db(reset_alembic=getattr(args, "reset_alembic", False))
            return 0

        if args.command == "clean-db":
            from itacamba_reportes.core.db.schema import truncate_all_tables, drop_all_tables
            if not getattr(args, "force", False):
                accion = "ELIMINAR" if getattr(args, "drop", False) else "VACIAR"
                confirm = input(f"ADVERTENCIA: Se van a {accion} todas las tablas en la Base de Datos. ¿Continuar? (s/N): ").strip().lower()
                if confirm not in ("s", "si", "y", "yes"):
                    logger.info("Operación cancelada por el usuario.")
                    return 0
            if getattr(args, "drop", False):
                dropped = drop_all_tables(reset_state=True)
                logger.info("Base de datos reseteada: %d tablas eliminadas.", len(dropped))
            else:
                cleared = truncate_all_tables(reset_state=True)
                logger.info("Base de datos limpiada: %d tablas vaciadas.", len(cleared))
            return 0

        ensure_schema_current()

        if args.command == "run-referencias":
            run_referencias(force=getattr(args, "force", False))
        elif args.command == "run-cartera":
            run_cartera(force=getattr(args, "force", False))
        elif args.command == "run-query":
            run_query(is_fin_de_mes=args.fin_de_mes, corte_fecha=args.corte_fecha, force=getattr(args, "force", False))
        elif args.command == "run-proyeccion":
            run_proyeccion(force=getattr(args, "force", False))
        elif args.command == "run-gd20":
            run_gd20(is_fin_de_mes=args.fin_de_mes, corte_fecha=args.corte_fecha, force=getattr(args, "force", False))
            run_ventas_bi()
        elif args.command == "run-ventas-bi":
            run_ventas_bi()
        elif args.command == "run-despacho-bi":
            run_despacho_bi()
        elif args.command == "run-despacho-mes":
            run_despacho_mes(is_fin_de_mes=args.fin_de_mes, corte_fecha=args.corte_fecha)
        elif args.command == "export-historial":
            export_historial_ventas()
        elif args.command == "run-all":
            force_all = getattr(args, "force", False)
            force_c = getattr(args, "force_cartera", False)
            return run_all(force=force_all, force_cartera=force_c, is_fin_de_mes=args.fin_de_mes, corte_fecha=args.corte_fecha)
        return 0
    except Exception as exc:
        logger.exception("Error en ejecución de %s: %s", args.command, exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
