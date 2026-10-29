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
from itacamba_reportes.sap.config import SapDownloadConfig
from itacamba_reportes.sap.session import SapSessionManager
from itacamba_reportes.sap.selectors import SELECTORES_SAP
from itacamba_reportes.sap.actions.login_action import execute_login
from itacamba_reportes.sap.actions.logout_action import execute_logout
from itacamba_reportes.sap.actions.download_action import execute_download_report

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


def test_download_task(task_key: str, out_dir: Path | None = None) -> int:
    tasks = load_tasks()
    task = next((t for t in tasks if t.get("id", "").lower() == task_key.lower()), None)
    if not task:
        print(f"[ERROR] Tarea '{task_key}' no encontrada en storage/sap_tasks.json.")
        print("Tareas disponibles: " + ", ".join([t.get("id", "") for t in tasks]))
        return 1

    # Asegurar conexion y login antes de descargar
    print("\n-> Verificando sesión activa de SAP...")
    info = get_active_sap_session_info()
    if not info or "error" in info or not info.get("user") or info.get("client") == "000":
        print("-> Sesión no autenticada. Conectando y logueando automáticamente...")
        mgr = SapSessionManager()
        try:
            mgr.ensure_connected_and_ready(auto_launch=True)
            print("[OK] Sesión abierta y autenticada.")
        except Exception as exc:
            print(f"[ERROR] No se pudo asegurar la sesión SAP: {exc}")
            return 1

    target_directory = out_dir or (ROOT / "storage" / "raw" / "test_sap")
    target_directory.mkdir(parents=True, exist_ok=True)

    print(f"\n--> Preparando descarga para: {task.get('titulo', task_key)}")
    print(f"    Transacción : {task.get('tcode')}")
    print(f"    Variante    : {task.get('variante')}")
    print(f"    Layout      : {task.get('layout')}")
    print(f"    Archivo     : {task.get('destino')}")
    print(f"    Destino     : {target_directory}")

    campos = {c.get("id"): c.get("valor") for c in task.get("campos", [])}
    tcode = task.get("tcode", "").lower()

    if tcode == "gd20":
        periodo = campos.get("periodo", time.strftime("%m"))
        cfg = SapDownloadConfig(
            transaction=task.get("tcode", "GD20"),
            variant=task.get("variante", "Prueba_GD20"),
            ledger=task.get("ledger", "VC"),
            period_low=periodo,
            period_high=periodo,
            export_filename=task.get("destino", "GD20.xlsx"),
            target_dir=str(target_directory),
        )
    elif tcode == "zbcs":
        cfg = SapDownloadConfig(
            transaction=task.get("tcode", "ZBCS"),
            variant=task.get("variante", "IM"),
            date_from=campos.get("desde", "2026-10-01"),
            date_to=campos.get("hasta", time.strftime("%Y-%m-%d")),
            export_filename=task.get("destino", "QUERY.xlsx"),
            target_dir=str(target_directory),
        )
    else:
        cfg = SapDownloadConfig(
            transaction=task.get("tcode", "ZSDI"),
            variant=task.get("variante", "CAD_CLIENTE"),
            export_filename=task.get("destino", "CARTERA.xlsx"),
            target_dir=str(target_directory),
        )

    session_mgr = SapSessionManager()
    t0 = perf_counter()
    try:
        print("\nEjecutando automatización de exportación en SAP GUI...")
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="test_sap",
        description="Banco de pruebas y automatización SAP GUI Scripting.",
    )
    parser.add_argument(
        "--action",
        choices=["diagnostic", "launch", "login", "logout", "full-auth", "kill", "download"],
        default=None,
        help="Acción específica a ejecutar.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Alias de --action diagnostic.",
    )
    parser.add_argument(
        "--kill",
        action="store_true",
        help="Alias de --action kill.",
    )
    parser.add_argument(
        "--launch",
        action="store_true",
        help="Alias de --action launch.",
    )
    parser.add_argument(
        "--task",
        choices=["gd20", "zbcs", "cartera"],
        default=None,
        help="Tarea a descargar cuando action es download o se invoca directamente.",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Carpeta destino de descarga.",
    )

    args = parser.parse_args(argv)

    if args.kill or args.action == "kill":
        action_kill_processes()
        if not args.launch and not args.task and not args.action:
            return 0

    if args.launch or args.action == "launch":
        ok = action_launch_and_connect()
        return 0 if ok else 1

    if args.action == "login":
        ok = action_login()
        return 0 if ok else 1

    if args.action == "logout":
        ok = action_logout(close_logon=True)
        return 0 if ok else 1

    if args.action == "full-auth":
        ok = action_full_auth_cycle()
        return 0 if ok else 1

    if args.check_only or args.action == "diagnostic":
        ok = action_diagnostic()
        return 0 if ok else 1

    if args.task or args.action == "download":
        task_id = args.task or "gd20"
        return test_download_task(task_id, out_dir=Path(args.out_dir) if args.out_dir else None)

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
        print("  --- FASE 2: DESCARGAS DE REPORTES ---")
        print("  7. Probar descarga GD20 (Ventas contables)")
        print("  8. Probar descarga ZBCS (Despachos / Query)")
        print("  9. Probar descarga Cartera (ZSDI)")
        print("  0. Salir")
        print("======================================================================")

        try:
            choice = input("\nIngrese una opción (0-9): ").strip()
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
                test_download_task("gd20")
            elif choice == "8":
                test_download_task("zbcs")
            elif choice == "9":
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
