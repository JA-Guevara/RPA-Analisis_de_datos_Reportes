from __future__ import annotations

import logging
import os
from typing import Any

from itacamba_reportes.sap.exceptions import SapLoginError
from itacamba_reportes.sap.selectors import (
    SELECTORES_SAP,
    SelectoresLogin,
)
from itacamba_reportes.sap.session import SapSessionManager

logger = logging.getLogger(__name__)


def execute_login(
    session_manager: SapSessionManager,
    user: str | None = None,
    password: str | None = None,
    client: str | None = None,
    lang: str = "ES",
    selectors: SelectoresLogin | None = None,
) -> None:
    sel = selectors or SELECTORES_SAP.login
    from itacamba_reportes.core.settings import EnvConfig
    usr = user or os.getenv("SAP_USER") or os.getenv("SAP_USUARIO") or EnvConfig.SAP_USER
    pwd = password or os.getenv("SAP_PASSWORD") or EnvConfig.SAP_PASSWORD
    mandante = client or os.getenv("SAP_MANDANTE") or EnvConfig.SAP_MANDANTE or "300"

    if not usr or not pwd:
        raise SapLoginError("Credenciales de SAP no proporcionadas en argumentos ni en variables de entorno (SAP_USER, SAP_PASSWORD)")

    session_manager.maximize(SELECTORES_SAP.ventana.main)

    # Paso 1: Verificacion de pantalla de autenticacion
    if session_manager.element_exists(sel.usuario):
        logger.info("Ingresando credenciales de usuario SAP: %s", usr)
        session_manager.set_text(sel.usuario, usr)
        session_manager.set_text(sel.password, pwd)

        if session_manager.element_exists(sel.mandante) and mandante:
            session_manager.set_text(sel.mandante, mandante)

        if session_manager.element_exists(sel.lenguaje) and lang:
            session_manager.set_text(sel.lenguaje, lang)

        # Paso 2: Envio de credenciales
        session_manager.send_vkey(SELECTORES_SAP.barra.btn_enter_key, window_id=SELECTORES_SAP.ventana.main)

        # Paso 3: Gestion de concurrencia y sesiones previas
        session_manager.handle_multilogon_if_present(selectors=sel)

        # Paso 4: Validacion de mensajes de error en barra de estado
        msg_type, msg_text = session_manager.get_status_message()
        if msg_type == "E":
            raise SapLoginError(f"Error de login en SAP: {msg_text}")

        logger.info("Autenticacion en SAP completada")
    else:
        logger.info("Pantalla de login no detectada, sesion ya activa")
