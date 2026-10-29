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
    is_gd20 = config.transaction.strip().lower() == "gd20"
    logger.info(
        "Iniciando descarga parametrizada en SAP (Tx: %s, Variante: %s, Periodo: %s, Archivo: %s)",
        config.transaction,
        config.variant,
        config.period_low,
        config.export_filename,
    )

    # Paso 1: Navegacion dinamica a la transaccion solicitada
    session_manager.set_text(sel.barra.okcode, config.transaction)
    session_manager.send_vkey(sel.barra.btn_enter_key, window_id=sel.ventana.main)
    time.sleep(1.0)

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

    # Paso 5: Parametrizacion dinamica de rangos de fecha
    if config.date_from and session_manager.element_exists(sel.zbcs.fecha_desde, timeout=5.0):
        session_manager.set_text(sel.zbcs.fecha_desde, str(config.date_from))
    if config.date_to and session_manager.element_exists(sel.zbcs.fecha_hasta, timeout=2.0):
        session_manager.set_text(sel.zbcs.fecha_hasta, str(config.date_to))

    # Paso 6: Entradas de formulario personalizadas adicionales
    if config.custom_inputs:
        for selector, val in config.custom_inputs.items():
            if session_manager.element_exists(selector, timeout=2.0):
                session_manager.set_text(selector, str(val))

    # Paso 7: Ejecutar reporte F8
    logger.info("Ejecutando reporte en SAP con F8...")
    session_manager.press_button(sel.barra.btn_execute_f8)
    time.sleep(1.5)

    # Paso 8: Seleccion de layout ALV (para GD20 o si se especifica fila/nombre)
    target_row = config.layout_row
    if target_row is None and is_gd20:
        target_row = 16  # Fila 16 identificada en grabaciones VBScript para GD20

    if target_row is not None or config.layout_name:
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

                # Búsqueda dinámica por nombre si fue provisto
                if config.layout_name:
                    try:
                        row_count = int(getattr(grid, "RowCount", 0))
                        for r in range(row_count):
                            val_var = str(grid.GetCellValue(r, "VARIANT") or "").strip()
                            val_txt = str(grid.GetCellValue(r, "TEXT") or "").strip()
                            if config.layout_name.lower() in val_var.lower() or config.layout_name.lower() in val_txt.lower():
                                target_row = r
                                logger.info("Layout '%s' encontrado en fila %d (%s)", config.layout_name, r, val_txt)
                                break
                    except Exception as exc:
                        logger.debug("Búsqueda por nombre de layout no concluyente: %s", exc)

                chosen_row = target_row if target_row is not None else 16
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

                # Si el modal wnd[1] sigue abierto, confirmar selección
                try:
                    if getattr(session_manager.session.ActiveWindow, "Name", "") == "wnd[1]":
                        session_manager.session.findById("wnd[1]/tbar[0]/btn[0]").press()
                        time.sleep(1.0)
                except Exception:
                    pass

                logger.info("Disposición ALV aplicada exitosamente.")
            except Exception as exc:
                logger.warning("No se pudo seleccionar disposición ALV: %s", exc)
        else:
            logger.warning("No se detectó el botón de disposición ALV (btn[33]) tras ejecutar reporte.")

    # Paso 9: Exportacion a archivo Excel / Hoja de Calculo
    try:
        logger.info("Iniciando exportación a Excel vía menú de SAP (Lista -> Exportar -> Hoja de cálculo)...")
        if session_manager.element_exists(sel.gd20.menu_export_excel, timeout=15.0):
            session_manager.session.findById(sel.gd20.menu_export_excel).select()
            time.sleep(1.5)

            filename_base = Path(config.export_filename).stem
            target_name = Path(config.export_filename).name

            # Diálogo inicial de formato o nombre
            if session_manager.element_exists(sel.gd20.export_filename, timeout=3.0):
                session_manager.set_text(sel.gd20.export_filename, filename_base)
                logger.info("Nombre base de archivo configurado: %s", filename_base)

            if session_manager.element_exists(sel.gd20.export_btn_generate, timeout=5.0):
                session_manager.press_button(sel.gd20.export_btn_generate)
                time.sleep(1.5)

            # Diálogo de ruta y nombre directo (DY_PATH / DY_FILENAME) según Script4.vbs
            if session_manager.element_exists(sel.gd20.export_dir_path, timeout=5.0):
                dest_dir = str(Path(config.target_dir).resolve()) if config.target_dir else str(Path.cwd().resolve())
                session_manager.set_text(sel.gd20.export_dir_path, dest_dir)
                if session_manager.element_exists(sel.gd20.export_file_name_direct, timeout=2.0):
                    session_manager.set_text(sel.gd20.export_file_name_direct, target_name)
                logger.info("Ruta de exportación directa asignada en SAP: %s\\%s", dest_dir, target_name)

            # Confirmar guardado / reemplazo (btn[11])
            if session_manager.element_exists(sel.gd20.export_btn_replace, timeout=5.0):
                session_manager.press_button(sel.gd20.export_btn_replace)
                time.sleep(1.0)
        else:
            raise SapExportError(f"No se encontró el menú de exportación Excel: {sel.gd20.menu_export_excel}")
    except Exception as exc:
        raise SapExportError(f"Fallo durante la exportacion en transaccion {config.transaction}: {exc}") from exc

    # Paso 10: Retorno limpio al menu principal de SAP
    for _ in range(4):
        try:
            session_manager.press_button(sel.barra.btn_back)
            time.sleep(0.3)
        except Exception:
            pass

    if session_manager.element_exists(sel.gd20.exit_confirm_dialog, timeout=2.0):
        try:
            session_manager.press_button(sel.gd20.exit_confirm_dialog)
            time.sleep(0.5)
        except Exception:
            pass

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
