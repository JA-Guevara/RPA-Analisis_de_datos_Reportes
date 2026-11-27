from __future__ import annotations

import logging
import os
import time
from typing import Any

from itacamba_reportes.core.settings import EnvConfig
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
    lang: str | None = None,
    selectors: SelectoresLogin | None = None,
) -> None:
    sel = selectors or SELECTORES_SAP.login
    usr = user or os.getenv("SAP_USER") or os.getenv("SAP_USUARIO") or EnvConfig.SAP_USER
    pwd = password or os.getenv("SAP_PASSWORD") or EnvConfig.SAP_PASSWORD
    mandante = client or os.getenv("SAP_MANDANTE")
    idioma = lang or os.getenv("SAP_IDIOMA")

    if not usr or not pwd:
        raise SapLoginError("Credenciales de SAP no proporcionadas en argumentos ni en variables de entorno (SAP_USER, SAP_PASSWORD)")

    session_manager.maximize(SELECTORES_SAP.ventana.main)

    # Paso 1: Verificacion de pantalla de autenticacion con espera
    if session_manager.element_exists(sel.usuario, timeout=5.0):
        logger.info("Ingresando credenciales de usuario SAP: %s", usr)

        if mandante and session_manager.element_exists(sel.mandante, timeout=0.5):
            session_manager.set_text(sel.mandante, str(mandante))

        session_manager.set_text(sel.usuario, str(usr))
        session_manager.set_text(sel.password, str(pwd))

        if idioma and session_manager.element_exists(sel.lenguaje, timeout=0.5):
            session_manager.set_text(sel.lenguaje, str(idioma))

        # Paso 2: Envio de credenciales (Enter)
        session_manager.send_vkey(SELECTORES_SAP.barra.btn_enter_key, window_id=SELECTORES_SAP.ventana.main)
        time.sleep(1.0)

        # Paso 3: Gestion de concurrencia y sesiones previas (Multi-Logon)
        session_manager.handle_multilogon_if_present(selectors=sel)

        # Paso 4: Validar modal informativo vs cambio obligatorio de clave / bloqueo
        try:
            active_wnd = session_manager.session.ActiveWindow
            active_name = getattr(active_wnd, "Name", "")
            active_text = str(getattr(active_wnd, "Text", "") or "").lower()
            if active_name != "wnd[0]":
                if any(k in active_text for k in ("clave", "contrase", "password", "caduc", "expir")):
                    raise SapLoginError(
                        f"[AUTH_SAP] SAP requiere cambio manual o renovación de contraseña ({active_wnd.Text})."
                    )
                session_manager.session.findById(f"{active_name}/tbar[0]/btn[0]").press()
                time.sleep(0.5)
        except SapLoginError:
            raise
        except Exception:
            pass

        # Paso 5: Validacion de mensajes de error en barra de estado y sesión autenticada
        msg_type, msg_text = session_manager.get_status_message()
        if msg_type in ("E", "A"):
            txt_l = str(msg_text or "").lower()
            if any(k in txt_l for k in ("clave", "password", "bloquead", "locked", "caduc", "expir", "logon", "authorization", "no autorizado")):
                raise SapLoginError(f"[AUTH_SAP] Error de autenticación en SAP: {msg_text}")
            raise SapLoginError(f"Error de login en SAP: {msg_text}")

        if session_manager.element_exists(sel.usuario, timeout=0.5):
            raise SapLoginError("[AUTH_SAP] El usuario sigue en la pantalla de login de SAP tras enviar credenciales.")

        logger.info("Autenticacion en SAP completada exitosamente")
    else:
        logger.info("Pantalla de login no detectada, sesion ya activa")
