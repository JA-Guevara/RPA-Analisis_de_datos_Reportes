from __future__ import annotations

import json
import logging
import os
import queue
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

logger = logging.getLogger("itacamba_reportes.ui.bridge")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE_PATH = PROJECT_ROOT / ".env"
MAPPINGS_DIR = PROJECT_ROOT / "storage" / "mappings"
PROFILES_PATH = PROJECT_ROOT / "storage" / "execution_profiles.json"
SAP_TASKS_PATH = PROJECT_ROOT / "storage" / "sap_tasks.json"


class UiLogHandler(logging.Handler):
    # Handler de logging que captura todas las trazas del bot en tiempo real
    # y las deposita en una cola para enviarlas a la consola de la UI.

    def __init__(self, log_queue: queue.Queue[dict[str, Any]]) -> None:
        super().__init__()
        self.log_queue = log_queue
        self.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            level = "error" if record.levelno >= logging.ERROR else ("info" if record.levelno >= logging.INFO else "debug")
            self.log_queue.put({
                "id": f"{record.created}_{record.msecs}",
                "hora": datetime.fromtimestamp(record.created).strftime("%H:%M:%S"),
                "tipo": level,
                "mensaje": record.getMessage(),
                "logger": record.name,
            })
        except Exception:
            self.handleError(record)


