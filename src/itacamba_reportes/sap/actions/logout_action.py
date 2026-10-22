from __future__ import annotations

import logging

from itacamba_reportes.sap.selectors import SELECTORES_SAP, SelectoresBarra
from itacamba_reportes.sap.session import SapSessionManager

logger = logging.getLogger(__name__)


def execute_logout(
    session_manager: SapSessionManager,
    selectors: SelectoresBarra | None = None,
) -> None:
    sel = selectors or SELECTORES_SAP.barra
    try:
        session_manager.set_text(sel.okcode, "/nex")
        session_manager.send_vkey(sel.btn_enter_key, window_id=SELECTORES_SAP.ventana.main)
        logger.info("Cierre de sesion SAP ejecutado (/nex)")
    except Exception as exc:
        logger.warning("No se pudo ejecutar el cierre forzado de sesion: %s", exc)
