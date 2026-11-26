from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from itacamba_reportes.core.logging_config import setup_logging
from itacamba_reportes.core.settings import EnvConfig
from itacamba_reportes.sap.config import (
    CONFIG_CARTERA,
    CONFIG_GD20,
    CONFIG_QUERY,
    SapDownloadConfig,
)
from itacamba_reportes.sap.session import SapSessionManager
from itacamba_reportes.sap.selectors import SELECTORES_SAP
from itacamba_reportes.sap.actions.login_action import execute_login
from itacamba_reportes.sap.actions.logout_action import execute_logout
from itacamba_reportes.sap.actions.download_action import (
    execute_download_all_sap,
    execute_download_report,
    finalize_sap_session,
)

logger = setup_logging()

SAP_TASKS_FILE = ROOT / "storage" / "sap_tasks.json"


def check_sap_processes() -> list[str]:
    # Verifica si los ejecutables de SAP estan activos en Windows.
    running: list[str] = []
    try:
        output = subprocess.check_output(
            ["tasklist", "/FI", "IMAGENAME eq sap*", "/FO", "CSV", "/NH"],
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        for line in output.splitlines():
            line = line.strip().strip('"')
            if line and "sap" in line.lower():
                parts = [p.strip().strip('"') for p in line.split('","')]
                if parts:
                    running.append(parts[0])
    except Exception:
        pass
    return sorted(list(set(running)))


def get_active_sap_session_info() -> dict[str, str] | None:
    # Obtiene datos de la sesion SAP activa via COM.
    try:
        import win32com.client
    except ImportError:
        print("[!] pywin32 no esta instalado en el entorno virtual.")
        return None

    try:
        sap_gui_auto = win32com.client.GetObject("SAPGUI")
        application = sap_gui_auto.GetScriptingEngine
        if not application or application.Children.Count == 0:
            return {"error": "SAPGUI detectado pero no hay conexiones abiertas a ningun ambiente."}

        connection = application.Children(0)
        if connection.Children.Count == 0:
            return {"error": "Conexion SAP abierta pero sin ventanas/sesiones activas."}

        session = connection.Children(0)
        info = {
            "system": getattr(session.Info, "SystemName", "N/A"),
            "client": getattr(session.Info, "Client", "N/A"),
            "user": getattr(session.Info, "User", "N/A"),
            "transaction": getattr(session.Info, "Transaction", "N/A"),
            "program": getattr(session.Info, "ProgramName", "N/A"),
            "window_title": getattr(session.ActiveWindow, "Text", "N/A") if hasattr(session, "ActiveWindow") else "N/A",
        }
        return info
    except Exception as exc:
        return {"error": str(exc)}


def action_diagnostic() -> bool:
    print("\n==================================================")
    print("=== 1. DIAGNÓSTICO DE CONECTIVIDAD SAP GUI    ===")
    print("==================================================")
    print(f"Ambiente configurado : {EnvConfig.SAP_AMBIENT}")
    print(f"Ruta SAP Logon       : {EnvConfig.SAP_LOGON_PATH}")
    print(f"Sistema configurado  : {EnvConfig.SAP_SISTEMA}")
    print(f"Usuario configurado  : {EnvConfig.SAP_USER}")
    print("--------------------------------------------------")

    processes = check_sap_processes()
    if processes:
        print(f"[OK] Procesos SAP activos en Windows: {', '.join(processes)}")
    else:
        print("[AVISO] No se detectó 'saplogon.exe' en ejecución.")

    print("Probando vinculación COM con 'Sapgui.ScriptingCtrl' / 'SAPGUI'...")
    t0 = perf_counter()
    info = get_active_sap_session_info()
    elapsed = perf_counter() - t0

    if not info:
        print(f"[ERROR] No se pudo vincular al motor COM ({elapsed:.2f}s).")
        return False

    if "error" in info:
        print(f"[ESTADO] {info['error']} ({elapsed:.2f}s)")
        print("\nSugerencia: Ejecute la opción de Abrir y Conectar Ambiente.")
        print("==================================================")
        return False

    print(f"[OK] ¡Conexión exitosa a la sesión activa en {elapsed:.2f}s!")
    print(f"     Sistema SAP        : {info['system']}")
    print(f"     Mandante/Client    : {info['client']}")
    print(f"     Usuario activo     : {info['user']}")
    print(f"     Transacción actual : {info['transaction']}")
    print(f"     Ventana actual     : {info['window_title']}")
    print("==================================================")
    return True


def action_launch_and_connect(ambient: str | None = None) -> bool:
    target_ambient = (ambient or EnvConfig.SAP_AMBIENT).strip().strip('"').strip("'")
    print("\n==================================================")
    print(f"=== 2. ABRIR SAP LOGON Y CONECTAR AMBIENTE     ===")
    print("==================================================")
    print(f"Ambiente objetivo: '{target_ambient}'")
    print(f"Ejecutable       : {EnvConfig.SAP_LOGON_PATH}")
    print("--------------------------------------------------")

    mgr = SapSessionManager()
    t0 = perf_counter()
    try:
        if not SapSessionManager.is_saplogon_running():
            print("-> SAP Logon no está corriendo. Iniciando ejecutable...")
            mgr.launch_saplogon(sap_path=EnvConfig.SAP_LOGON_PATH, wait_timeout=30.0)
            print("[OK] SAP Logon iniciado y motor de Scripting enganchado.")
        else:
            print("[OK] SAP Logon ya se encuentra en ejecución.")

        print(f"-> Abriendo conexión hacia ambiente '{target_ambient}'...")
        session = mgr.open_connection(ambient=target_ambient, sync=True)
        mgr.maximize()
        elapsed = perf_counter() - t0

        wnd_title = ""
        try:
            wnd_title = session.ActiveWindow.Text or ""
        except Exception:
            pass

        print(f"[OK] Conexión establecida exitosamente en {elapsed:.2f}s!")
        print(f"     Ventana activa: {wnd_title}")
        print("==================================================")
        return True
    except Exception as exc:
        elapsed = perf_counter() - t0
        print(f"[ERROR] Falló al abrir o conectar ({elapsed:.2f}s): {exc}")
        print("==================================================")
        return False


def action_login() -> bool:
    print("\n==================================================")
    print("=== 3. PROBAR LOGIN / AUTENTICACIÓN EN SAP     ===")
    print("==================================================")
    print(f"Usuario objetivo : {EnvConfig.SAP_USER}")
    print("--------------------------------------------------")

    mgr = SapSessionManager()
    t0 = perf_counter()
    try:
        session = mgr.session
        mgr.maximize()
        time.sleep(1.0)

        # 1. Comprobar si hay modal emergente inicial (ej. avisos)
        if getattr(session.ActiveWindow, "Name", "") != "wnd[0]":
            print("-> Detectada ventana modal / popup...")
            if mgr.handle_multilogon_if_present():
                print("[OK] Popup de Multi-Logon gestionado.")
            else:
                try:
                    session.findById(f"{session.ActiveWindow.Name}/tbar[0]/btn[0]").press()
                    time.sleep(0.5)
                except Exception:
                    pass

        # 2. Esperar a que el campo de login este disponible (timeout de 5s)
        print("-> Verificando pantalla de autenticación en SAP GUI...")
        has_login_field = mgr.element_exists(SELECTORES_SAP.login.usuario, timeout=5.0)

        if has_login_field:
            print("-> Pantalla de login detectada:")
            print(f"   [1/2] Ingresando Usuario  : {EnvConfig.SAP_USER}")
            print(f"   [2/2] Ingresando Clave    : ******")
            execute_login(
                mgr,
                user=EnvConfig.SAP_USER,
                password=EnvConfig.SAP_PASSWORD,
            )
            print("[OK] Credenciales ingresadas y confirmadas con Enter.")
        else:
            usr_session = getattr(session.Info, "User", "").strip()
            client_session = getattr(session.Info, "Client", "000")
            if usr_session and client_session != "000":
                print(f"[OK] Sesión ya autenticada en SAP: Usuario={usr_session}, Mandante={client_session}.")
            else:
                print("-> No se detectó campo de usuario de inmediato. Intentando ejecución de login...")
                execute_login(
                    mgr,
                    user=EnvConfig.SAP_USER,
                    password=EnvConfig.SAP_PASSWORD,
                )

        time.sleep(1.5)
        info = get_active_sap_session_info()
        elapsed = perf_counter() - t0
        print(f"\n>>> ESTADO FINAL TRAS LOGIN ({elapsed:.2f}s) <<<")
        if info and "error" not in info:
            print(f"     Usuario en sesión  : {info.get('user')}")
            print(f"     Mandante activo    : {info.get('client')}")
            print(f"     Sistema            : {info.get('system')}")
            print(f"     Transacción actual : {info.get('transaction')}")
            print(f"     Ventana actual     : {info.get('window_title')}")
        print("==================================================")
        return True
    except Exception as exc:
        elapsed = perf_counter() - t0
        print(f"[ERROR] Falló la verificación de Login ({elapsed:.2f}s): {exc}")
        return False


def action_logout(close_logon: bool = True) -> bool:
    print("\n==================================================")
    print("=== 4. CERRAR SESIÓN Y PROCESO SAP (/nex)      ===")
    print("==================================================")
    mgr = SapSessionManager()
    t0 = perf_counter()
    try:
        # Paso 1: Enviar /nex para cerrar la sesion en el servidor
        print("-> Paso 1: Desconectando sesión en SAP (/nex)...")
        try:
            execute_logout(mgr)
            print("[OK] Sesión de servidor SAP cerrada.")
        except Exception as exc:
            logger.info("Nota al cerrar sesión (/nex): %s", exc)

        time.sleep(1.0)

        # Paso 2: Cerrar el ejecutable saplogon.exe de Windows
        if close_logon:
            print("-> Paso 2: Cerrando ejecutable 'saplogon.exe' de Windows...")
            killed = mgr.kill_sap_processes()
            if killed:
                print(f"[OK] Procesos finalizados en Windows: {', '.join(killed)}")
            else:
                print("[OK] Procesos SAP finalizados limpiamente.")

        elapsed = perf_counter() - t0
        print(f"\n[OK] ¡Cierre completo finalizado con éxito en {elapsed:.2f}s!")
        print("==================================================")
        return True
    except Exception as exc:
        elapsed = perf_counter() - t0
        print(f"[ERROR] Error al cerrar SAP ({elapsed:.2f}s): {exc}")
        print("==================================================")
        return False


def action_full_auth_cycle() -> bool:
    print("\n==================================================")
    print("=== CICLO COMPLETO AUTOMATIZADO (1 A 4)        ===")
    print("==================================================")
    print("Paso 1: Abrir SAP Logon y conectar ambiente...")
    if not action_launch_and_connect():
        return False

    print("\nPaso 2: Realizar Login con credenciales...")
    if not action_login():
        return False

    print("\nPaso 3: Diagnóstico y validación de sesión activa...")
    action_diagnostic()

    print("\nPaso 4: Desloguear (/nex) y Cerrar proceso saplogon.exe de Windows...")
    action_logout(close_logon=True)
    print("\n>>> ¡FLUJO DE AUTENTICACIÓN Y CIERRE COMPLETO EXITOSO! <<<")
    return True


def action_kill_processes() -> bool:
    print("\n==================================================")
    print("=== CERRAR PROCESOS SAP (RESET FORZADO)        ===")
    print("==================================================")
    killed = SapSessionManager.kill_sap_processes()
    if killed:
        print(f"[OK] Procesos finalizados con éxito: {', '.join(killed)}")
    else:
        print("[INFO] No había ningún proceso de saplogon o sapgui en ejecución.")
    print("==================================================")
    return True


def load_tasks() -> list[dict]:
    if SAP_TASKS_FILE.exists():
        try:
            with open(SAP_TASKS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning("No se pudo cargar %s: %s", SAP_TASKS_FILE, exc)
    return []


def test_download_task(
    task_key: str,
    out_dir: Path | None = None,
    period_low: str | None = None,
    period_high: str | None = None,
    year: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    close_at_end: bool = True,
) -> int:
    key = task_key.lower().strip()
    if key == "cartera":
        print(f"[AVISO] {CONFIG_CARTERA.source_note}")
        print("        Llega por correo via Power Automate; no requiere script SAP GUI.")
        return 1

    target_directory = out_dir or (ROOT / "storage" / "raw" / "test_sap")
    target_directory.mkdir(parents=True, exist_ok=True)

    tasks = load_tasks()
    task_lookup = "zbcs" if key in ("zbcs", "query") else key
    task = next((t for t in tasks if t.get("id", "").lower() == task_lookup), None)
    task_vals: dict[str, object] = {}
    if task:
        campos = {c.get("id"): c.get("valor") for c in task.get("campos", [])}
        for field_id in ("variante", "ledger", "sociedad", "periodo", "ejercicio", "desde", "hasta", "layout", "layout_row"):
            val = campos.get(field_id)
            if val is None or (isinstance(val, str) and not val.strip()):
                val = task.get(field_id)
            if isinstance(val, str):
                val = val.strip()
            if val not in (None, ""):
                task_vals[field_id] = val
        if dest := task.get("destino"):
            if str(dest).strip():
                task_vals["destino"] = str(dest).strip()

    # 1. Resolver configuracion base tipada desde src/itacamba_reportes/sap/config.py
    if key == "gd20":
        p_low_eff = period_low or (str(task_vals["periodo"]) if "periodo" in task_vals else None)
        p_high_eff = period_high or p_low_eff
        y_eff = year or (str(task_vals["ejercicio"]) if "ejercicio" in task_vals else None)
        cfg = CONFIG_GD20.to_download_config(
            target_dir=target_directory,
            period_override=p_low_eff,
            period_high_override=p_high_eff,
            year_override=y_eff,
        )
        if "variante" in task_vals:
            cfg.variant = str(task_vals["variante"])
        if "ledger" in task_vals and str(task_vals["ledger"]).upper() != "N/A":
            cfg.ledger = str(task_vals["ledger"])
        if "layout" in task_vals:
            cfg.layout_name = str(task_vals["layout"])
        if "layout_row" in task_vals:
            try:
                cfg.layout_row = int(str(task_vals["layout_row"]))
            except Exception:
                pass
        titulo = "Ventas Contables (GD20)"
    elif key in ("zbcs", "query"):
        d_from_eff = date_from or (str(task_vals["desde"]) if "desde" in task_vals else None)
        d_to_eff = date_to or (str(task_vals["hasta"]) if "hasta" in task_vals else None)
        cfg = CONFIG_QUERY.to_download_config(
            target_dir=target_directory,
            date_from_override=d_from_eff,
            date_to_override=d_to_eff,
        )
        if "variante" in task_vals:
            cfg.variant = str(task_vals["variante"])
        if "sociedad" in task_vals:
            cfg.sociedad = str(task_vals["sociedad"])
        titulo = "Despachos Query (ZVCSD381 · 3 meses atrás)"
    else:
        print(f"[ERROR] Tarea '{task_key}' no reconocida. Opciones válidas: gd20, zbcs, query, all, cartera")
        return 1

    if "destino" in task_vals:
        cfg.export_filename = str(task_vals["destino"])

    # 2. Asegurar conexion y login una sola vez en la misma sesion
    print(f"\n--> Preparando flujo completo separado para: {titulo}")
    print(f"    Transacción   : {cfg.transaction}")
    if key == "gd20":
        print(f"    Ledger        : {cfg.ledger or '(N/A)'}")
        print(f"    Variante      : {cfg.variant or '(N/A)'}")
        print(f"    Ejercicio     : {cfg.year_low or '(Variante)'}")
        print(f"    Período       : {cfg.period_low} .. {cfg.period_high}")
        print(f"    Layout ALV    : {cfg.layout_name or cfg.layout_row or '(Default)'}")
    else:
        print(f"    Sociedad      : {cfg.sociedad or '4253'}")
        print(f"    Disposición   : {cfg.variant or '/IM'}")
        print(f"    Rango Fechas  : {cfg.date_from} -> {cfg.date_to}")
    print(f"    Archivo       : {cfg.export_filename}")
    print(f"    Destino       : {target_directory}")
    print(f"    Cierre final  : {'Sí (/nex + kill SAP)' if close_at_end else 'No (queda en Easy Access)'}")

    session_mgr = SapSessionManager()
    t0 = perf_counter()
    try:
        print("\n-> [1/3] Verificando conexión y autenticación SAP...")
        session_mgr.ensure_connected_and_ready(auto_launch=True)
        print("-> [2/3] Ejecutando descarga automatizada en SAP GUI...")
        res_file = execute_download_report(session_mgr, cfg)
        elapsed = perf_counter() - t0
        print(f"\n>>> ¡DESCARGA COMPLETADA EXITOSAMENTE EN {elapsed:.2f}s! <<<")
        print(f"Archivo generado   : {res_file}")
        if res_file.exists():
            print(f"Tamaño del archivo : {res_file.stat().st_size / 1024:.1f} KB")
        return 0
    except Exception as exc:
        elapsed = perf_counter() - t0
        print(f"\n[ERROR] Falló la descarga de SAP ({elapsed:.2f}s): {exc}")
        logger.exception("Error en prueba de descarga SAP: %s", exc)
        return 1
    finally:
        print(f"-> [3/3] Finalizando sesión SAP (close_at_end={close_at_end})...")
        finalize_sap_session(session_mgr, close_at_end=close_at_end)


def action_validate_config() -> int:
    from itacamba_reportes.ui.bridge import BotBridge

    print("\n======================================================================")
    print("=== VALIDACIÓN INTEGRAL DE CONFIGURACIÓN (.env, BD, SAP, PERFIL)   ===")
    print("======================================================================")
    report = BotBridge().validate_web_configuration()
    for item in report.get("checks", []):
        st = {"ok": "[OK]", "warn": "[AVISO]", "error": "[ERROR]"}.get(item.get("status"), "[INFO]")
        print(f"  {st:<8} {item.get('label')}: {item.get('detail')}")
    print("----------------------------------------------------------------------")
    sap_res = report.get("sap_resolved", {})
    if sap_res:
        print(f"  Perfil activo : {sap_res.get('profile_name')} ({sap_res.get('mes_ejecucion') or 'rango'})")
        print(f"  GD20 resuelto : Ejercicio {sap_res.get('gd20_year')} | Período {sap_res.get('gd20_period')} | Layout {sap_res.get('gd20_layout')}")
        print(f"  Query resuelto: ZVCSD381 {sap_res.get('query_date_from')} -> {sap_res.get('query_date_to')} (3 meses atrás)")
    print("======================================================================")
    print(f"Resumen: {report.get('summary')}")
    return 0 if report.get("ok") else 1


def test_download_all_batch(
    out_dir: Path | None = None,
    period_low: str | None = None,
    period_high: str | None = None,
    year: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    close_at_end: bool = True,
) -> int:
    target_directory = out_dir or (ROOT / "storage" / "raw" / "test_sap")
    target_directory.mkdir(parents=True, exist_ok=True)

    print("\n======================================================================")
    print("=== DESCARGA CONJUNTA SAP: GD20 (Mes/Año) + QUERY (3 Meses)        ===")
    print("======================================================================")
    print("Este flujo realiza un único inicio de sesión, ejecuta ambas transacciones")
    print("volviendo limpiamente al menú principal entre ellas, y cierra al final.")
    print("----------------------------------------------------------------------")

    t0 = perf_counter()
    try:
        results = execute_download_all_sap(
            target_dir=target_directory,
            period_gd20=period_low,
            period_high_gd20=period_high,
            year_gd20=year,
            date_from_query=date_from,
            date_to_query=date_to,
            close_at_end=close_at_end,
        )
        elapsed = perf_counter() - t0
        print(f"\n>>> ¡DESCARGA CONJUNTA COMPLETADA EXITOSAMENTE EN {elapsed:.2f}s! <<<")
        for k, p in results.items():
            sz = p.stat().st_size / 1024 if p.exists() else 0
            print(f"  [{k.upper()}] {p.name} ({sz:.1f} KB) -> {p}")
        return 0
    except Exception as exc:
        elapsed = perf_counter() - t0
        print(f"\n[ERROR] Falló la descarga conjunta ({elapsed:.2f}s): {exc}")
        logger.exception("Error en descarga conjunta SAP: %s", exc)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="test_sap",
        description="Banco de pruebas y automatización SAP GUI Scripting.",
    )
    parser.add_argument(
        "--action",
        choices=["diagnostic", "launch", "login", "logout", "full-auth", "kill", "download", "batch", "validate-config"],
        default=None,
        help="Acción específica a ejecutar.",
    )
    parser.add_argument("--check-only", action="store_true", help="Alias de --action diagnostic.")
    parser.add_argument("--kill", action="store_true", help="Alias de --action kill.")
    parser.add_argument("--launch", action="store_true", help="Alias de --action launch.")
    parser.add_argument(
        "--task",
        choices=["gd20", "zbcs", "query", "cartera", "all", "batch"],
        default=None,
        help="Tarea a descargar cuando action es download o se invoca directamente.",
    )
    parser.add_argument("--out-dir", default=None, help="Carpeta destino de descarga.")
    parser.add_argument("--period-low", "-p", default=None, help="Período inicial GD20 (1..12).")
    parser.add_argument("--period-high", default=None, help="Período final GD20 (1..12).")
    parser.add_argument("--year", "-y", default=None, help="Ejercicio / Año GD20 (ej: 2026).")
    parser.add_argument("--date-from", default=None, help="Fecha desde Query (DD.MM.YYYY o YYYY-MM-DD).")
    parser.add_argument("--date-to", default=None, help="Fecha hasta Query (DD.MM.YYYY o YYYY-MM-DD).")
    parser.add_argument("--keep-open", action="store_true", help="No cerrar SAP al terminar la prueba.")

    args = parser.parse_args(argv)
    close_at_end = not bool(args.keep_open)
    out_path = Path(args.out_dir) if args.out_dir else None

    if args.kill or args.action == "kill":
        action_kill_processes()
        if not args.launch and not args.task and not args.action:
            return 0

    if args.action == "validate-config":
        return action_validate_config()

    if args.launch or args.action == "launch":
        ok = action_launch_and_connect()
        return 0 if ok else 1

    if args.action == "login":
        ok = action_login()
        return 0 if ok else 1

    if args.action == "logout":
        ok = action_logout(close_at_end)
        return 0 if ok else 1

    if args.action == "full-auth":
        ok = action_full_auth_cycle()
        return 0 if ok else 1

    if args.check_only or args.action == "diagnostic":
        ok = action_diagnostic()
        return 0 if ok else 1

    if args.action == "batch" or (args.task and args.task.lower() in ("all", "batch")):
        return test_download_all_batch(
            out_dir=out_path,
            period_low=args.period_low,
            period_high=args.period_high,
            year=args.year,
            date_from=args.date_from,
            date_to=args.date_to,
            close_at_end=close_at_end,
        )

    if args.task or args.action == "download":
        task_id = args.task or "gd20"
        return test_download_task(
            task_id,
            out_dir=out_path,
            period_low=args.period_low,
            period_high=args.period_high,
            year=args.year,
            date_from=args.date_from,
            date_to=args.date_to,
            close_at_end=close_at_end,
        )

    # Menú interactivo
    while True:
        print("\n======================================================================")
        print("  ITACAMBA CEMENTO S.A. - BANCO DE PRUEBAS SAP GUI (RPA)")
        print("======================================================================")
        print(f"Ambiente configurado : {EnvConfig.SAP_AMBIENT}")
        print(f"Ruta SAP Logon       : {EnvConfig.SAP_LOGON_PATH}")
        print(f"Sistema configurado  : {EnvConfig.SAP_SISTEMA}")
        print(f"Usuario configurado  : {EnvConfig.SAP_USER}")
        print("----------------------------------------------------------------------")
        print("Seleccione la prueba que desea ejecutar:")
        print("  --- FASE 1: CONECTIVIDAD, AUTENTICACIÓN Y CIERRE ---")
        print("  1. Diagnóstico rápido de conexión")
        print("  2. Abrir SAP Logon y Conectar Ambiente (Launch & Connect)")
        print("  3. Probar Login (Ingreso de usuario y contraseña)")
        print("  4. Cerrar sesión y proceso SAP (/nex + Cerrar saplogon.exe)")
        print("  5. Ciclo Completo: Abrir -> Login -> Validar -> Logout -> Cerrar SAP")
        print("  6. Cerrar procesos de SAP por la fuerza (Kill / Reset)")
        print("  --- FASE 2: FLUJOS COMPLETOS SEPARADOS Y EN LOTE ---")
        print("  7. Flujo completo separado GD20 (Login -> GD20 -> Menú -> Cierre)")
        print("  8. Flujo completo separado Query ZVCSD381 (Login -> 3 meses -> Menú -> Cierre)")
        print("  9. Flujo conjunto GD20 + Query (1 solo Login -> Menú -> Cierre)")
        print("  10. Validar configuración completa (.env, BD, SAP, Rutas, Perfil)")
        print("  11. Estado de Cartera (correo vía Power Automate)")
        print("  0. Salir")
        print("======================================================================")

        try:
            choice = input("\nIngrese una opción (0-11): ").strip()
            if choice == "1":
                action_diagnostic()
            elif choice == "2":
                action_launch_and_connect()
            elif choice == "3":
                action_login()
            elif choice == "4":
                action_logout(close_logon=True)
            elif choice == "5":
                action_full_auth_cycle()
            elif choice == "6":
                action_kill_processes()
            elif choice == "7":
                test_download_task("gd20", close_at_end=True)
            elif choice == "8":
                test_download_task("zbcs", close_at_end=True)
            elif choice == "9":
                test_download_all_batch(close_at_end=True)
            elif choice == "10":
                action_validate_config()
            elif choice == "11":
                test_download_task("cartera")
            elif choice == "0":
                print("Finalizado.")
                return 0
            else:
                print("Opción no válida. Intente nuevamente.")
        except KeyboardInterrupt:
            print("\nCancelado por el usuario.")
            return 0


if __name__ == "__main__":
    sys.exit(main())
