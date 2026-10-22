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

    # Paso 2: Ledger si aplica
    if config.ledger and session_manager.element_exists(sel.gd20.ledger):
        session_manager.set_text(sel.gd20.ledger, str(config.ledger))
        session_manager.send_vkey(sel.barra.btn_enter_key, window_id=sel.ventana.main)

    # Paso 3: Carga dinamica de variante si se especifica
    if config.variant and session_manager.element_exists(sel.gd20.btn_get_variant):
        session_manager.press_button(sel.gd20.btn_get_variant)
        session_manager.set_text(sel.gd20.popup_variant_name, str(config.variant))
        session_manager.press_button(sel.gd20.popup_btn_find_variant)

    # Paso 4: Parametrizacion dinamica de periodos
    if config.period_low is not None and session_manager.element_exists(sel.gd20.period_low):
        session_manager.set_text(sel.gd20.period_low, str(config.period_low))
    if config.period_high is not None and session_manager.element_exists(sel.gd20.period_high):
        session_manager.set_text(sel.gd20.period_high, str(config.period_high))

    # Paso 5: Parametrizacion dinamica de rangos de fecha
    if config.date_from and session_manager.element_exists(sel.zbcs.fecha_desde):
        session_manager.set_text(sel.zbcs.fecha_desde, str(config.date_from))
    if config.date_to and session_manager.element_exists(sel.zbcs.fecha_hasta):
        session_manager.set_text(sel.zbcs.fecha_hasta, str(config.date_to))

    # Paso 6: Entradas de formulario personalizadas adicionales
    if config.custom_inputs:
        for selector, val in config.custom_inputs.items():
            if session_manager.element_exists(selector):
                session_manager.set_text(selector, str(val))

    # Paso 7: Ejecutar reporte F8
    session_manager.press_button(sel.barra.btn_execute_f8)
    time.sleep(1.0)

    # Paso 8: Seleccion de layout ALV si se solicita
    if config.layout_row is not None and session_manager.element_exists(sel.gd20.btn_choose_layout):
        try:
            session_manager.press_button(sel.gd20.btn_choose_layout)
            grid = session_manager.find_element(sel.gd20.layout_grid, timeout=10.0)
            grid.setCurrentCell(config.layout_row, "TEXT")
            grid.selectedRows = str(config.layout_row)
            grid.clickCurrentCell()
            time.sleep(1.0)
        except Exception as exc:
            logger.warning("No se pudo seleccionar disposicion ALV fila %d: %s", config.layout_row, exc)

    # Paso 9: Exportacion a archivo Excel / Hoja de Calculo
    try:
        if session_manager.element_exists(sel.gd20.menu_export_excel):
            session_manager.session.findById(sel.gd20.menu_export_excel).select()
            session_manager.set_text(sel.gd20.export_filename, config.export_filename, timeout=8.0)
            session_manager.press_button(sel.gd20.export_btn_generate)

            time.sleep(0.5)
            if session_manager.element_exists(sel.gd20.export_btn_replace):
                session_manager.press_button(sel.gd20.export_btn_replace)
    except Exception as exc:
        raise SapExportError(f"Fallo durante la exportacion en transaccion {config.transaction}: {exc}") from exc

    # Paso 10: Retorno limpio al menu principal de SAP
    for _ in range(4):
        try:
            session_manager.press_button(sel.barra.btn_back)
            time.sleep(0.3)
        except Exception:
            pass

    if session_manager.element_exists(sel.gd20.exit_confirm_dialog):
        session_manager.press_button(sel.gd20.exit_confirm_dialog)

    # Paso 11: Resolucion y ubicacion final del archivo descargado
    out_path = Path(config.export_filename)
    if config.target_dir:
        target_dir = Path(config.target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        if out_path.exists():
            dest = target_dir / out_path.name
            shutil.move(str(out_path), str(dest))
            out_path = dest

    logger.info("Descarga parametrizada de %s finalizada: %s", config.transaction, out_path)
    return out_path
