from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path

from itacamba_reportes.sap.config import SapDownloadConfig
from itacamba_reportes.sap.exceptions import SapExportError
from itacamba_reportes.sap.selectors import (
    SELECTORES_SAP,
    SelectoresSAP,
)
from itacamba_reportes.sap.session import SapSessionManager
from itacamba_reportes.sap.win_dialogs import SapSecurityWatchdog, close_excel_workbook_by_name

logger = logging.getLogger(__name__)


def _wait_for_alv_after_f8(
    session_manager: SapSessionManager,
    sel: SelectoresSAP,
    transaction: str,
    timeout: float = 240.0,
) -> None:
    logger.info("Esperando respuesta de %s en SAP tras F8...", transaction)
    elapsed = 0.0
    step = 0.5
    while elapsed < timeout:
        msg = session_manager.get_status_message()
        if isinstance(msg, tuple) and len(msg) == 2:
            msg_type, msg_text = msg
            if msg_type in ("E", "A") and msg_text:
                raise SapExportError(f"SAP rechazó la ejecución de {transaction}: {msg_text}")
            if msg_type == "S" and "no se han seleccionado datos" in msg_text.lower():
                raise SapExportError(f"SAP no devolvió datos en {transaction}: {msg_text}")

        if session_manager.element_exists(sel.gd20.btn_choose_layout, timeout=0.0) or \
           session_manager.element_exists(sel.gd20.menu_export_excel, timeout=0.0):
            return

        time.sleep(step)
        elapsed += step


def finalize_sap_session(
    session_manager: SapSessionManager,
    close_at_end: bool = True,
) -> None:
    if close_at_end:
        logger.info("Finalizando sesión SAP en 2 niveles (/nex + cierre de proceso)...")
        try:
            from itacamba_reportes.sap.actions.logout_action import execute_logout
            execute_logout(session_manager)
        except Exception as exc:
            logger.warning("Aviso durante logout (/nex): %s", exc)
        time.sleep(1.0)
        session_manager.kill_sap_processes()
    else:
        session_manager.return_to_main_menu()