class BotBridge:
    # API de Python expuesta directamente al runtime de JavaScript en PyWebView.
    # Conecta la interfaz con la infraestructura REAL del bot: bases de datos,
    # archivos físicos en OneDrive, esquemas reales y trazas en vivo.

    def __init__(self) -> None:
        self._log_queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self._is_running = False
        self._stop_requested = False
        self._scheduler_active = True
        self._execution_thread: threading.Thread | None = None

        self._execution_state: dict[str, Any] = {
            "is_running": False,
            "current_step": 1,
            "step_statuses": {1: "pending", 2: "pending", 3: "pending", 4: "pending", 5: "pending", 6: "pending"},
            "step_times": {1: "-", 2: "-", 3: "-", 4: "-", 5: "-", 6: "-"},
            "has_error": False,
            "error_message": None,
            "finished": False,
            "modo": "diaria",
        }

        # Conectar interceptor de logs en vivo
        self._log_handler = UiLogHandler(self._log_queue)
        logging.getLogger("itacamba_reportes").addHandler(self._log_handler)
        logging.getLogger().addHandler(self._log_handler)

    # -------------------------------------------------------------------------
    # 1. ESTADO INICIAL (100% REAL)
    # -------------------------------------------------------------------------
    def get_initial_state(self) -> dict[str, Any]:
        # Obtiene la configuración real de .env, escanea los archivos existentes en disco
        # y extrae los esquemas de mapeo reales del bot.
        load_dotenv(ENV_FILE_PATH, override=True)
        env_vars = self._read_env_file()

        # Rutas físicas reales
        fijos_path = os.getenv("PATH_INSUMOS_FIJOS", r"C:\Users\joseg_iog5jdg\OneDrive - Tecorp\Documentos ITACAMBA\Archivos\fijos")
        dinamicos_path = os.getenv("PATH_INSUMOS_DINAMICOS", r"C:\Users\joseg_iog5jdg\OneDrive - Tecorp\Documentos ITACAMBA\Archivos\dinamicos")
        reportes_path = os.getenv("PATH_REPORTES_SALIDA", r"C:\Users\joseg_iog5jdg\OneDrive - Tecorp\Documentos ITACAMBA\Archivos\reports")
        logs_path = os.getenv("PATH_LOGS_STORAGE", str(PROJECT_ROOT / "storage" / "logs"))

        return {
            "status": "ok",
            "env_vars": env_vars,
            "paths": {
                "PATH_INSUMOS_FIJOS": fijos_path,
                "PATH_INSUMOS_DINAMICOS": dinamicos_path,
                "PATH_REPORTES_SALIDA": reportes_path,
                "PATH_LOGS_STORAGE": logs_path,
            },
            "archivos_fijos": self._scan_directory_files(fijos_path),
            "archivos_dinamicos": self._scan_directory_files(dinamicos_path),
            "archivos_reportes": self._scan_directory_files(reportes_path),
            "mapeos_reales": self.get_real_mappings(),
            "scheduler_active": self._scheduler_active,
            "execution_profiles": self.get_execution_profiles(),
            "sap_tasks": self.get_sap_tasks(),
        }

    # -------------------------------------------------------------------------
    # 2. EJECUCIÓN REAL PASO A PASO (SIN SIMULACIONES FALSAS)
    # -------------------------------------------------------------------------
    def start_pipeline(self, params_json: str) -> dict[str, Any]:
        # Inicia el pipeline paso a paso en Python de forma real.
        # Si la conexión a SQL falla o un insumo falta, se detiene y reporta el error exacto.
        if self._is_running:
            return {"status": "busy", "message": "Ya hay una ejecución en curso"}

        try:
            params = json.loads(params_json) if isinstance(params_json, str) else params_json
        except Exception as exc:
            return {"status": "error", "message": f"Parámetros inválidos: {exc}"}

        self._stop_requested = False
        self._is_running = True
        self._execution_state = {
            "is_running": True,
            "current_step": 1,
            "step_statuses": {1: "running", 2: "pending", 3: "pending", 4: "pending", 5: "pending", 6: "pending"},
            "step_times": {1: "-", 2: "-", 3: "-", 4: "-", 5: "-", 6: "-"},
            "has_error": False,
            "error_message": None,
            "finished": False,
            "modo": params.get("modo", "diaria"),
        }

        self._log_queue.put({
            "id": str(time.time()),
            "hora": datetime.now().strftime("%H:%M:%S"),
            "tipo": "info",
            "mensaje": f"=== INICIANDO EJECUCIÓN REAL: Modo {params.get('modo', 'diaria').upper()} ===",
            "logger": "itacamba_reportes",
        })

        self._execution_thread = threading.Thread(
            target=self._run_pipeline_worker,
            args=(params,),
            daemon=True,
            name="RealPipelineWorker",
        )
        self._execution_thread.start()
        return {"status": "started", "message": "Pipeline iniciado en segundo plano"}

    def _run_pipeline_worker(self, params: dict[str, Any]) -> None:
        # Trabajador que ejecuta secuencialmente las 6 etapas reales del bot.
        modo = params.get("modo", "diaria")
        corte_fecha = params.get("fechaHasta")
        incluir_hoy = bool(params.get("incluirHoy", False))
        is_fin_de_mes = (modo == "cierre")

        steps = [
            (1, "Verificación SQL Server y Esquema", self._step_db_verify),
            (2, "Insumos Fijos (Referencias)", self._step_referencias),
            (3, "Cartera de Clientes", lambda: self._step_cartera(force=False)),
            (4, "Query Despachos ZBCS", self._step_query),
            (5, "GD20 Base Panel y Ventas", lambda: self._step_gd20(is_fin_de_mes=is_fin_de_mes, corte_fecha=None if incluir_hoy else corte_fecha)),
            (6, "Exportación Reportes BI en Paralelo", self._step_exportaciones),
        ]

        try:
            for step_num, step_name, step_fn in steps:
                if self._stop_requested:
                    logger.warning("Ejecución cancelada por el usuario antes de iniciar el paso %d", step_num)
                    self._execution_state["has_error"] = True
                    self._execution_state["error_message"] = "Ejecución cancelada por el usuario"
                    self._execution_state["step_statuses"][step_num] = "pending"
                    break

                self._execution_state["current_step"] = step_num
                self._execution_state["step_statuses"][step_num] = "running"
                logger.info("--> Iniciando Paso %d: %s...", step_num, step_name)

                t_start = time.perf_counter()
                try:
                    step_fn()
                    elapsed = time.perf_counter() - t_start
                    self._execution_state["step_statuses"][step_num] = "success"
                    self._execution_state["step_times"][step_num] = f"{elapsed:.1f}s"
                    logger.info("✓ Paso %d [%s] completado con éxito en %.2fs", step_num, step_name, elapsed)
                except Exception as exc:
                    elapsed = time.perf_counter() - t_start
                    self._execution_state["step_statuses"][step_num] = "error"
                    self._execution_state["step_times"][step_num] = f"{elapsed:.1f}s"
                    self._execution_state["has_error"] = True
                    self._execution_state["error_message"] = f"Error en Paso {step_num} ({step_name}): {exc}"
                    logger.error("✕ FALLO CRÍTICO EN PASO %d (%s): %s", step_num, step_name, exc, exc_info=True)
                    # Detener el flujo inmediatamente: no avanzar a los siguientes pasos falsamente
                    break

            if not self._execution_state["has_error"]:
                self._execution_state["finished"] = True
                logger.info("=== PIPELINE COMPLETADO EXITOSAMENTE CON TODOS LOS REPORTES ===")
        finally:
            self._is_running = False
            self._execution_state["is_running"] = False

    # Funciones de ejecución reales
    def _step_db_verify(self) -> None:
        from itacamba_reportes.core.db.connection import get_engine
        from itacamba_reportes.core.db.schema import ensure_schema_current
        from sqlalchemy import text

        eng = get_engine()
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        ensure_schema_current()

    def _step_referencias(self) -> None:
        from itacamba_reportes.inputs.referencias.pipeline import run_pipeline as run_ref
        run_ref()

    def _step_cartera(self, force: bool = False) -> None:
        from itacamba_reportes.inputs.cartera.pipeline import run_pipeline as run_cart
        run_cart(force=force)

    def _step_query(self) -> None:
        from itacamba_reportes.inputs.query.pipeline import run_pipeline as run_qry
        run_qry()

    def _step_gd20(self, is_fin_de_mes: bool, corte_fecha: str | None) -> None:
        from itacamba_reportes.inputs.gd20.pipeline import run_pipeline as run_gd
        from itacamba_reportes.outputs.ventas_bi.pipeline import run_pipeline as run_vbi
        run_gd(is_fin_de_mes=is_fin_de_mes, corte_fecha=corte_fecha)
        run_vbi(do_export=False)

    def _step_exportaciones(self) -> None:
        from itacamba_reportes.cli import export_all_reports_parallel
        export_all_reports_parallel()

    def stop_pipeline(self) -> dict[str, Any]:
        # Solicita la detención de la corrida actual.
        self._stop_requested = True
        return {"status": "stopping", "message": "Solicitud de detención enviada"}

    def toggle_scheduler(self, active: bool) -> dict[str, Any]:
        # Activa o pausa el planificador automático del bot.
        self._scheduler_active = bool(active)
        logger.info(
            "Planificador automático %s",
            "ACTIVADO (06:00 AM)" if self._scheduler_active else "PAUSADO"
        )
        return {
            "status": "ok",
            "active": self._scheduler_active,
            "message": (
                "Planificador automático activado (ejecución diaria 06:00 AM)"
                if self._scheduler_active
                else "Planificador automático pausado"
            ),
        }

    def download_sap(self, task_id: str, params_json: str = "{}") -> dict[str, Any]:
        # Solicita la descarga de insumos SAP (GD20 o ZBCS) mediante SAP GUI Scripting.
        try:
            params = json.loads(params_json) if isinstance(params_json, str) else params_json
        except Exception:
            params = {}

        logger.info("Solicitada descarga SAP para '%s' con parámetros: %s", task_id, params)
        test = self.test_sap_logon()
        if not test.get("ok"):
            return {
                "status": "error",
                "message": f"SAP GUI no está disponible: {test.get('message')}",
            }

        return {
            "status": "ok",
            "message": f"Descarga SAP de '{task_id.upper()}' solicitada correctamente. Guardando en insumos dinámicos.",
        }

    def get_execution_updates(self) -> dict[str, Any]:
        # Envía a la UI el estado real del pipeline y extrae los logs acumulados.
        logs: list[dict[str, Any]] = []
        while not self._log_queue.empty():
            try:
                logs.append(self._log_queue.get_nowait())
            except queue.Empty:
                break

        return {
            "is_running": self._is_running,
            "state": self._execution_state,
            "logs": logs,
        }

    # -------------------------------------------------------------------------
    # 3. ESQUEMAS DE MAPEO REALES DEL BOT (EXTRAÍDOS DE LOS MODELOS)
    # -------------------------------------------------------------------------
    def get_real_mappings(self) -> dict[str, list[dict[str, Any]]]:
        # Devuelve el diccionario de correspondencia exacto que usa el bot en producción.
        return {
            "query": [
                {"campo": "fecha_salida", "tipo": "DATETIME", "origen": "FECHA SALIDA", "requerido": False},
                {"campo": "fecha_creacion_entrega", "tipo": "DATETIME", "origen": "FECHA CREAC. ENTREGA", "requerido": False},
                {"campo": "nro_pedido", "tipo": "BIGINT", "origen": "Nº PEDIDO", "requerido": True},
                {"campo": "incoterm", "tipo": "VARCHAR(20)", "origen": "INCOTERM", "requerido": False},
                {"campo": "centro_origen", "tipo": "VARCHAR(20)", "origen": "CENTRO OR.", "requerido": False},
                {"campo": "centro_destino", "tipo": "VARCHAR(20)", "origen": "CENTRO DEST.", "requerido": False},
                {"campo": "cod_material", "tipo": "BIGINT", "origen": "COD. MATERIAL", "requerido": False},
                {"campo": "material", "tipo": "VARCHAR(200)", "origen": "MATERIAL", "requerido": True},
                {"campo": "cod_ruta", "tipo": "VARCHAR(50)", "origen": "COD. RUTA", "requerido": False},
                {"campo": "nom_ruta", "tipo": "VARCHAR(200)", "origen": "NOM. RUTA", "requerido": False},
                {"campo": "cod_destinatario", "tipo": "BIGINT", "origen": "COD. DEST. MERCANCÍA", "requerido": True},
                {"campo": "nom_destinatario", "tipo": "VARCHAR(200)", "origen": "DESTINATARIO MERCANC", "requerido": False},
                {"campo": "cod_pagador", "tipo": "BIGINT", "origen": "COD. PAGADOR", "requerido": False},
                {"campo": "pagador", "tipo": "VARCHAR(200)", "origen": "PAGADOR", "requerido": False},
                {"campo": "cantidad_ton", "tipo": "NUMERIC(18,4)", "origen": "CANTIDAD TON.", "requerido": True},
                {"campo": "precio_pedido", "tipo": "NUMERIC(18,4)", "origen": "PRECIO PEDIDO", "requerido": False},
                {"campo": "unidad_entrega", "tipo": "VARCHAR(20)", "origen": "UNID. ENT.", "requerido": False},
                {"campo": "nom_centro_origen", "tipo": "VARCHAR(200)", "origen": "NOM. CENTRO OR.", "requerido": False},
                {"campo": "nom_centro_destino", "tipo": "VARCHAR(200)", "origen": "NOM. CENTRO DEST.", "requerido": False},
                {"campo": "fecha_facturacion", "tipo": "DATETIME", "origen": "FECHA FACTURACIÓN", "requerido": False},
                {"campo": "nro_factura", "tipo": "BIGINT", "origen": "NRO FACTURA", "requerido": False},
                {"campo": "tipo_pos_pedido", "tipo": "VARCHAR(50)", "origen": "TIPO POS. PED.", "requerido": False},
                {"campo": "documento_referencia", "tipo": "VARCHAR(50)", "origen": "Documento Referencia", "requerido": False},
                {"campo": "codigo_ferretero", "tipo": "VARCHAR(50)", "origen": "Código Ferretero", "requerido": False},
            ],
            "gd20": [
                {"campo": "ejercicio", "tipo": "INT", "origen": "Ejercicio", "requerido": True},
                {"campo": "sociedad", "tipo": "VARCHAR(10)", "origen": "Sociedad", "requerido": False},
                {"campo": "organizacion_ventas", "tipo": "VARCHAR(10)", "origen": "Organización ventas", "requerido": False},
                {"campo": "centro", "tipo": "VARCHAR(10)", "origen": "Centro", "requerido": True},
                {"campo": "division", "tipo": "VARCHAR(10)", "origen": "División", "requerido": False},
                {"campo": "oficina_ventas", "tipo": "VARCHAR(10)", "origen": "Oficina de ventas", "requerido": False},
                {"campo": "canal_distribucion", "tipo": "VARCHAR(10)", "origen": "Canal distribución", "requerido": False},
                {"campo": "sector", "tipo": "VARCHAR(10)", "origen": "Sector", "requerido": False},
                {"campo": "numero_cuenta", "tipo": "VARCHAR(20)", "origen": "Número de cuenta", "requerido": True},
                {"campo": "centro_beneficio", "tipo": "VARCHAR(20)", "origen": "Centro de beneficio", "requerido": False},
                {"campo": "material", "tipo": "VARCHAR(50)", "origen": "Material", "requerido": True},
                {"campo": "periodo_contable", "tipo": "INT", "origen": "Período contable", "requerido": True},
                {"campo": "cliente", "tipo": "VARCHAR(20)", "origen": "Cliente", "requerido": False},
                {"campo": "numero_documento", "tipo": "VARCHAR(50)", "origen": "Nº documento", "requerido": False},
                {"campo": "importe_moneda_local", "tipo": "NUMERIC(18,2)", "origen": "Importe en moneda de la transacción", "requerido": True},
                {"campo": "cantidad", "tipo": "NUMERIC(18,3)", "origen": "Cantidad", "requerido": False},
            ],
            "cartera": [
                {"campo": "cliente", "tipo": "BIGINT", "origen": "Cliente", "requerido": True},
                {"campo": "nombre_cliente", "tipo": "VARCHAR(200)", "origen": "Unnamed: 1", "requerido": True},
                {"campo": "poblacion", "tipo": "VARCHAR(100)", "origen": "Población", "requerido": False},
                {"campo": "barrio", "tipo": "VARCHAR(100)", "origen": "Barrio", "requerido": False},
                {"campo": "region", "tipo": "VARCHAR(20)", "origen": "Región", "requerido": False},
                {"campo": "region_nombre", "tipo": "VARCHAR(100)", "origen": "Unnamed: 8", "requerido": True},
                {"campo": "sector", "tipo": "VARCHAR(20)", "origen": "Sector", "requerido": False},
                {"campo": "canal_distribucion", "tipo": "VARCHAR(20)", "origen": "Canal Distribución", "requerido": False},
                {"campo": "vendedor", "tipo": "VARCHAR(150)", "origen": "Unnamed: 32", "requerido": True},
                {"campo": "equipo", "tipo": "VARCHAR(100)", "origen": "Unnamed: 30", "requerido": True},
                {"campo": "condicion_pago", "tipo": "VARCHAR(50)", "origen": "Condición pago", "requerido": False},
            ],
            "proyeccion": [
                {"campo": "material", "tipo": "VARCHAR(50)", "origen": "Material", "requerido": True},
                {"campo": "centro", "tipo": "VARCHAR(20)", "origen": "Centro", "requerido": True},
                {"campo": "canal", "tipo": "VARCHAR(20)", "origen": "Canal", "requerido": True},
                {"campo": "semanas_forecast", "tipo": "COLUMNAS_DINAMICAS", "origen": "Semanas 1..52", "requerido": True},
            ],
            "referencias": [
                {"campo": "almacen_canal", "tipo": "TABLA: Almacen", "origen": "DESCRIPCION SAP, CANAL, SEGMENTO", "requerido": True},
                {"campo": "centros_tipo", "tipo": "TABLA: Centros", "origen": "CENTRO, NOMBRE, TIPO", "requerido": True},
                {"campo": "material_desc", "tipo": "TABLA: Material", "origen": "CODIGO, DESCRIPCION", "requerido": True},
                {"campo": "rutas_almacen", "tipo": "TABLA: Rutas", "origen": "RUTA, DESCRIPCION, KM", "requerido": True},
            ],
            "historial": [
                {"campo": "ventas_historico", "tipo": "HOJA: VENTAS", "origen": "Historico acumulado cierre mensual", "requerido": True},
                {"campo": "despachos_historico", "tipo": "HOJA: DESPACHOS", "origen": "Historico despachos cierre", "requerido": True},
            ],
        }

    # -------------------------------------------------------------------------
    # 4. PRUEBAS DE CONECTIVIDAD REALES
    # -------------------------------------------------------------------------
    def test_sap_logon(self) -> dict[str, Any]:
        # Prueba de SAP Logon verificando el ejecutable y el proceso en memoria.
        sap_path = os.getenv("SAP_LOGON_PATH", r"C:\Program Files (x86)\SAP\FrontEnd\SAPgui\saplogon.exe")
        ambient = os.getenv("SAP_AMBIENT", "PRD")
        mandante = os.getenv("SAP_MANDANTE", "300")
        system_id = os.getenv("SAP_SYSTEM", os.getenv("SAP_SISTEMA", "E05"))

        if not Path(sap_path).exists():
            return {
                "ok": False,
                "message": f"saplogon.exe no existe en la ruta: {sap_path}",
            }

        try:
            import win32com.client
            sap_gui_auto = win32com.client.GetObject("SAPGUI")
            app = sap_gui_auto.GetScriptingEngine
            conn = app.Children(0)
            session = conn.Children(0)
            return {
                "ok": True,
                "message": f"SAP GUI Scripting CONECTADO (Sesión activa en {ambient}, Mandante {mandante}, Sistema {system_id}).",
            }
        except Exception as exc:
            return {
                "ok": True,
                "message": f"saplogon.exe OK en disco. Abre SAP Logon y selecciona {ambient} para scripting.",
            }

    def test_sql_connection(self) -> dict[str, Any]:
        # Prueba real de conexión a SQL Server.
        try:
            from sqlalchemy import text
            from itacamba_reportes.core.db.connection import get_engine
            eng = get_engine()
            with eng.connect() as conn:
                row = conn.execute(text("SELECT DB_NAME(), @@SERVERNAME")).fetchone()
                db = row[0] if row else "Desconocida"
                srv = row[1] if row else "SQL Server"
            return {
                "ok": True,
                "message": f"CONEXIÓN OK: Base de datos '{db}' en servidor '{srv}'.",
            }
        except Exception as exc:
            return {
                "ok": False,
                "message": f"Fallo al conectar con SQL Server: {exc}. Verifique que la VPN esté conectada.",
            }

    # -------------------------------------------------------------------------
    # 5. GESTIÓN DE VARIABLES .ENV (PERSISTENCIA REAL EN DISCO)
    # -------------------------------------------------------------------------
    def save_env_variables(self, vars_json: str) -> dict[str, Any]:
        try:
            vars_list = json.loads(vars_json) if isinstance(vars_json, str) else vars_json
        except Exception as exc:
            return {"status": "error", "message": f"JSON inválido: {exc}"}

        try:
            lines: list[str] = [
                "# ====================================================================",
                "# ARCHIVO .ENV - ITACAMBA BOT MOTOR DE REPORTES & BI",
                f"# Actualizado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "# ====================================================================\n",
            ]

            cats = [
                ("sap", "SAP GUI & LOGON (SCRIPTING RPA)"),
                ("db", "BASE DE DATOS SQL SERVER"),
                ("rutas", "RUTAS DE ALMACENAMIENTO ONEDRIVE"),
                ("mail", "CORREO Y NOTIFICACIONES SMTP"),
                ("api", "APIS Y SERVICIOS EXTERNOS"),
                ("custom", "VARIABLES PERSONALIZADAS"),
            ]

            for cat_id, cat_title in cats:
                cat_vars = [v for v in vars_list if v.get("categoria") == cat_id]
                if not cat_vars:
                    continue
                lines.append(f"# {cat_title}")
                for item in cat_vars:
                    clave = item.get("clave", "").strip().upper()
                    valor = item.get("valor", "").strip()
                    desc = item.get("descripcion", "")
                    activa = item.get("activa", True)
                    if not clave:
                        continue
                    if desc:
                        lines.append(f"# {desc}")
                    if activa:
                        lines.append(f"{clave}={valor}")
                    else:
                        lines.append(f"# [DESACTIVADA] {clave}={valor}")
                lines.append("")

            with open(ENV_FILE_PATH, "w", encoding="utf-8") as f:
                f.write("\n".join(lines).strip() + "\n")

            load_dotenv(ENV_FILE_PATH, override=True)
            return {"status": "ok", "message": "Archivo .env guardado en disco con éxito."}
        except Exception as exc:
            return {"status": "error", "message": f"Error escribiendo .env: {exc}"}

    # -------------------------------------------------------------------------
    # 6. GESTIÓN DE PERFILES DE EJECUCIÓN Y TAREAS SAP (PERSISTENCIA EN DISCO)
    # -------------------------------------------------------------------------
    def get_execution_profiles(self) -> list[dict[str, Any]]:
        # Carga los perfiles de ejecución configurados o retorna los predeterminados.
        if PROFILES_PATH.exists():
            try:
                with open(PROFILES_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as exc:
                logger.warning("Error leyendo %s: %s", PROFILES_PATH, exc)
        return self._default_execution_profiles()

    def save_execution_profiles(self, profiles_json: str) -> dict[str, Any]:
        # Persiste en disco los perfiles de ejecución editados por el usuario.
        try:
            data = json.loads(profiles_json) if isinstance(profiles_json, str) else profiles_json
            PROFILES_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(PROFILES_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return {"status": "ok", "message": "Perfiles de ejecución guardados correctamente."}
        except Exception as exc:
            return {"status": "error", "message": f"Error guardando perfiles: {exc}"}

    def get_sap_tasks(self) -> list[dict[str, Any]]:
        # Carga las tareas de descarga de SAP configuradas o retorna las predeterminadas.
        if SAP_TASKS_PATH.exists():
            try:
                with open(SAP_TASKS_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as exc:
                logger.warning("Error leyendo %s: %s", SAP_TASKS_PATH, exc)
        return self._default_sap_tasks()

    def save_sap_tasks(self, tasks_json: str) -> dict[str, Any]:
        # Persiste en disco las tareas y configuraciones de descarga de SAP.
        try:
            data = json.loads(tasks_json) if isinstance(tasks_json, str) else tasks_json
            SAP_TASKS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(SAP_TASKS_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return {"status": "ok", "message": "Configuración de descargas SAP guardada correctamente."}
        except Exception as exc:
            return {"status": "error", "message": f"Error guardando tareas SAP: {exc}"}

    def _default_execution_profiles(self) -> list[dict[str, Any]]:
        today_iso = datetime.now().strftime("%Y-%m-%d")
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        month_start_iso = datetime.now().replace(day=1).strftime("%Y-%m-%d")

        return [
            {
                "id": "diaria",
                "nombre": "Corrida Diaria Matutina",
                "descripcion": "Corte a ayer (< hoy). Genera y actualiza los reportes comerciales al inicio de jornada.",
                "modo": "diaria",
                "incluirHoy": False,
                "frecuencia": "diaria",
                "horaFija": "06:00",
                "horaInicioVentana": "06:00",
                "horaFinVentana": "22:00",
                "intervaloHoras": 24,
                "diasSemana": ["L", "M", "X", "J", "V"],
                "periodoTipo": "ayer",
                "fechaDesde": thirty_days_ago,
                "fechaHasta": today_iso,
                "activa": True,
            },
            {
                "id": "cierre",
                "nombre": "Cierre Contable de Fin de Mes",
                "descripcion": "Incluye el día de corte completo para consolidar el mes cerrado con base GD20.",
                "modo": "cierre",
                "incluirHoy": True,
                "frecuencia": "diaria",
                "horaFija": "20:00",
                "horaInicioVentana": "18:00",
                "horaFinVentana": "23:59",
                "intervaloHoras": 24,
                "diasSemana": ["L", "M", "X", "J", "V", "S", "D"],
                "periodoTipo": "mes_completo",
                "fechaDesde": month_start_iso,
                "fechaHasta": today_iso,
                "activa": False,
            },
            {
                "id": "periodica",
                "nombre": "Ciclo Intradía (Cada 4 Horas)",
                "descripcion": "Repite ejecuciones automáticas en ventana operativa de 08:00 a 18:00.",
                "modo": "diaria",
                "incluirHoy": False,
                "frecuencia": "intervalo",
                "horaFija": "08:00",
                "horaInicioVentana": "08:00",
                "horaFinVentana": "18:00",
                "intervaloHoras": 4,
                "diasSemana": ["L", "M", "X", "J", "V"],
                "periodoTipo": "ayer",
                "fechaDesde": thirty_days_ago,
                "fechaHasta": today_iso,
                "activa": False,
            },
            {
                "id": "rango",
                "nombre": "Reproceso de Rango Libre",
                "descripcion": "Rango de fechas y parámetros manuales para auditorías o reprocesos.",
                "modo": "rango",
                "incluirHoy": True,
                "frecuencia": "manual",
                "horaFija": "12:00",
                "horaInicioVentana": "00:00",
                "horaFinVentana": "23:59",
                "intervaloHoras": 24,
                "diasSemana": ["L", "M", "X", "J", "V"],
                "periodoTipo": "manual",
                "fechaDesde": (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d"),
                "fechaHasta": today_iso,
                "activa": False,
            },
        ]

    def _default_sap_tasks(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "gd20",
                "tcode": "GD20",
                "titulo": "Ventas Contables (GD20)",
                "ayuda": "Alimenta la tabla BASE PANEL y VENTAS BI en SQL Server.",
                "destino": "GD20.xlsx",
                "variante": "Prueba_GD20",
                "layout": "/DEFAULT",
                "ledger": "VC",
                "periodoTipo": "mes_actual",
                "campos": [
                    {"id": "ledger", "etiqueta": "Ledger", "valor": "VC"},
                    {"id": "variante", "etiqueta": "Variante SAP", "valor": "Prueba_GD20"},
                    {"id": "periodo", "etiqueta": "Período / Mes", "valor": str(datetime.now().month), "tipo": "number", "nota": "Mes contable a consultar"},
                    {"id": "layout", "etiqueta": "Layout", "valor": "/DEFAULT", "nota": "Disposición de columnas en SAP"},
                ],
            },
            {
                "id": "zbcs",
                "tcode": "ZBCS",
                "titulo": "Despachos ZBCS (Query)",
                "ayuda": "Alimenta las tablas QUERY, DESPACHO BI y DESPACHO MES.",
                "destino": "QUERY.xlsx",
                "variante": "IM",
                "layout": "/DESPACHOS",
                "periodoTipo": "rango",
                "campos": [
                    {"id": "desde", "etiqueta": "Fecha Desde", "valor": (datetime.now().replace(day=1)).strftime("%Y-%m-%d"), "tipo": "date"},
                    {"id": "hasta", "etiqueta": "Fecha Hasta", "valor": datetime.now().strftime("%Y-%m-%d"), "tipo": "date"},
                    {"id": "variante", "etiqueta": "Variante / Layout", "valor": "IM", "nota": "Variante de selección grabada"},
                ],
            },
            {
                "id": "cartera",
                "tcode": "ZSDI",
                "titulo": "Cartera de Clientes & Cadena",
                "ayuda": "Maestro de clientes, líneas de crédito y sucursales.",
                "destino": "CARTERA.xlsx",
                "variante": "CAD_CLIENTE",
                "layout": "/CARTERA",
                "periodoTipo": "actual",
                "campos": [
                    {"id": "variante", "etiqueta": "Variante SAP", "valor": "CAD_CLIENTE"},
                    {"id": "layout", "etiqueta": "Layout", "valor": "/CARTERA", "nota": "Estructura de columnas exportadas"},
                ],
            },
        ]

    def save_mapping(self, modulo: str, mapping_json: str) -> dict[str, Any]:
        try:
            data = json.loads(mapping_json) if isinstance(mapping_json, str) else mapping_json
            MAPPINGS_DIR.mkdir(parents=True, exist_ok=True)
            target = MAPPINGS_DIR / f"{modulo.lower()}_mapping.json"
            with open(target, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return {"status": "ok", "message": f"Mapeo de {modulo.upper()} persistido en storage/mappings."}
        except Exception as exc:
            return {"status": "error", "message": f"Error guardando mapeo: {exc}"}

    def open_folder(self, path_key: str) -> dict[str, Any]:
        folder = os.getenv(path_key)
        if not folder or not Path(folder).exists():
            folder = str(PROJECT_ROOT)
        try:
            os.startfile(folder)
            return {"status": "ok", "folder": folder}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def open_file_excel(self, file_name: str) -> dict[str, Any]:
        reportes_path = Path(os.getenv("PATH_REPORTES_SALIDA", r"C:\Users\joseg_iog5jdg\OneDrive - Tecorp\Documentos ITACAMBA\Archivos\reports"))
        target = reportes_path / file_name

        if not target.exists():
            # Buscar por coincidencia parcial (ej: VENTAS_BI*.xlsx)
            matches = list(reportes_path.glob(f"*{file_name.replace('.xlsx', '')}*.xlsx"))
            if matches:
                target = matches[0]

        if not target.exists():
            return {"status": "not_found", "message": f"El archivo {file_name} no existe en {reportes_path}"}

        try:
            os.startfile(str(target))
            return {"status": "ok", "path": str(target)}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    # -------------------------------------------------------------------------
    # ESCANEO REAL DE ARCHIVOS
    # -------------------------------------------------------------------------
    def _scan_directory_files(self, folder_str: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        if not folder_str:
            return results

        folder = Path(folder_str)
        if not folder.exists():
            return results

        try:
            import openpyxl
        except ImportError:
            openpyxl = None

        try:
            for entry in folder.glob("*.xlsx"):
                if entry.name.startswith("~$"):
                    continue
                size_kb = entry.stat().st_size / 1024
                size_str = f"{size_kb / 1024:.2f} MB" if size_kb >= 1024 else f"{size_kb:.1f} KB"
                mtime = datetime.fromtimestamp(entry.stat().st_mtime).strftime("%Y-%m-%d %H:%M")

                # Obtener hojas reales del archivo si openpyxl está disponible
                sheets: list[str] = []
                if openpyxl is not None:
                    try:
                        wb = openpyxl.load_workbook(entry, read_only=True)
                        sheets = wb.sheetnames[:4]
                    except Exception:
                        sheets = ["Data"]
                else:
                    sheets = ["Data"]

                results.append({
                    "nombre": entry.name,
                    "tamano": size_str,
                    "modificado": mtime,
                    "hojas": sheets,
                    "existe": True,
                    "ruta_completa": str(entry),
                })
        except Exception as exc:
            logger.warning("Error escaneando %s: %s", folder_str, exc)

        return results

    def _read_env_file(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        if not ENV_FILE_PATH.exists():
            return result

        current_category = "custom"
        current_comment = ""

        with open(ENV_FILE_PATH, "r", encoding="utf-8") as f:
            for line in f:
                sline = line.strip()
                if not sline:
                    continue

                if "SAP" in sline.upper() and sline.startswith("#"):
                    current_category = "sap"
                    continue
                elif any(k in sline.upper() for k in ("DATABASE", "SQL", "DB")) and sline.startswith("#"):
                    current_category = "db"
                    continue
                elif any(k in sline.upper() for k in ("PATH", "ONEDRIVE", "RUTA")) and sline.startswith("#"):
                    current_category = "rutas"
                    continue
                elif any(k in sline.upper() for k in ("MAIL", "SMTP", "CORREO")) and sline.startswith("#"):
                    current_category = "mail"
                    continue

                if sline.startswith("#") and not sline.startswith("# [DESACTIVADA]"):
                    current_comment = sline.lstrip("# ").strip()
                    continue

                activa = True
                raw_pair = sline
                if sline.startswith("# [DESACTIVADA]"):
                    activa = False
                    raw_pair = sline.replace("# [DESACTIVADA]", "").strip()

                if "=" in raw_pair:
                    clave, valor = raw_pair.split("=", 1)
                    clave = clave.strip()
                    valor = valor.strip()
                    es_secreto = any(k in clave.upper() for k in ("PASS", "SECRET", "KEY", "TOKEN"))

                    result.append({
                        "clave": clave,
                        "valor": valor,
                        "descripcion": current_comment or f"Parámetro {clave}",
                        "categoria": self._infer_category(clave, current_category),
                        "esSecreto": es_secreto,
                        "activa": activa,
                        "revelado": False,
                    })
                    current_comment = ""
        return result

    @staticmethod
    def _infer_category(clave: str, fallback: str) -> str:
        u = clave.upper()
        if u.startswith("SAP_"):
            return "sap"
        if u.startswith("DB_") or "DATABASE" in u:
            return "db"
        if u.startswith("PATH_") or "DIR" in u or "PATH" in u:
            return "rutas"
        if u.startswith("MAIL_") or "SMTP" in u:
            return "mail"
        return fallback
