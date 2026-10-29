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
from itacamba_reportes.sap.actions.download_action import execute_download_report

logger = setup_logging()

SAP_TASKS_FILE = ROOT / "storage" / "sap_tasks.json"


def check_sap_processes() -> list[str]:
    # Verifica si los ejecutables de SAP estan activos en el administrador de tareas de Windows.
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
    # Intenta conectarse al objeto COM SAPGUI y extraer metadatos de la sesion activa.
    try:
        import win32com.client
    except ImportError:
        print("[!] pywin32 no esta instalado en el entorno virtual.")
        return None

    try:
        sap_gui_auto = win32com.client.GetObject("SAPGUI")
        application = sap_gui_auto.GetScriptingEngine
        if not application or application.Children.Count == 0:
            return {"error": "SAPGUI encontrado pero no hay conexiones activas abiertas en SAP Logon."}

        connection = application.Children(0)
        if connection.Children.Count == 0:
            return {"error": "Conexion SAP abierta pero no hay ninguna sesion/ventana activa."}

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


def run_sap_diagnostic() -> bool:
    print("==================================================")
    print("=== DIAGNÓSTICO DE CONECTIVIDAD SAP GUI        ===")
    print("==================================================")
    print(f"Ambiente configurado : {EnvConfig.SAP_AMBIENT}")
    print(f"Ruta SAP Logon       : {EnvConfig.SAP_LOGON_PATH}")
    print(f"Mandante / Sistema   : {EnvConfig.SAP_MANDANTE} / {EnvConfig.SAP_SISTEMA}")
    print(f"Usuario configurado  : {EnvConfig.SAP_USER}")
    print("--------------------------------------------------")

    # 1. Procesos
    processes = check_sap_processes()
    if processes:
        print(f"[OK] Procesos SAP activos en Windows: {', '.join(processes)}")
    else:
        print("[AVISO] No se detectó 'saplogon.exe' en ejecución.")

    # 2. Conexión COM
    print("Probando vinculación COM con 'Sapgui.ScriptingCtrl' / 'SAPGUI'...")
    t0 = perf_counter()
    info = get_active_sap_session_info()
    elapsed = perf_counter() - t0

    if not info:
        print(f"[ERROR] No se pudo vincular al motor COM ({elapsed:.2f}s).")
        return False

    if "error" in info:
        print(f"[ESTADO] {info['error']} ({elapsed:.2f}s)")
        print("\nOpciones de resolución:")
        print(f"  a) Iniciar SAP Logon y conectar al ambiente '{EnvConfig.SAP_AMBIENT}'.")
        print("  b) Usar el parámetro --launch para arrancarlo y conectarlo automáticamente.")
        print("==================================================")
        return False

    print(f"[OK] ¡Conexión exitosa al motor SAP GUI en {elapsed:.2f}s!")
    print(f"     Sistema SAP        : {info['system']}")
    print(f"     Mandante/Client    : {info['client']}")
    print(f"     Usuario activo     : {info['user']}")
    print(f"     Transacción actual : {info['transaction']}")
    print(f"     Ventana actual     : {info['window_title']}")
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

    target_directory = out_dir or (ROOT / "storage" / "raw" / "test_sap")
    target_directory.mkdir(parents=True, exist_ok=True)

    print(f"\n--> Preparando prueba de descarga para tarea: {task.get('titulo', task_key)}")
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
        print("\nEjecutando script de descarga en SAP GUI...")
        res_file = execute_download_report(session_mgr, cfg)
        elapsed = perf_counter() - t0
        print(f"\n>>> ¡DESCARGA COMPLETADA EXITOSAMENTE EN {elapsed:.2f}s! <<<")
        print(f"Archivo generado: {res_file}")
        if res_file.exists():
            print(f"Tamaño del archivo: {res_file.stat().st_size / 1024:.1f} KB")
        return 0
    except Exception as exc:
        elapsed = perf_counter() - t0
        print(f"\n[ERROR] Falló la descarga de SAP ({elapsed:.2f}s): {exc}")
        logger.exception("Error en prueba de descarga SAP: %s", exc)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="test_sap",
        description="Diagnóstico y pruebas de automatización SAP GUI Scripting.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Solo verifica la conexión y metadatos de sesión en SAP GUI sin descargar archivos.",
    )
    parser.add_argument(
        "--task",
        choices=["gd20", "zbcs", "cartera"],
        default=None,
        help="Ejecuta la prueba de descarga para una tarea específica (gd20, zbcs, cartera).",
    )
    parser.add_argument(
        "--kill",
        action="store_true",
        help="Cierra por la fuerza cualquier proceso de saplogon.exe o sapgui.exe activo.",
    )
    parser.add_argument(
        "--launch",
        action="store_true",
        help="Arranca SAP Logon automáticamente si está cerrado y abre la conexión al ambiente configurado.",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Carpeta donde se guardará el archivo de prueba descargado.",
    )

    args = parser.parse_args(argv)

    if args.kill:
        print("Cerrando procesos de SAP...")
        killed = SapSessionManager.kill_sap_processes()
        print(f"Procesos finalizados: {killed if killed else 'Ninguno en ejecución'}")
        if not args.launch and not args.task and not args.check_only:
            return 0

    if args.launch:
        print(f"Iniciando SAP Logon y conectando a '{EnvConfig.SAP_AMBIENT}'...")
        try:
            mgr = SapSessionManager()
            mgr.ensure_connected_and_ready(auto_launch=True)
            print("[OK] Conexión y sesión de SAP Logon establecidas exitosamente.")
        except Exception as exc:
            print(f"[ERROR] Fallo al iniciar o conectar a SAP Logon: {exc}")
            return 1

    # 1. Diagnostico previo
    ok = run_sap_diagnostic()
    if not ok and not args.launch:
        print("\nConsejo: Puedes ejecutar con '--launch' para que el script abra SAP Logon automáticamente:")
        print(f"         python scripts/test_sap.py --launch")
        return 1

    if args.check_only:
        return 0

    out_path = Path(args.out_dir) if args.out_dir else None

    # 2. Si se especifico tarea directa
    if args.task:
        return test_download_task(args.task, out_dir=out_path)

    # 3. Menu interactivo
    print("\n¿Qué acción desea realizar?")
    print("  1. Probar descarga GD20 (Ventas contables)")
    print("  2. Probar descarga ZBCS (Despachos / Query)")
    print("  3. Probar descarga Cartera (ZSDI)")
    print("  4. Abrir/Conectar SAP Logon automáticamente")
    print("  5. Cerrar y reiniciar procesos de SAP (Reset)")
    print("  6. Salir (Solo verificar conexión)")

    try:
        choice = input("\nSeleccione una opción (1-6): ").strip()
        if choice == "1":
            return test_download_task("gd20", out_dir=out_path)
        elif choice == "2":
            return test_download_task("zbcs", out_dir=out_path)
        elif choice == "3":
            return test_download_task("cartera", out_dir=out_path)
        elif choice == "4":
            mgr = SapSessionManager()
            mgr.ensure_connected_and_ready(auto_launch=True)
            return 0
        elif choice == "5":
            SapSessionManager.kill_sap_processes()
            print("Procesos SAP cerrados limpiamente.")
            return 0
        else:
            print("Operación finalizada sin descargas.")
            return 0
    except KeyboardInterrupt:
        print("\nCancelado por el usuario.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
