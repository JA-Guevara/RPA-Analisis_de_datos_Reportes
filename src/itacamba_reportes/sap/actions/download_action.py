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

logger = logging.getLogger(__name__)


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
        "Iniciando descarga parametrizada en SAP (Tx: %s, Variante: %s, Periodo: %s, Fechas: %s a %s, Archivo: %s)",
        config.transaction,
        config.variant,
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
            session_manager.press_button(sel.gd20.popup_btn_find_variant, timeout=5.0)
            time.sleep(0.5)

        # Paso 4: Parametrizacion dinamica de periodos
        if config.period_low is not None and session_manager.element_exists(sel.gd20.period_low, timeout=5.0):
            session_manager.set_text(sel.gd20.period_low, str(config.period_low))
        if config.period_high is not None and session_manager.element_exists(sel.gd20.period_high, timeout=2.0):
            session_manager.set_text(sel.gd20.period_high, str(config.period_high))

    # Paso 5: Ejecutar reporte F8
    logger.info("Ejecutando reporte en SAP con F8...")
    session_manager.press_button(sel.barra.btn_execute_f8)
    time.sleep(2.0)

    # Paso 6: Seleccion de layout ALV (por nombre o por fila, tipico en GD20)
    needs_layout = bool(config.layout_name or config.layout_row is not None)

    if needs_layout:
        logger.info("Esperando visualización del reporte ALV en SAP (botón btn[33])...")
        if session_manager.element_exists(sel.gd20.btn_choose_layout, timeout=45.0):
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
                grid.clickCurrentCell()
                time.sleep(1.5)

                if getattr(session_manager.session.ActiveWindow, "Name", "") == "wnd[1]":
                    session_manager.session.findById("wnd[1]/tbar[0]/btn[0]").press()
                    time.sleep(1.0)

                logger.info("Disposición ALV aplicada exitosamente.")
            except Exception as exc:
                logger.warning("No se pudo seleccionar disposición ALV: %s", exc)
        else:
            logger.warning("No se detectó el botón de disposición ALV (btn[33]) tras ejecutar reporte.")

    # Paso 7: Exportacion a archivo Excel / Hoja de Calculo
    try:
        logger.info("Iniciando exportación a Excel en SAP (sendVKey 43 / Menú)...")
        filename_base = Path(config.export_filename).stem
        target_name = Path(config.export_filename).name

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

    # Paso 11: Resolucion y ubicacion final del archivo descargado
    target_name = Path(config.export_filename).name
    candidate_paths = [
        Path(config.target_dir or ".") / target_name,
        Path(config.export_filename),
        Path.cwd() / target_name,
        Path.home() / "Documents" / "SAP" / "SAP GUI" / target_name,
        Path.home() / "Documents" / target_name,
        Path.home() / "Documents" / "Archivos" / target_name,
        Path.home() / "Downloads" / target_name,
    ]
    found_file = next((p for p in candidate_paths if p.exists() and p.is_file()), None)

    if found_file and config.target_dir:
        target_dir = Path(config.target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        dest = target_dir / found_file.name
        if found_file.resolve() != dest.resolve():
            shutil.move(str(found_file), str(dest))
        out_path = dest
    elif found_file:
        out_path = found_file
    else:
        out_path = Path(config.target_dir or ".") / target_name

    logger.info("Descarga parametrizada de %s finalizada: %s", config.transaction, out_path)
    return out_path


def execute_download_all_sap(
    session_manager: SapSessionManager | None = None,
    target_dir: Path | str | None = None,
    period_gd20: str | int | None = None,
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
        # 2. Descarga GD20 (Mes en curso o indicado)
        cfg_gd20 = CONFIG_GD20.to_download_config(target_dir=dest_dir, period_override=period_gd20)
        logger.info("--> [1/2] Ejecutando descarga GD20 (Período: %s)...", cfg_gd20.period_low)
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
        # 4. Cierre en 2 niveles si se solicita
        if close_at_end:
            logger.info("Finalizadas todas las descargas. Procediendo al cierre en 2 niveles (logout /nex y kill)...")
            try:
                from itacamba_reportes.sap.actions.logout_action import execute_logout
                execute_logout(mgr)
            except Exception as exc:
                logger.warning("Aviso durante logout (/nex): %s", exc)
            time.sleep(1.0)
            mgr.kill_sap_processes()
        else:
            mgr.return_to_main_menu()

    return results
