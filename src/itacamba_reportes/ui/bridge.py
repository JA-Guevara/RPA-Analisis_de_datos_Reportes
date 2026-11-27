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
CALENDAR_PATH = PROJECT_ROOT / "storage" / "execution_calendar.json"


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
        self._sap_download_running = False
        self._sap_download_seq = 0
        self._sap_download_result: dict[str, Any] | None = None
        self._stop_requested = False
        self._scheduler_active = False
        self._execution_thread: threading.Thread | None = None
        self._schedule_lock = threading.RLock()
        self._schedule_stop = threading.Event()
        self._schedule_thread: threading.Thread | None = None
        self._schedule_jobs: list[dict[str, Any]] = []
        self._schedule_status: dict[str, Any] = {
            "active": False,
            "profile_name": None,
            "next_run": None,
            "current_run": None,
            "pending": 0,
            "completed": 0,
            "total": 0,
            "skipped": 0,
            "message": "Cronograma detenido",
        }

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
    def _resolve_storage_paths(self) -> dict[str, str]:
        from itacamba_reportes.core.settings import EnvConfig

        EnvConfig.reload(ENV_FILE_PATH if ENV_FILE_PATH.exists() else None)
        return {
            "PATH_INSUMOS_FIJOS": str(EnvConfig.FIXED_INPUTS_PATH),
            "PATH_INSUMOS_DINAMICOS": str(EnvConfig.DYNAMIC_INPUTS_PATH),
            "PATH_REPORTES_SALIDA": str(EnvConfig.REPORTS_OUTPUT_PATH),
            "PATH_LOGS_STORAGE": str(EnvConfig.LOG_PATH),
        }

    def get_initial_state(self) -> dict[str, Any]:
        # Obtiene la configuración real de .env, escanea los archivos existentes en disco
        # y extrae los esquemas de mapeo reales del bot.
        load_dotenv(ENV_FILE_PATH, override=True)
        env_vars = self._read_env_file()
        paths = self._resolve_storage_paths()
        fijos_path = paths["PATH_INSUMOS_FIJOS"]
        dinamicos_path = paths["PATH_INSUMOS_DINAMICOS"]
        reportes_path = paths["PATH_REPORTES_SALIDA"]

        return {
            "status": "ok",
            "env_vars": env_vars,
            "paths": paths,
            "archivos_fijos": self._scan_directory_files(fijos_path),
            "archivos_dinamicos": self._scan_directory_files(dinamicos_path),
            "archivos_reportes": self._scan_directory_files(reportes_path),
            "mapeos_reales": self.get_real_mappings(),
            "scheduler_active": self._scheduler_active,
            "schedule_status": self.get_schedule_status(),
            "execution_profiles": self.get_execution_profiles(),
            "execution_calendar": self.get_execution_calendar(),
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
        fecha_desde = params.get("fechaDesde")
        incluir_hoy = bool(params.get("incluirHoy", False))
        descargar_sap = bool(params.get("descargarSap", False))
        is_fin_de_mes = (modo == "cierre")

        steps = [
            (1, "Verificación SQL Server y Esquema", lambda: self._step_db_and_optional_sap(
                descargar_sap=descargar_sap,
                fecha_desde=fecha_desde,
                corte_fecha=corte_fecha,
                profile_id=params.get("configuracionId"),
            )),
            (2, "Insumos Fijos (Referencias y Proyección)", self._step_referencias),
            (3, "Cartera de Clientes", lambda: self._step_cartera(force=False)),
            (4, "Despachos (Query, Despacho BI y Mes)", lambda: self._step_query(
                is_fin_de_mes=is_fin_de_mes,
                corte_fecha=corte_fecha,
                incluir_hasta=incluir_hoy,
            )),
            (5, "GD20 Base Panel y Ventas BI", lambda: self._step_gd20(
                is_fin_de_mes=is_fin_de_mes,
                corte_fecha=corte_fecha,
                fecha_desde=fecha_desde,
                incluir_hasta=incluir_hoy,
            )),
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
    def _resolve_sap_config_dates(
        self,
        fecha_desde: str | None = None,
        corte_fecha: str | None = None,
        profile_id: str | None = None,
    ) -> tuple[str, str, str, str, str]:
        p_id = str(profile_id).split(":")[0] if profile_id else None
        if (not fecha_desde or not corte_fecha) and PROFILES_PATH.exists():
            profiles = self.get_execution_profiles()
            target_prof = next((p for p in profiles if p_id and str(p.get("id")) == p_id), None)
            if target_prof is None:
                target_prof = next((p for p in profiles if p.get("activa")), profiles[0] if profiles else None)
            if target_prof:
                fecha_desde = fecha_desde or target_prof.get("fechaDesde")
                corte_fecha = corte_fecha or target_prof.get("fechaHasta")
                if not fecha_desde and target_prof.get("mesEjecucion"):
                    fecha_desde = f"{target_prof['mesEjecucion']}-01"

        dt_hasta = datetime.now()
        if corte_fecha:
            try:
                dt_hasta = datetime.fromisoformat(str(corte_fecha))
            except ValueError:
                pass

        dt_desde = dt_hasta
        if fecha_desde:
            try:
                dt_desde = datetime.fromisoformat(str(fecha_desde))
            except ValueError:
                pass

        p_low = str(dt_desde.month)
        p_high = str(dt_hasta.month) if dt_hasta >= dt_desde else p_low
        y_low = str(dt_desde.year)
        y_high = str(dt_hasta.year) if dt_hasta >= dt_desde else y_low
        date_to_sap = dt_hasta.strftime("%d.%m.%Y")
        return p_low, p_high, y_low, y_high, date_to_sap

    def _resolve_sap_period_from_config(
        self,
        fecha_desde: str | None = None,
        corte_fecha: str | None = None,
        profile_id: str | None = None,
    ) -> tuple[str, str, str]:
        p_low, p_high, _y_low, _y_high, date_to_sap = self._resolve_sap_config_dates(
            fecha_desde=fecha_desde,
            corte_fecha=corte_fecha,
            profile_id=profile_id,
        )
        return p_low, p_high, date_to_sap

    def _step_db_verify(self) -> None:
        from itacamba_reportes.core.db.connection import get_engine
        from itacamba_reportes.core.db.schema import ensure_schema_current
        from sqlalchemy import text

        eng = get_engine()
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        ensure_schema_current()

    def _step_db_and_optional_sap(
        self,
        descargar_sap: bool = False,
        fecha_desde: str | None = None,
        corte_fecha: str | None = None,
        profile_id: str | None = None,
    ) -> None:
        self._step_db_verify()
        if descargar_sap:
            from itacamba_reportes.sap.actions import execute_download_all_sap

            p_low, p_high, y_low, y_high, date_to_query = self._resolve_sap_config_dates(
                fecha_desde=fecha_desde,
                corte_fecha=corte_fecha,
                profile_id=profile_id,
            )
            logger.info(
                "Ejecutando descarga previa automatizada en SAP (GD20 Ejercicio %s..%s, Período %s..%s + Query hasta %s)...",
                y_low,
                y_high,
                p_low,
                p_high,
                date_to_query,
            )
            dinamicos_dir = Path(self._resolve_storage_paths()["PATH_INSUMOS_DINAMICOS"])
            dinamicos_dir.mkdir(parents=True, exist_ok=True)
            execute_download_all_sap(
                target_dir=dinamicos_dir,
                period_gd20=p_low,
                period_high_gd20=p_high,
                year_gd20=y_low,
                year_high_gd20=y_high,
                date_to_query=date_to_query,
                close_at_end=True,
            )

    def _step_referencias(self) -> None:
        from itacamba_reportes.inputs.referencias.pipeline import run_pipeline as run_ref
        from itacamba_reportes.inputs.proyeccion.pipeline import run_pipeline as run_proy
        run_ref()
        run_proy()

    def _step_cartera(self, force: bool = False) -> None:
        from itacamba_reportes.inputs.cartera.pipeline import run_pipeline as run_cart
        run_cart(force=force)

    def _step_query(
        self,
        is_fin_de_mes: bool = False,
        corte_fecha: str | None = None,
        incluir_hasta: bool = False,
    ) -> None:
        from itacamba_reportes.inputs.query.pipeline import run_pipeline as run_qry
        from itacamba_reportes.outputs.despacho_bi.pipeline import run_pipeline as run_dbi
        from itacamba_reportes.outputs.despacho_mes.pipeline import run_pipeline as run_dmes
        run_qry(
            corte_fecha=corte_fecha,
            is_fin_de_mes=is_fin_de_mes,
            incluir_hasta=incluir_hasta,
        )
        run_dbi(do_export=False)
        run_dmes(
            corte_fecha=corte_fecha,
            is_fin_de_mes=is_fin_de_mes,
            incluir_hasta=incluir_hasta,
            do_export=False,
        )

    def _step_gd20(
        self,
        is_fin_de_mes: bool,
        corte_fecha: str | None,
        fecha_desde: str | None = None,
        incluir_hasta: bool = False,
    ) -> None:
        from itacamba_reportes.inputs.gd20.pipeline import run_pipeline as run_gd
        from itacamba_reportes.outputs.ventas_bi.pipeline import run_pipeline as run_vbi
        run_gd(
            is_fin_de_mes=is_fin_de_mes,
            corte_fecha=corte_fecha,
            fecha_desde=fecha_desde,
            incluir_hasta=incluir_hasta,
        )
        run_vbi(do_export=False)

    def _step_exportaciones(self) -> None:
        from itacamba_reportes.cli import export_all_reports_parallel
        export_all_reports_parallel()

    def stop_pipeline(self) -> dict[str, Any]:
        # Solicita la detención de la corrida actual.
        self._stop_requested = True
        return {"status": "stopping", "message": "Solicitud de detención enviada"}

    def toggle_scheduler(self, active: bool) -> dict[str, Any]:
        # Compatibilidad con el control anterior: ahora inicia o detiene el cronograma real.
        return self.start_schedule(self.get_execution_calendar()) if active else self.stop_schedule()

    def get_schedule_status(self) -> dict[str, Any]:
        with self._schedule_lock:
            status = dict(self._schedule_status)
            status["active"] = bool(self._scheduler_active)
            status["running"] = bool(self._is_running)
            return status

    def start_schedule(self, calendar_json: str | dict[str, Any] | None = None) -> dict[str, Any]:
        # Activa un cronograma de fechas futuras ya configuradas en el calendario.
        with self._schedule_lock:
            if self._scheduler_active:
                return {"status": "ok", "active": True, **self.get_schedule_status(), "message": "El cronograma ya está en marcha."}
            if self._schedule_thread is not None and self._schedule_thread.is_alive():
                return {"status": "error", "message": "El cronograma anterior todavía está terminando. Intenta iniciarlo de nuevo en unos segundos."}

        try:
            if calendar_json is None:
                calendar = self.get_execution_calendar()
            elif isinstance(calendar_json, str):
                calendar = json.loads(calendar_json)
            else:
                calendar = calendar_json
        except Exception as exc:
            return {"status": "error", "message": f"No se pudo leer el calendario: {exc}"}

        if not isinstance(calendar, dict) or not isinstance(calendar.get("asignaciones"), dict):
            calendars = calendar.get("perfiles") if isinstance(calendar, dict) else None
            if isinstance(calendars, dict):
                calendar = next(
                    (item for item in calendars.values() if isinstance(item, dict) and isinstance(item.get("asignaciones"), dict) and item["asignaciones"]),
                    {},
                )
        if not isinstance(calendar, dict) or not isinstance(calendar.get("asignaciones"), dict):
            return {"status": "error", "message": "Guarda primero un calendario válido antes de iniciarlo."}

        default_time = calendar.get("horaEjecucionDefault") or "06:00"
        now = datetime.now()
        jobs: list[dict[str, Any]] = []
        skipped = 0
        for date_key, raw_assignment in calendar["asignaciones"].items():
            assignment = {"tipo": raw_assignment} if isinstance(raw_assignment, str) else raw_assignment
            if not isinstance(assignment, dict):
                continue
            tipo = assignment.get("tipo")
            if tipo not in {"mes_actual", "mes_anterior", "cierre", "rango"}:
                continue

            scheduled_time = assignment.get("hora") or default_time
            try:
                run_at = datetime.strptime(f"{date_key} {scheduled_time}", "%Y-%m-%d %H:%M")
            except (TypeError, ValueError):
                return {"status": "error", "message": f"Revisa la fecha o la hora configurada para {date_key}."}
            if run_at <= now:
                skipped += 1
                continue

            if tipo == "rango":
                fecha_desde = assignment.get("fechaDesde") or calendar.get("fechaDesdeManual")
                fecha_hasta = assignment.get("fechaHasta") or calendar.get("fechaHastaManual") or date_key
            else:
                year, month, _day = (int(part) for part in date_key.split("-"))
                if tipo == "mes_anterior":
                    previous_month = datetime(year, month - 1, 1) if month > 1 else datetime(year - 1, 12, 1)
                    fecha_desde = previous_month.strftime("%Y-%m-01")
                else:
                    fecha_desde = f"{year:04d}-{month:02d}-01"
                fecha_hasta = date_key

            try:
                inicio_periodo = datetime.strptime(fecha_desde, "%Y-%m-%d").date()
                fin_periodo = datetime.strptime(fecha_hasta, "%Y-%m-%d").date()
            except (TypeError, ValueError):
                return {"status": "error", "message": f"El periodo de {date_key} tiene fechas inválidas."}
            if inicio_periodo > fin_periodo:
                return {"status": "error", "message": f"El periodo de {date_key} tiene fechas inválidas."}

            jobs.append({
                "fecha": date_key,
                "hora": scheduled_time,
                "run_at": run_at,
                "tipo": tipo,
                "params": {
                    "modo": "rango" if tipo == "rango" else ("diaria" if tipo == "mes_actual" else "cierre"),
                    "fechaDesde": fecha_desde,
                    "fechaHasta": fecha_hasta,
                    "incluirHoy": bool(assignment.get("incluirDia", tipo != "mes_actual")),
                    "configuracionId": f"calendario:{date_key}",
                },
            })

        return self._activate_schedule_jobs(jobs, skipped, "Calendario mensual")

    def start_profile_schedule(
        self,
        profile_json: str | dict[str, Any],
        calendar_json: str | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        # Activa las fechas del calendario del perfil con su frecuencia y periodo.
        try:
            profile = json.loads(profile_json) if isinstance(profile_json, str) else profile_json
        except Exception as exc:
            return {"status": "error", "message": f"No se pudo leer el perfil: {exc}"}
        if not isinstance(profile, dict):
            return {"status": "error", "message": "Selecciona un perfil de ejecución válido."}

        frequency = profile.get("frecuencia", "diaria")
        if frequency == "manual":
            return {"status": "error", "message": "Este perfil es solo manual; usa “Ejecutar ahora”."}
        if frequency not in {"diaria", "intervalo"}:
            return {"status": "error", "message": "El perfil tiene una frecuencia no reconocida."}

        if calendar_json is None:
            calendar = self.get_execution_calendar()
            calendars = calendar.get("perfiles") if isinstance(calendar, dict) else None
            if isinstance(calendars, dict):
                calendar = calendars.get(str(profile.get("id") or ""), {})
        else:
            try:
                calendar = json.loads(calendar_json) if isinstance(calendar_json, str) else calendar_json
            except Exception as exc:
                return {"status": "error", "message": f"No se pudo leer el calendario: {exc}"}
            if isinstance(calendar, dict) and isinstance(calendar.get("perfiles"), dict):
                calendar = calendar["perfiles"].get(str(profile.get("id") or ""), {})

        if not isinstance(calendar, dict) or not isinstance(calendar.get("asignaciones"), dict):
            return {"status": "error", "message": "Guarda primero el perfil con sus días y periodos desde Programador."}
        selected_month = str(profile.get("mesEjecucion") or calendar.get("mes") or "")
        try:
            datetime.strptime(selected_month, "%Y-%m")
        except (TypeError, ValueError):
            return {"status": "error", "message": "El perfil no tiene un mes válido seleccionado."}
        month_prefix = f"{selected_month}-"
        assignments = {
            date_key: assignment
            for date_key, assignment in calendar["asignaciones"].items()
            if isinstance(date_key, str) and date_key.startswith(month_prefix)
        }
        if not assignments:
            return {
                "status": "error",
                "message": f"Este perfil no tiene días configurados para {selected_month}. Revisa el mes elegido en Programador.",
            }

        use_type_schedules = bool(profile.get("usarHorarioPorTipo"))
        type_schedules = profile.get("horariosPorTipo") if use_type_schedules else {}
        if not isinstance(type_schedules, dict):
            return {"status": "error", "message": "Revisa los horarios definidos por tipo de periodo."}

        if frequency == "intervalo" and not use_type_schedules:
            try:
                datetime.strptime(profile.get("horaInicioVentana") or "08:00", "%H:%M")
                datetime.strptime(profile.get("horaFinVentana") or "18:00", "%H:%M")
                global_interval = int(profile.get("intervaloHoras") or 4)
            except (TypeError, ValueError):
                return {"status": "error", "message": "Revisa la hora inicial, final y el intervalo general."}
            if not 1 <= global_interval <= 24:
                return {"status": "error", "message": "El intervalo general debe estar entre 1 y 24 horas."}

        now = datetime.now()
        jobs: list[dict[str, Any]] = []
        skipped = 0
        profile_name = str(profile.get("nombre") or "Perfil")
        profile_id = str(profile.get("id") or "perfil")
        for date_key, raw_assignment in sorted(assignments.items()):
            assignment = {"tipo": raw_assignment} if isinstance(raw_assignment, str) else raw_assignment
            if not isinstance(assignment, dict):
                continue
            tipo = assignment.get("tipo")
            if tipo not in {"mes_actual", "mes_anterior", "cierre", "rango"}:
                continue
            try:
                run_date = datetime.strptime(date_key, "%Y-%m-%d").date()
            except (TypeError, ValueError):
                return {"status": "error", "message": f"La fecha {date_key} del calendario no es válida."}

            if tipo == "rango":
                fecha_desde = assignment.get("fechaDesde") or calendar.get("fechaDesdeManual") or profile.get("fechaDesde")
                fecha_hasta = assignment.get("fechaHasta") or calendar.get("fechaHastaManual") or profile.get("fechaHasta")
            else:
                month_start = run_date.replace(day=1)
                if tipo == "mes_anterior":
                    fecha_desde = (month_start - timedelta(days=1)).replace(day=1).isoformat()
                else:
                    fecha_desde = month_start.isoformat()
                fecha_hasta = run_date.isoformat()

            try:
                start_date = datetime.strptime(fecha_desde, "%Y-%m-%d").date()
                end_date = datetime.strptime(fecha_hasta, "%Y-%m-%d").date()
            except (TypeError, ValueError):
                return {"status": "error", "message": f"Completa las fechas del periodo para {date_key}."}
            if start_date > end_date:
                return {"status": "error", "message": f"El periodo de {date_key} termina antes de comenzar."}
            include_day = bool(assignment.get("incluirDia", tipo in {"mes_anterior", "cierre"}))
            last_included_date = end_date if include_day else end_date - timedelta(days=1)
            if start_date > last_included_date:
                return {
                    "status": "error",
                    "message": f"El {date_key} no deja fechas completas para procesar. Incluye el día de ejecución o elige otro periodo.",
                }

            rule = type_schedules.get(tipo, {}) if use_type_schedules else {}
            if not isinstance(rule, dict):
                return {"status": "error", "message": f"Revisa el horario de “{tipo}”."}
            day_frequency = rule.get("frecuencia") or frequency
            if day_frequency not in {"diaria", "intervalo"}:
                return {"status": "error", "message": f"El tipo “{tipo}” debe ejecutarse una vez al día o por intervalo."}
            hora_personalizada = assignment.get("horaPersonalizada", bool(assignment.get("hora")))
            if day_frequency == "diaria":
                default_time = rule.get("horaFija") if use_type_schedules else profile.get("horaFija")
                scheduled_time = assignment.get("hora") if hora_personalizada else None
                run_times = [scheduled_time or default_time or "06:00"]
            else:
                try:
                    start_value = rule.get("horaInicioVentana") if use_type_schedules else profile.get("horaInicioVentana")
                    end_value = rule.get("horaFinVentana") if use_type_schedules else profile.get("horaFinVentana")
                    interval_value = rule.get("intervaloHoras") if use_type_schedules else profile.get("intervaloHoras")
                    interval_hours = int(interval_value or 4)
                    start_time = datetime.strptime(
                        (assignment.get("hora") if hora_personalizada else None) or start_value or "08:00", "%H:%M"
                    ).time()
                    end_time = datetime.strptime(end_value or "18:00", "%H:%M").time()
                except (TypeError, ValueError):
                    return {"status": "error", "message": f"Revisa el intervalo y las horas definidas para {date_key}."}
                if not 1 <= interval_hours <= 24:
                    return {"status": "error", "message": f"El intervalo de {date_key} debe estar entre 1 y 24 horas."}
                if start_time > end_time:
                    return {"status": "error", "message": f"La hora inicial del {date_key} debe ser anterior o igual a la final."}
                start_minutes = start_time.hour * 60 + start_time.minute
                end_minutes = end_time.hour * 60 + end_time.minute
                run_times = [
                    f"{minute // 60:02d}:{minute % 60:02d}"
                    for minute in range(start_minutes, end_minutes + 1, interval_hours * 60)
                ]

            for scheduled_time in run_times:
                try:
                    run_at = datetime.strptime(f"{date_key} {scheduled_time}", "%Y-%m-%d %H:%M")
                except (TypeError, ValueError):
                    return {"status": "error", "message": f"Revisa la fecha o la hora configurada para {date_key}."}
                if run_at <= now:
                    skipped += 1
                    continue

                jobs.append({
                    "fecha": date_key,
                    "hora": scheduled_time,
                    "run_at": run_at,
                    "tipo": day_frequency,
                    "params": {
                        "modo": "rango" if tipo == "rango" else ("diaria" if tipo == "mes_actual" else "cierre"),
                        "fechaDesde": start_date.isoformat(),
                        "fechaHasta": end_date.isoformat(),
                        "incluirHoy": include_day,
                        "descargarSap": bool(profile.get("descargarSap", False)),
                        "configuracionId": f"{profile_id}:{date_key}",
                    },
                })

        if not jobs:
            return {
                "status": "error",
                "message": "No quedan ejecuciones futuras. Revisa las fechas asignadas y sus horarios.",
                "skipped": skipped,
            }
        return self._activate_schedule_jobs(jobs, skipped, profile_name)

    def _activate_schedule_jobs(self, jobs: list[dict[str, Any]], skipped: int, schedule_name: str) -> dict[str, Any]:
        jobs.sort(key=lambda job: job["run_at"])
        if not jobs:
            return {
                "status": "error",
                "message": "No quedan ejecuciones futuras para este perfil. Revisa el mes, los días y las horas configurados.",
                "skipped": skipped,
            }

        now = datetime.now()
        with self._schedule_lock:
            if self._scheduler_active:
                return {"status": "ok", "active": True, **self.get_schedule_status(), "message": "Ya hay una programación en marcha."}
            if self._schedule_thread is not None and self._schedule_thread.is_alive():
                return {"status": "error", "message": "La programación anterior todavía está terminando. Intenta iniciarla de nuevo en unos segundos."}
            self._schedule_stop.clear()
            self._schedule_jobs = jobs
            self._scheduler_active = True
            self._schedule_status = {
                "active": True,
                "profile_name": schedule_name,
                "started_at": now.strftime("%Y-%m-%d %H:%M:%S"),
                "next_run": jobs[0]["run_at"].strftime("%Y-%m-%d %H:%M"),
                "current_run": None,
                "pending": len(jobs),
                "completed": 0,
                "total": len(jobs),
                "skipped": skipped,
                "message": "Programación en marcha",
            }
            self._schedule_thread = threading.Thread(
                target=self._run_schedule_worker,
                daemon=True,
                name="ExecutionScheduleWorker",
            )
            self._schedule_thread.start()

        next_run = jobs[0]["run_at"].strftime("%Y-%m-%d %H:%M")
        logger.info(
            "Programación '%s' iniciada: %d ejecución(es) futura(s); %d horario(s) pasado(s) omitido(s). Próxima: %s",
            schedule_name,
            len(jobs),
            skipped,
            next_run,
        )
        return {
            "status": "started",
            "active": True,
            "profile_name": schedule_name,
            "next_run": next_run,
            "pending": len(jobs),
            "completed": 0,
            "total": len(jobs),
            "skipped": skipped,
            "message": (
                f"Programación de “{schedule_name}” iniciada. Las corridas se ejecutarán en orden."
                + (f" Se omitieron {skipped} horario(s) pasado(s)." if skipped else "")
            ),
        }

    def _run_schedule_worker(self) -> None:
        jobs = list(self._schedule_jobs)
        pending: list[dict[str, Any]] = []
        next_index = 0
        current_job: dict[str, Any] | None = None
        stopped = False

        try:
            while not self._schedule_stop.is_set():
                now = datetime.now()
                while next_index < len(jobs) and jobs[next_index]["run_at"] <= now:
                    pending.append(jobs[next_index])
                    next_index += 1

                if current_job is not None and not self._is_running:
                    logger.info(
                        "Ejecución programada del %s (%s) finalizada.",
                        current_job["fecha"],
                        current_job["hora"],
                    )
                    current_job = None

                if current_job is None and pending and not self._is_running:
                    candidate = pending.pop(0)
                    result = self.start_pipeline(candidate["params"])
                    if result.get("status") == "started":
                        current_job = candidate
                        logger.info(
                            "Iniciando ejecución programada: %s a las %s (%s).",
                            candidate["fecha"],
                            candidate["hora"],
                            candidate["tipo"],
                        )
                    elif result.get("status") == "busy":
                        pending.insert(0, candidate)
                    else:
                        logger.error(
                            "No se pudo iniciar la ejecución programada del %s: %s",
                            candidate["fecha"],
                            result.get("message", "error desconocido"),
                        )

                next_job = pending[0] if pending else (jobs[next_index] if next_index < len(jobs) else None)
                remaining = len(pending) + (len(jobs) - next_index) + (1 if current_job is not None else 0)
                with self._schedule_lock:
                    self._schedule_status.update({
                        "active": True,
                        "next_run": next_job["run_at"].strftime("%Y-%m-%d %H:%M") if next_job else None,
                        "current_run": (
                            f'{current_job["fecha"]} {current_job["hora"]}'
                            if current_job is not None
                            else None
                        ),
                        "pending": remaining,
                        "completed": len(jobs) - remaining,
                        "total": len(jobs),
                        "message": "Cronograma en marcha",
                    })

                if current_job is None and not pending and next_index >= len(jobs) and not self._is_running:
                    break
                self._schedule_stop.wait(0.5)
        finally:
            stopped = self._schedule_stop.is_set()
            remaining = len(pending) + (len(jobs) - next_index) + (1 if current_job is not None and self._is_running else 0)
            with self._schedule_lock:
                self._scheduler_active = False
                self._schedule_status.update({
                    "active": False,
                    "next_run": None,
                    "current_run": (
                        f'{current_job["fecha"]} {current_job["hora"]}'
                        if current_job is not None and self._is_running
                        else None
                    ),
                    "pending": remaining,
                    "completed": len(jobs) - remaining,
                    "total": len(jobs),
                    "message": (
                        "Cronograma detenido; la corrida activa terminará."
                        if stopped and self._is_running
                        else ("Cronograma detenido" if stopped else "Cronograma completado")
                    ),
                })
            logger.info(self._schedule_status["message"])

    def stop_schedule(self) -> dict[str, Any]:
        with self._schedule_lock:
            if not self._scheduler_active:
                return {"status": "ok", "active": False, **self.get_schedule_status(), "message": "El cronograma ya está detenido."}
            self._scheduler_active = False
            self._schedule_status["active"] = False
            self._schedule_status["message"] = "Deteniendo cronograma…"
            self._schedule_stop.set()
        logger.info("Solicitud de detención del cronograma recibida.")
        return {
            "status": "ok",
            "active": False,
            "message": "Se detuvieron las próximas ejecuciones. Si hay una corrida en curso, terminará normalmente.",
        }

    def download_sap(self, task_id: str, params_json: str = "{}") -> dict[str, Any]:
        try:
            params = json.loads(params_json) if isinstance(params_json, str) else params_json
        except Exception:
            params = {}

        logger.info("Solicitada descarga SAP para '%s' con parámetros: %s", task_id, params)
        if task_id.lower().strip() == "cartera":
            return {
                "status": "error",
                "message": "CARTERA.xlsx no cuenta con script SAP GUI automatizado; llega por correo automático a dinamicos/.",
            }

        if self._sap_download_running:
            return {
                "status": "busy",
                "message": "Ya hay una descarga SAP en ejecución. Espera a que finalice.",
            }

        test = self.test_sap_logon()
        if not test.get("ok"):
            return {
                "status": "error",
                "message": f"SAP GUI no está disponible: {test.get('message')}",
            }

        key = task_id.lower().strip()
        p_low_cfg, p_high_cfg, y_low_cfg, y_high_cfg, date_to_cfg = self._resolve_sap_config_dates(
            fecha_desde=params.get("fechaDesdeConfig") or params.get("fechaDesde") or None,
            corte_fecha=params.get("fechaHastaConfig") or params.get("fechaHasta") or None,
            profile_id=params.get("profileId") or None,
        )
        manual_period = (params.get("periodo") or "").strip() or None
        manual_year = (params.get("ejercicio") or "").strip() or None
        manual_desde = (params.get("desde") or "").strip() or None
        manual_hasta = (params.get("hasta") or "").strip() or None
        close_at_end = bool(params.get("cerrarAlFinal", True))

        p_eff_low = manual_period or p_low_cfg
        p_eff_high = p_eff_low if manual_period else p_high_cfg
        y_eff_low = manual_year or y_low_cfg
        q_to_preview = manual_hasta or date_to_cfg

        self._sap_download_running = True

        def _worker():
            from itacamba_reportes.sap.config import CONFIG_CARTERA, CONFIG_GD20, CONFIG_QUERY, SapDownloadConfig
            from itacamba_reportes.sap.session import SapSessionManager
            from itacamba_reportes.sap.actions import execute_download_all_sap, execute_download_report, finalize_sap_session

            mgr = SapSessionManager()
            connected = False
            try:
                target_dir = Path(self._resolve_storage_paths()["PATH_INSUMOS_DINAMICOS"])
                target_dir.mkdir(parents=True, exist_ok=True)

                mgr.ensure_connected_and_ready(auto_launch=True)
                connected = True

                if key in ("all", "batch", "lote", "todos"):
                    out_files = execute_download_all_sap(
                        session_manager=mgr,
                        target_dir=target_dir,
                        period_gd20=p_eff_low,
                        period_high_gd20=None if manual_period else p_high_cfg,
                        year_gd20=y_eff_low,
                        year_high_gd20=None if manual_year else y_high_cfg,
                        date_from_query=manual_desde,
                        date_to_query=q_to_preview,
                        close_at_end=close_at_end,
                    )
                    connected = False
                    logger.info("Descarga en lote SAP finalizada exitosamente: %s", out_files)
                    names = ", ".join(p.name for p in out_files.values())
                    self._sap_download_seq += 1
                    self._sap_download_result = {
                        "id": self._sap_download_seq,
                        "task_id": task_id,
                        "status": "ok",
                        "message": f"Descarga conjunta SAP completada: {names}",
                    }
                    return

                if key == "gd20":
                    cfg = CONFIG_GD20.to_download_config(
                        target_dir=target_dir,
                        period_override=p_eff_low,
                        period_high_override=None if manual_period else p_high_cfg,
                        year_override=y_eff_low,
                        year_high_override=None if manual_year else y_high_cfg,
                    )
                elif key in ("zbcs", "query"):
                    cfg = CONFIG_QUERY.to_download_config(
                        target_dir=target_dir,
                        date_from_override=manual_desde,
                        date_to_override=q_to_preview,
                    )
                elif key == "cartera":
                    cfg = CONFIG_CARTERA.to_download_config(target_dir=target_dir)
                else:
                    cfg = SapDownloadConfig(transaction=params.get("tcode", task_id), target_dir=target_dir)

                if p := params.get("periodo"):
                    p_str = str(p).strip()
                    if p_str.isdigit() and int(p_str) > 0:
                        cfg.period_low = p_str
                        cfg.period_high = p_str
                if ej := params.get("ejercicio"):
                    ej_str = str(ej).strip()
                    if ej_str.isdigit() and int(ej_str) > 0:
                        cfg.year_low = ej_str
                        cfg.year_high = None
                if v := params.get("variante"):
                    if str(v).strip():
                        cfg.variant = str(v).strip()
                if l := params.get("ledger"):
                    if str(l).strip() and str(l).strip().upper() != "N/A":
                        cfg.ledger = str(l).strip()
                if soc := params.get("sociedad"):
                    if str(soc).strip():
                        cfg.sociedad = str(soc).strip()
                if lr := params.get("layout_row"):
                    try:
                        cfg.layout_row = int(lr)
                    except Exception:
                        pass
                if ln := (params.get("layout_name") or params.get("layout")):
                    ln_clean = str(ln).strip()
                    if ln_clean and not (key in ("zbcs", "query") and ln_clean == (cfg.variant or "")):
                        cfg.layout_name = ln_clean
                if dest := params.get("destino"):
                    if str(dest).strip():
                        cfg.export_filename = str(dest).strip()

                out_file = execute_download_report(mgr, cfg)
                logger.info("Descarga web de '%s' finalizada exitosamente: %s", task_id, out_file)
                self._sap_download_seq += 1
                self._sap_download_result = {
                    "id": self._sap_download_seq,
                    "task_id": task_id,
                    "status": "ok",
                    "message": f"Descarga SAP de '{task_id.upper()}' completada: {out_file.name}",
                }
            except Exception as exc:
                logger.error("Error en descarga SAP desde interfaz web para '%s': %s", task_id, exc)
                self._sap_download_seq += 1
                self._sap_download_result = {
                    "id": self._sap_download_seq,
                    "task_id": task_id,
                    "status": "error",
                    "message": f"Error en descarga SAP '{task_id.upper()}': {exc}",
                }
            finally:
                if connected:
                    try:
                        finalize_sap_session(mgr, close_at_end=close_at_end)
                    except Exception as exc_close:
                        logger.warning("Aviso al cerrar sesión SAP tras descarga web: %s", exc_close)
                self._sap_download_running = False

        threading.Thread(target=_worker, daemon=True, name=f"SapDownload-{task_id}").start()

        p_label = p_eff_low if p_eff_low == p_eff_high else f"{p_eff_low}..{p_eff_high}"
        if key == "gd20":
            detail = f"Ejercicio {y_eff_low}, Período {p_label}"
        elif key in ("zbcs", "query"):
            detail = f"3 meses hasta {q_to_preview}"
        elif key in ("all", "batch", "lote", "todos"):
            detail = f"GD20 {y_eff_low}/{p_label} + Query hasta {q_to_preview}"
        else:
            detail = f"Período {p_label}"

        return {
            "status": "ok",
            "message": f"Descarga SAP de '{task_id.upper()}' iniciada ({detail}).",
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
            "sap_download_running": self._sap_download_running,
            "sap_download_result": self._sap_download_result,
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
        # Prueba de SAP Logon verificando el ejecutable, credenciales configuradas y sesión COM.
        sap_path = os.getenv("SAP_LOGON_PATH", r"C:\Program Files (x86)\SAP\FrontEnd\SAPgui\saplogon.exe")
        ambient = os.getenv("SAP_AMBIENT", "").strip()
        mandante = os.getenv("SAP_MANDANTE", "300").strip()
        system_id = os.getenv("SAP_SYSTEM", os.getenv("SAP_SISTEMA", "E05")).strip()
        sap_user = (os.getenv("SAP_USER") or os.getenv("SAP_USUARIO") or "").strip()
        sap_password = (os.getenv("SAP_PASSWORD") or "").strip()

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
            info = getattr(session, "Info", None)
            sys_live = getattr(info, "SystemName", "") or system_id
            usr_live = getattr(info, "User", "") or sap_user or "sin login"
            return {
                "ok": True,
                "message": f"SAP GUI Scripting CONECTADO (Sistema {sys_live}, Mandante {mandante}, Usuario {usr_live}).",
            }
        except Exception:
            missing_cfg = [
                k for k, v in (("SAP_AMBIENT", ambient), ("SAP_USER", sap_user), ("SAP_PASSWORD", sap_password)) if not v
            ]
            if missing_cfg:
                return {
                    "ok": False,
                    "message": f"Falta configurar {', '.join(missing_cfg)} en .env para login automático en SAP.",
                }
            return {
                "ok": True,
                "message": f"saplogon.exe y credenciales OK en .env. Ambiente objetivo: {ambient}.",
            }

    def validate_web_configuration(
        self,
        profile_id: str | None = None,
        profile_json: str | None = None,
    ) -> dict[str, Any]:
        load_dotenv(ENV_FILE_PATH, override=True)
        from itacamba_reportes.sap.config import CONFIG_GD20, CONFIG_QUERY

        checks: list[dict[str, str]] = []

        # 1. Archivo .env
        if ENV_FILE_PATH.exists():
            checks.append({"id": "env", "label": "Archivo .env", "status": "ok", "detail": str(ENV_FILE_PATH.name)})
        else:
            checks.append({"id": "env", "label": "Archivo .env", "status": "error", "detail": "No existe .env en la raíz del proyecto."})

        # 2. Credenciales y rutas críticas de SAP en .env + estado SAP GUI
        sap_missing = [
            key for key in ("SAP_LOGON_PATH", "SAP_AMBIENT", "SAP_USER", "SAP_PASSWORD")
            if not (os.getenv(key) or (key == "SAP_USER" and os.getenv("SAP_USUARIO")) or "").strip()
        ]
        sap_res = self.test_sap_logon()
        if sap_missing and not sap_res.get("ok"):
            checks.append({"id": "sap_cfg", "label": "Configuración SAP (.env)", "status": "error", "detail": f"Faltan variables: {', '.join(sap_missing)}."})
        elif sap_missing:
            checks.append({"id": "sap_cfg", "label": "Configuración SAP (.env)", "status": "warn", "detail": f"Faltan variables: {', '.join(sap_missing)} (solo afectará auto-login)."})
        else:
            checks.append({"id": "sap_cfg", "label": "Configuración SAP (.env)", "status": "ok", "detail": f"Ambiente '{os.getenv('SAP_AMBIENT')}', Usuario '{os.getenv('SAP_USER') or os.getenv('SAP_USUARIO')}'."})

        checks.append({
            "id": "sap_gui",
            "label": "SAP GUI Scripting",
            "status": "ok" if sap_res.get("ok") else "error",
            "detail": str(sap_res.get("message") or ""),
        })

        # 3. Configuración y conectividad real a SQL Server
        db_url = (os.getenv("DATABASE_URL") or "").strip()
        db_missing = [] if db_url else [
            key for key in ("DB_SERVER", "DB_NAME", "DB_USER", "DB_PASSWORD")
            if not (os.getenv(key) or "").strip()
        ]
        if db_missing:
            checks.append({"id": "sql_cfg", "label": "Configuración SQL (.env)", "status": "error", "detail": f"Faltan variables: {', '.join(db_missing)}."})
        else:
            target_db_desc = "DATABASE_URL configurada" if db_url else f"{os.getenv('DB_SERVER')} / {os.getenv('DB_NAME')}"
            checks.append({"id": "sql_cfg", "label": "Configuración SQL (.env)", "status": "ok", "detail": target_db_desc})

        sql_res = self.test_sql_connection()
        checks.append({
            "id": "sql_conn",
            "label": "Conexión SQL Server",
            "status": "ok" if sql_res.get("ok") else "error",
            "detail": str(sql_res.get("message") or ""),
        })

        # 4. Segmentación e integridad de las 3 rutas independientes (Fijos, Dinámicos, Entrega de Reportes)
        resolved_paths = self._resolve_storage_paths()
        route_specs = (
            ("PATH_INSUMOS_FIJOS", "Insumos Fijos (fijos/)", ("REFERENCIAS", "PROYECCION"), False),
            ("PATH_INSUMOS_DINAMICOS", "Insumos Dinámicos (dinamicos/)", ("CARTERA", "GD20", "QUERY"), True),
            ("PATH_REPORTES_SALIDA", "Entrega de Reportes (reports/)", (), True),
        )

        unsegmented_keys = [
            env_key for env_key, _lbl, _pats, _rw in route_specs if not (os.getenv(env_key) or "").strip()
        ]
        if unsegmented_keys:
            checks.append({
                "id": "routes_segmentation",
                "label": "Segmentación de rutas (.env)",
                "status": "warn",
                "detail": (
                    f"Usando respaldo/predeterminado para: {', '.join(unsegmented_keys)}. "
                    "Define PATH_INSUMOS_FIJOS, PATH_INSUMOS_DINAMICOS y PATH_REPORTES_SALIDA en Configuración (.env) para control independiente."
                ),
            })
        else:
            checks.append({
                "id": "routes_segmentation",
                "label": "Segmentación de rutas (.env)",
                "status": "ok",
                "detail": "Las 3 rutas (Fijos, Dinámicos y Entrega de Reportes) están segmentadas explícitamente en .env.",
            })

        resolved_norms: dict[str, list[str]] = {}
        for env_key, _lbl, _pats, _rw in route_specs:
            val = resolved_paths.get(env_key, "").strip()
            if val:
                norm = str(Path(val).resolve()).lower()
                resolved_norms.setdefault(norm, []).append(env_key)
        collisions = [keys for keys in resolved_norms.values() if len(keys) > 1]
        if collisions:
            collided_str = "; ".join(" y ".join(grp) for grp in collisions)
            checks.append({
                "id": "routes_collision",
                "label": "Separación de carpetas",
                "status": "error",
                "detail": f"Colisión detectada ({collided_str}) apuntando al mismo directorio. Deben ser 3 carpetas independientes.",
            })

        routes_summary: list[dict[str, Any]] = []
        for env_key, key_lbl, required_patterns, requires_write in route_specs:
            folder_val = resolved_paths.get(env_key, "").strip()
            explicit_val = (os.getenv(env_key) or "").strip()
            if explicit_val:
                origin = "segmentada (.env)"
                is_segmented = True
            elif env_key == "PATH_REPORTES_SALIDA" and (os.getenv("EXPORT_PATH") or "").strip():
                origin = "respaldo (EXPORT_PATH)"
                is_segmented = False
            elif env_key != "PATH_REPORTES_SALIDA" and (os.getenv("DATA_PATH") or "").strip():
                origin = "respaldo (DATA_PATH)"
                is_segmented = False
            else:
                origin = "predeterminada (storage/)"
                is_segmented = False

            if not folder_val:
                msg = "Ruta no definida en .env."
                checks.append({"id": f"path_{key_lbl}", "label": key_lbl, "status": "error", "detail": msg})
                routes_summary.append({
                    "key": env_key,
                    "label": key_lbl,
                    "path": "",
                    "origin": origin,
                    "segmented": is_segmented,
                    "exists": False,
                    "writable": False if requires_write else None,
                    "xlsx_count": 0,
                    "status": "error",
                    "detail": msg,
                })
                continue

            p_dir = Path(folder_val)
            if not p_dir.exists():
                msg = f"[{origin}] La carpeta no existe: {p_dir}"
                checks.append({"id": f"path_{key_lbl}", "label": key_lbl, "status": "error", "detail": msg})
                routes_summary.append({
                    "key": env_key,
                    "label": key_lbl,
                    "path": str(p_dir),
                    "origin": origin,
                    "segmented": is_segmented,
                    "exists": False,
                    "writable": False if requires_write else None,
                    "xlsx_count": 0,
                    "status": "error",
                    "detail": msg,
                })
                continue

            writable_ok = True
            write_err = ""
            if requires_write:
                probe = p_dir / f".itacamba_write_{os.getpid()}_{threading.get_ident()}.tmp"
                try:
                    probe.write_bytes(b"")
                except Exception as exc:
                    writable_ok = False
                    write_err = str(exc)
                finally:
                    try:
                        if probe.exists():
                            probe.unlink()
                    except Exception:
                        pass

            if not writable_ok:
                msg = f"[{origin}] Sin permiso de escritura en {p_dir}: {write_err}"
                checks.append({"id": f"path_{key_lbl}", "label": key_lbl, "status": "error", "detail": msg})
                routes_summary.append({
                    "key": env_key,
                    "label": key_lbl,
                    "path": str(p_dir),
                    "origin": origin,
                    "segmented": is_segmented,
                    "exists": True,
                    "writable": False,
                    "xlsx_count": 0,
                    "status": "error",
                    "detail": msg,
                })
                continue

            xlsx_names = [f.name.upper() for f in p_dir.glob("*.xlsx") if not f.name.startswith("~$")]
            missing_files = [pat for pat in required_patterns if not any(n.startswith(pat) for n in xlsx_names)]
            if missing_files:
                status_lvl = "warn" if env_key == "PATH_INSUMOS_DINAMICOS" else "error"
                msg = (
                    f"[{origin}] {p_dir} ({len(xlsx_names)} .xlsx). "
                    f"Faltan: {', '.join(missing_files)} (se actualizarán al descargar)."
                )
            elif requires_write:
                status_lvl = "ok"
                msg = f"[{origin}] {p_dir} (escritura OK, {len(xlsx_names)} .xlsx listos)."
            else:
                status_lvl = "ok"
                msg = f"[{origin}] {p_dir} ({len(xlsx_names)} .xlsx listos)."

            checks.append({"id": f"path_{key_lbl}", "label": key_lbl, "status": status_lvl, "detail": msg})
            routes_summary.append({
                "key": env_key,
                "label": key_lbl,
                "path": str(p_dir),
                "origin": origin,
                "segmented": is_segmented,
                "exists": True,
                "writable": True if requires_write else None,
                "xlsx_count": len(xlsx_names),
                "status": status_lvl,
                "detail": msg,
            })

        # 5. Coherencia del perfil activo y parámetros resueltos para GD20 y Query
        prof_obj: dict[str, Any] = {}
        if profile_json:
            try:
                parsed = json.loads(profile_json) if isinstance(profile_json, str) else profile_json
                if isinstance(parsed, dict):
                    prof_obj = parsed
            except Exception:
                pass
        if not prof_obj:
            profiles = self.get_execution_profiles()
            p_key = str(profile_id).split(":")[0] if profile_id else None
            prof_obj = next((p for p in profiles if p_key and str(p.get("id")) == p_key), None) or \
                next((p for p in profiles if p.get("activa")), profiles[0] if profiles else {})

        fecha_desde = prof_obj.get("fechaDesde")
        fecha_hasta = prof_obj.get("fechaHasta")
        current_month_start = datetime.now().replace(day=1).strftime("%Y-%m-%d")
        if fecha_desde and fecha_hasta and str(fecha_desde) > str(fecha_hasta):
            checks.append({
                "id": "profile",
                "label": "Perfil activo",
                "status": "error",
                "detail": f"{prof_obj.get('nombre', 'Perfil')}: fechaDesde ({fecha_desde}) es posterior a fechaHasta ({fecha_hasta}).",
            })
        elif fecha_hasta and str(fecha_hasta) < current_month_start and prof_obj.get("modo") != "rango":
            checks.append({
                "id": "profile",
                "label": "Perfil activo",
                "status": "warn",
                "detail": f"{prof_obj.get('nombre', 'Predeterminado')} apunta a mes anterior ({fecha_desde} -> {fecha_hasta}). Ajusta 'Mes de ejecución' en Programador si buscas el mes actual.",
            })
        else:
            checks.append({
                "id": "profile",
                "label": "Perfil activo",
                "status": "ok",
                "detail": f"{prof_obj.get('nombre', 'Predeterminado')} · {fecha_desde or 'auto'} -> {fecha_hasta or 'auto'}",
            })

        p_low, p_high, y_low, y_high, date_to_sap = self._resolve_sap_config_dates(
            fecha_desde=fecha_desde,
            corte_fecha=fecha_hasta,
            profile_id=prof_obj.get("id") or profile_id,
        )
        cfg_gd20 = CONFIG_GD20.to_download_config(
            period_override=p_low,
            period_high_override=p_high,
            year_override=y_low,
            year_high_override=y_high,
        )
        cfg_query = CONFIG_QUERY.to_download_config(date_to_override=date_to_sap)

        err_count = sum(1 for c in checks if c["status"] == "error")
        warn_count = sum(1 for c in checks if c["status"] == "warn")
        return {
            "ok": err_count == 0,
            "errors": err_count,
            "warnings": warn_count,
            "checks": checks,
            "routes_summary": routes_summary,
            "sap_resolved": {
                "profile_name": prof_obj.get("nombre") or "Perfil activo",
                "mes_ejecucion": prof_obj.get("mesEjecucion") or "",
                "gd20_year": f"{cfg_gd20.year_low}" + (f"..{cfg_gd20.year_high}" if cfg_gd20.year_high else ""),
                "gd20_period": f"{cfg_gd20.period_low}" if cfg_gd20.period_low == cfg_gd20.period_high else f"{cfg_gd20.period_low}..{cfg_gd20.period_high}",
                "gd20_layout": cfg_gd20.layout_name or "//AVRILGD20",
                "gd20_variant": cfg_gd20.variant or "BOT_GD20",
                "query_sociedad": cfg_query.sociedad or "4253",
                "query_variant": cfg_query.variant or "/IM",
                "query_date_from": cfg_query.date_from,
                "query_date_to": cfg_query.date_to,
            },
            "summary": "Configuración lista para probar GD20 y Query." if err_count == 0 else f"Se detectaron {err_count} error(es) y {warn_count} aviso(s).",
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

            for item in vars_list:
                k = str(item.get("clave") or "").strip().upper()
                val = str(item.get("valor") or "").strip()
                act = item.get("activa", True)
                if k and (not act or not val):
                    os.environ.pop(k, None)

            with open(ENV_FILE_PATH, "w", encoding="utf-8") as f:
                f.write("\n".join(lines).strip() + "\n")

            load_dotenv(ENV_FILE_PATH, override=True)
            from itacamba_reportes.core.settings import EnvConfig
            from itacamba_reportes.core.db.connection import set_engine
            EnvConfig.reload(ENV_FILE_PATH)
            set_engine(None)
            return {"status": "ok", "message": "Archivo .env guardado en disco y aplicado en memoria."}
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

    def get_execution_calendar(self) -> dict[str, Any]:
        if not CALENDAR_PATH.exists():
            return {}
        try:
            with open(CALENDAR_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception as exc:
            logger.warning("Error leyendo calendario %s: %s", CALENDAR_PATH, exc)
            return {}

    def save_execution_calendar(self, calendar_json: str) -> dict[str, Any]:
        try:
            data = json.loads(calendar_json) if isinstance(calendar_json, str) else calendar_json
            if not isinstance(data, dict):
                return {"status": "error", "message": "El calendario tiene un formato inválido."}
            calendars = data.get("perfiles")
            if calendars is not None:
                if not isinstance(calendars, dict) or any(
                    not isinstance(item, dict) or not isinstance(item.get("asignaciones", {}), dict)
                    for item in calendars.values()
                ):
                    return {"status": "error", "message": "Las agendas de los perfiles tienen un formato inválido."}
            elif not isinstance(data.get("asignaciones", {}), dict):
                return {"status": "error", "message": "El calendario tiene un formato inválido."}
            CALENDAR_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(CALENDAR_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return {"status": "ok", "message": "Calendario de ejecución guardado."}
        except Exception as exc:
            return {"status": "error", "message": f"Error guardando calendario: {exc}"}

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
                "ayuda": "Alimenta BASE PANEL y VENTAS BI en SQL Server (toma automáticamente el mes de ejecución si Período está vacío).",
                "destino": "GD20.xlsx",
                "variante": "BOT_GD20",
                "layout": "//AVRILGD20",
                "layout_name": "//AVRILGD20",
                "ledger": "VC",
                "periodoTipo": "mes_actual",
                "campos": [
                    {"id": "ledger", "etiqueta": "Ledger Contable", "valor": "VC"},
                    {"id": "variante", "etiqueta": "Variante SAP", "valor": "BOT_GD20"},
                    {"id": "ejercicio", "etiqueta": "Ejercicio / Año", "valor": "", "tipo": "number", "nota": "Vacío = año automático del perfil"},
                    {"id": "periodo", "etiqueta": "Período / Mes", "valor": "", "tipo": "number", "nota": "Vacío = mes automático del perfil"},
                    {"id": "layout", "etiqueta": "Layout ALV", "valor": "//AVRILGD20", "nota": "Disposición de columnas en SAP"},
                ],
            },
            {
                "id": "zbcs",
                "tcode": "ZVCSD381",
                "titulo": "Despachos Query (ZVCSD381)",
                "ayuda": "Alimenta QUERY, DESPACHO BI y DESPACHO MES (3 meses móviles hacia atrás si fechas quedan vacías).",
                "destino": "QUERY.xlsx",
                "variante": "/IM",
                "layout": "",
                "ledger": "N/A",
                "periodoTipo": "rango",
                "campos": [
                    {"id": "sociedad", "etiqueta": "Sociedad", "valor": "4253"},
                    {"id": "desde", "etiqueta": "Fecha Desde", "valor": "", "tipo": "date", "nota": "Vacío = 3 meses atrás automático"},
                    {"id": "hasta", "etiqueta": "Fecha Hasta", "valor": "", "tipo": "date", "nota": "Vacío = fecha de hoy"},
                    {"id": "variante", "etiqueta": "Disposición / Variante", "valor": "/IM", "nota": "Variante de selección grabada"},
                ],
            },
            {
                "id": "all",
                "tcode": "LOTE",
                "titulo": "Descarga Conjunta (GD20 + Query)",
                "ayuda": "1 solo Login -> GD20 (periodo configurado) -> Easy Access -> Query (3 meses atras) -> Cierre seguro.",
                "destino": "GD20.xlsx + QUERY.xlsx",
                "variante": "BOT_GD20 + /IM",
                "layout": "//AVRILGD20",
                "ledger": "VC",
                "periodoTipo": "mes_actual",
                "campos": [],
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
        paths = self._resolve_storage_paths()
        folder = (os.getenv(path_key) or paths.get(path_key) or "").strip()
        if not folder or not Path(folder).exists():
            folder = str(PROJECT_ROOT)
        try:
            os.startfile(folder)
            return {"status": "ok", "folder": folder}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def open_file_excel(self, file_name: str) -> dict[str, Any]:
        reportes_path = Path(self._resolve_storage_paths()["PATH_REPORTES_SALIDA"])
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
        if ENV_FILE_PATH.exists():
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

        existing_keys = {item["clave"].upper() for item in result}
        default_route_vars = (
            (
                "PATH_INSUMOS_FIJOS",
                "Ruta de archivos fijos (REFERENCIAS.xlsx, PROYECCION-SEMANAL.xlsx)",
            ),
            (
                "PATH_INSUMOS_DINAMICOS",
                "Ruta de insumos dinámicos (descargas SAP GD20/QUERY y CARTERA.xlsx)",
            ),
            (
                "PATH_REPORTES_SALIDA",
                "Ruta de entrega de reportes BI generados (VENTAS_BI, DESPACHO_BI, HISTORIAL)",
            ),
        )
        for key_name, desc_text in default_route_vars:
            if key_name not in existing_keys:
                result.append({
                    "clave": key_name,
                    "valor": "",
                    "descripcion": desc_text,
                    "categoria": "rutas",
                    "esSecreto": False,
                    "activa": True,
                    "revelado": False,
                })
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