def execute_download_report(
    session_manager: SapSessionManager,
    config: SapDownloadConfig,
    selectors: SelectoresSAP | None = None,
) -> Path:
    sel = selectors or SELECTORES_SAP
    tcode_lower = config.transaction.strip().lower()
    is_query = tcode_lower in ("zvcsd381", "zbcs", "query")
    is_gd20 = tcode_lower == "gd20"

    logger.info(
        "Iniciando descarga parametrizada en SAP (Tx: %s, Variante: %s, Ejercicio: %s, Periodo: %s, Fechas: %s a %s, Archivo: %s)",
        config.transaction,
        config.variant,
        config.year_low,
        config.period_low,
        config.date_from,
        config.date_to,
        config.export_filename,
    )

    # Paso 1: Navegacion dinamica a la transaccion solicitada
    session_manager.set_text(sel.barra.okcode, config.transaction)
    session_manager.send_vkey(sel.barra.btn_enter_key, window_id=sel.ventana.main)
    time.sleep(1.0)

    if is_query:
        # Formulario ZVCSD381 (Query de Despachos de 3 meses)
        soc = config.sociedad or "4253"
        if session_manager.element_exists(sel.query.sociedad, timeout=3.0):
            session_manager.set_text(sel.query.sociedad, str(soc))

        if config.date_from and session_manager.element_exists(sel.query.fecha_desde, timeout=2.0):
            session_manager.set_text(sel.query.fecha_desde, str(config.date_from))
        elif config.date_from and session_manager.element_exists(sel.query.fecha_desde_legacy, timeout=1.0):
            session_manager.set_text(sel.query.fecha_desde_legacy, str(config.date_from))

        if config.date_to and session_manager.element_exists(sel.query.fecha_hasta, timeout=2.0):
            session_manager.set_text(sel.query.fecha_hasta, str(config.date_to))
        elif config.date_to and session_manager.element_exists(sel.query.fecha_hasta_legacy, timeout=1.0):
            session_manager.set_text(sel.query.fecha_hasta_legacy, str(config.date_to))

        disp = config.variant or "/IM"
        if session_manager.element_exists(sel.query.disposicion, timeout=2.0):
            session_manager.set_text(sel.query.disposicion, str(disp))

    elif is_gd20:
        # Paso 2: Ledger si aplica
        if config.ledger and session_manager.element_exists(sel.gd20.ledger, timeout=5.0):
            session_manager.set_text(sel.gd20.ledger, str(config.ledger))
            session_manager.send_vkey(sel.barra.btn_enter_key, window_id=sel.ventana.main)
            time.sleep(0.5)

        # Paso 3: Carga dinamica de variante si se especifica
        if config.variant and session_manager.element_exists(sel.gd20.btn_get_variant, timeout=5.0):
            session_manager.press_button(sel.gd20.btn_get_variant)
            session_manager.set_text(sel.gd20.popup_variant_name, str(config.variant), timeout=5.0)
            if session_manager.element_exists(sel.gd20.popup_variant_created_by, timeout=1.0):
                try:
                    session_manager.set_text(sel.gd20.popup_variant_created_by, "")
                except Exception:
                    pass
            session_manager.press_button(sel.gd20.popup_btn_find_variant, timeout=5.0)
            time.sleep(0.5)
            # Si aparecen multiples variantes en lista modal, seleccionar la fila activa
            if getattr(session_manager.session.ActiveWindow, "Name", "") == "wnd[1]" and \
               session_manager.element_exists(sel.gd20.popup_variant_grid, timeout=1.0):
                try:
                    v_grid = session_manager.find_element(sel.gd20.popup_variant_grid, timeout=2.0)
                    v_grid.doubleClickCurrentCell()
                    time.sleep(0.5)
                except Exception:
                    pass

        # Paso 4: Parametrizacion dinamica de ejercicio (ano) y periodos
        if config.year_low is not None:
            year_updated = session_manager.set_selection_field_by_label(
                labels=("ejercicio", "fiscal year", "año", "year"),
                value_low=str(config.year_low),
                value_high=str(config.year_high) if config.year_high is not None else None,
                field_hint_tokens=("ryear", "gjahr"),
            )
            if not year_updated:
                logger.warning(
                    "No se pudo ubicar dinámicamente el campo 'Ejercicio' en GD20; se usará el año guardado en la variante (%s).",
                    config.variant or "default",
                )

        if config.period_low is not None and session_manager.element_exists(sel.gd20.period_low, timeout=5.0):
            session_manager.set_text(sel.gd20.period_low, str(config.period_low))
        if config.period_high is not None and session_manager.element_exists(sel.gd20.period_high, timeout=2.0):
            session_manager.set_text(sel.gd20.period_high, str(config.period_high))

    # Paso 5: Ejecutar reporte F8 y esperar carga real del ALV
    logger.info("Ejecutando reporte en SAP con F8...")
    session_manager.press_button(sel.barra.btn_execute_f8)
    _wait_for_alv_after_f8(session_manager, sel, config.transaction, timeout=240.0)

    # Paso 6: Seleccion de layout ALV (por nombre o por fila, tipico en GD20)
    needs_layout = bool(config.layout_name or config.layout_row is not None)

    if needs_layout:
        logger.info("Esperando visualización del reporte ALV en SAP (botón btn[33])...")
        if session_manager.element_exists(sel.gd20.btn_choose_layout, timeout=240.0):
            try:
                logger.info("Abriendo selector de disposición ALV (btn[33])...")
                session_manager.press_button(sel.gd20.btn_choose_layout)
                time.sleep(1.0)

                grid = session_manager.find_element(sel.gd20.layout_grid, timeout=15.0)

                if session_manager.element_exists(sel.gd20.layout_combo, timeout=2.0):
                    try:
                        session_manager.session.findById(sel.gd20.layout_combo).setFocus()
                    except Exception:
                        pass

                chosen_row = config.layout_row

                # Busqueda dinamica por nombre si fue provisto
                target_name = (config.layout_name or "").strip().lower()
                if target_name:
                    try:
                        row_count = int(getattr(grid, "RowCount", 0))
                        for r in range(row_count):
                            val_var = str(grid.GetCellValue(r, "VARIANT") or "").strip().lower()
                            val_txt = str(grid.GetCellValue(r, "TEXT") or "").strip().lower()
                            if target_name in val_var or target_name in val_txt or val_var in target_name:
                                chosen_row = r
                                logger.info("Layout '%s' encontrado dinámicamente en fila %d (%s)", config.layout_name, r, val_txt)
                                break
                    except Exception as exc:
                        logger.debug("Búsqueda por nombre de layout: %s", exc)

                if chosen_row is None:
                    if target_name:
                        logger.warning("Layout '%s' no encontrado en la grilla ALV; usando fila 0 como respaldo.", config.layout_name)
                    chosen_row = 0

                logger.info("Seleccionando disposición ALV en fila %d...", chosen_row)
                try:
                    grid.setCurrentCell(chosen_row, "TEXT")
                except Exception:
                    pass
                try:
                    grid.currentCellRow = chosen_row
                except Exception:
                    pass
                try:
                    grid.firstVisibleRow = max(0, chosen_row - 7)
                except Exception:
                    pass
                grid.selectedRows = str(chosen_row)
                try:
                    grid.clickCurrentCell()
                except Exception:
                    pass
                time.sleep(1.0)

                if getattr(session_manager.session.ActiveWindow, "Name", "") == "wnd[1]":
                    try:
                        grid.doubleClickCurrentCell()
                        time.sleep(1.0)
                    except Exception:
                        pass

                if getattr(session_manager.session.ActiveWindow, "Name", "") == "wnd[1]":
                    try:
                        session_manager.session.findById("wnd[1]/tbar[0]/btn[0]").press()
                    except Exception:
                        session_manager.send_vkey(sel.barra.btn_enter_key, window_id=sel.ventana.modal_1)
                    time.sleep(1.0)

                logger.info("Disposición ALV aplicada exitosamente.")
            except Exception as exc:
                logger.warning("No se pudo seleccionar disposición ALV: %s", exc)
        else:
            logger.warning("No se detectó el botón de disposición ALV (btn[33]) tras ejecutar reporte.")

    # Paso 7: Exportacion a archivo Excel / Hoja de Calculo
    export_started_at = time.time()
    target_name = Path(config.export_filename).name
    name_variants = list(dict.fromkeys([
        target_name,
        f"{Path(target_name).stem}.xlsx",
        f"{Path(target_name).stem}.XLSX",
    ]))
    search_dirs = [
        Path.home() / "Documents" / "SAP" / "SAP GUI",
        Path.home() / "Documents",
        Path.home() / "Downloads",
        Path(config.target_dir or "."),
        Path.cwd(),
    ]
    candidate_paths = [d / name for d in search_dirs for name in name_variants] + [Path(config.export_filename)]
    found_file: Path | None = None

    with SapSecurityWatchdog(remember_decision=True):
        try:
            logger.info("Iniciando exportación a Excel en SAP (sendVKey 43 / Menú)...")
            filename_base = Path(config.export_filename).stem

            exported_dialog_opened = False
            try:
                # Probar atajo rapido sendVKey 43 de ALV segun Script5.vbs y Script6 qyery.vbs
                session_manager.send_vkey(43, window_id=sel.ventana.main)
                time.sleep(1.5)
                if session_manager.element_exists(sel.gd20.export_filename, timeout=3.0) or \
                   session_manager.element_exists(sel.gd20.export_btn_generate, timeout=3.0):
                    exported_dialog_opened = True
            except Exception:
                pass

            if not exported_dialog_opened and session_manager.element_exists(sel.gd20.menu_export_excel, timeout=5.0):
                session_manager.session.findById(sel.gd20.menu_export_excel).select()
                time.sleep(1.5)
                exported_dialog_opened = True

            # Diálogo de exportación
            if session_manager.element_exists(sel.gd20.export_filename, timeout=3.0):
                session_manager.set_text(sel.gd20.export_filename, filename_base)
                logger.info("Nombre base de archivo configurado: %s", filename_base)

            if session_manager.element_exists(sel.gd20.export_btn_generate, timeout=5.0):
                session_manager.press_button(sel.gd20.export_btn_generate)
                time.sleep(1.5)

            # Diálogo de ruta y nombre directo si aparece (DY_PATH / DY_FILENAME)
            if session_manager.element_exists(sel.gd20.export_dir_path, timeout=3.0):
                dest_dir = str(Path(config.target_dir).resolve()) if config.target_dir else str(Path.cwd().resolve())
                session_manager.set_text(sel.gd20.export_dir_path, dest_dir)
                if session_manager.element_exists(sel.gd20.export_file_name_direct, timeout=2.0):
                    session_manager.set_text(sel.gd20.export_file_name_direct, target_name)
                logger.info("Ruta de exportación directa asignada en SAP: %s\\%s", dest_dir, target_name)

            if session_manager.element_exists(sel.gd20.export_btn_replace, timeout=5.0):
                session_manager.press_button(sel.gd20.export_btn_replace)
                time.sleep(1.5)
        except Exception as exc:
            raise SapExportError(f"Fallo durante la exportacion en transaccion {config.transaction}: {exc}") from exc

        # Paso 8: Retorno limpio al menu principal de SAP (SIN desloguear ni matar procesos)
        session_manager.return_to_main_menu()

        # Paso 11: Resolucion del archivo recien exportado (sin confundirlo con uno viejo de ayer)
        deadline = time.time() + 30.0
        while time.time() <= deadline:
            fresh_matches = [
                p for p in candidate_paths
                if p.exists() and p.is_file() and p.stat().st_mtime >= (export_started_at - 2.0)
            ]
            if fresh_matches:
                found_file = max(fresh_matches, key=lambda p: p.stat().st_mtime)
                break
            time.sleep(0.5)

    if found_file is None:
        raise SapExportError(
            f"No se detectó un archivo recién exportado para '{target_name}' tras la exportación en {config.transaction}."
        )

    # Cerrar automaticamente el libro Excel que SAP pudo haber abierto para liberar bloqueos
    close_excel_workbook_by_name([found_file.name, target_name, *name_variants], wait_timeout=3.0)

    if config.target_dir:
        target_dir = Path(config.target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        dest = target_dir / target_name
        if found_file.resolve() != dest.resolve():
            for attempt in range(3):
                try:
                    shutil.move(str(found_file), str(dest))
                    break
                except PermissionError:
                    if attempt == 2:
                        raise
                    close_excel_workbook_by_name([found_file.name, target_name, *name_variants], wait_timeout=1.5)
                    time.sleep(0.5)
        out_path = dest
    else:
        out_path = found_file

    close_excel_workbook_by_name([out_path.name, target_name], wait_timeout=0.0)
    logger.info("Descarga parametrizada de %s finalizada: %s", config.transaction, out_path)
    return out_path


def execute_download_all_sap(
    session_manager: SapSessionManager | None = None,
    target_dir: Path | str | None = None,
    period_gd20: str | int | None = None,
    period_high_gd20: str | int | None = None,
    year_gd20: str | int | None = None,
    year_high_gd20: str | int | None = None,
    date_from_query: str | None = None,
    date_to_query: str | None = None,
    close_at_end: bool = True,
) -> dict[str, Path]:
    from itacamba_reportes.core.settings import EnvConfig
    from itacamba_reportes.sap.config import CONFIG_GD20, CONFIG_QUERY

    mgr = session_manager or SapSessionManager()
    logger.info("Iniciando ciclo unificado de descargas SAP (GD20 y Query)...")

    # 1. Asegurar conexion y login una sola vez
    mgr.ensure_connected_and_ready(auto_launch=True)

    dest_dir = Path(target_dir) if target_dir else getattr(EnvConfig, "DATA_PATH", EnvConfig.PROJECT_ROOT / "storage" / "raw") / "dinamicos"
    dest_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, Path] = {}

    try:
        # 2. Descarga GD20 (Mes/año en curso o indicado)
        cfg_gd20 = CONFIG_GD20.to_download_config(
            target_dir=dest_dir,
            period_override=period_gd20,
            period_high_override=period_high_gd20,
            year_override=year_gd20,
            year_high_override=year_high_gd20,
        )
        logger.info(
            "--> [1/2] Ejecutando descarga GD20 (Ejercicio: %s%s, Períodos: %s a %s)...",
            cfg_gd20.year_low,
            f"..{cfg_gd20.year_high}" if cfg_gd20.year_high else "",
            cfg_gd20.period_low,
            cfg_gd20.period_high,
        )
        path_gd20 = execute_download_report(mgr, cfg_gd20)
        results["gd20"] = path_gd20
        logger.info("[OK] GD20 descargado exitosamente: %s", path_gd20)

        # 3. Descarga Query (3 meses atras siempre)
        cfg_query = CONFIG_QUERY.to_download_config(
            target_dir=dest_dir,
            date_from_override=date_from_query,
            date_to_override=date_to_query,
        )
        logger.info("--> [2/2] Ejecutando descarga Query ZVCSD381 (Rango: %s a %s)...", cfg_query.date_from, cfg_query.date_to)
        path_query = execute_download_report(mgr, cfg_query)
        results["query"] = path_query
        logger.info("[OK] Query ZVCSD381 descargado exitosamente: %s", path_query)

    finally:
        # 4. Cierre en 2 niveles si se solicita (o retorno limpio a Easy Access)
        finalize_sap_session(mgr, close_at_end=close_at_end)

    return results
