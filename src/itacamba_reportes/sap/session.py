from __future__ import annotations

import logging
import time
from typing import Any

from itacamba_reportes.sap.exceptions import (
    SapAutomationError,
    SapConnectionError,
    SapElementNotFoundError,
)
from itacamba_reportes.sap.selectors import (
    BTN_ENTER_KEY,
    POPUP_MULTILOGON_CONFIRM,
    POPUP_MULTILOGON_OPT2,
    STATUS_BAR,
    WND_MAIN,
    WND_MODAL_1,
)

logger = logging.getLogger(__name__)


class SapSessionManager:
    def __init__(self, connection_index: int = 0, session_index: int = 0):
        self.connection_index = connection_index
        self.session_index = session_index
        self._application: Any = None
        self._connection: Any = None
        self._session: Any = None

    def connect(self) -> Any:
        try:
            import win32com.client
        except ImportError as exc:
            raise SapConnectionError("pywin32 no esta disponible en el entorno virtual") from exc

        try:
            sap_gui_auto = win32com.client.GetObject("SAPGUI")
            self._application = sap_gui_auto.GetScriptingEngine
        except Exception as exc:
            raise SapConnectionError(
                "No se pudo conectar al motor SAP GUI Scripting. "
                "Asegurese de que SAP Logon este abierto y que el scripting este habilitado."
            ) from exc

        try:
            self._connection = self._application.Children(self.connection_index)
            self._session = self._connection.Children(self.session_index)
            logger.info("Sesion de SAP GUI vinculada exitosamente")
            return self._session
        except Exception as exc:
            raise SapConnectionError("Fallo al obtener la sesion activa de SAP GUI") from exc

    @property
    def session(self) -> Any:
        if self._session is None:
            return self.connect()
        return self._session

    def maximize(self, window_id: str = WND_MAIN) -> None:
        try:
            self.session.findById(window_id).maximize()
        except Exception:
            pass

    def find_element(self, selector: str, timeout: float = 10.0, step: float = 0.5) -> Any:
        elapsed = 0.0
        while elapsed < timeout:
            try:
                el = self.session.findById(selector)
                if el is not None:
                    return el
            except Exception:
                pass
            time.sleep(step)
            elapsed += step
        raise SapElementNotFoundError(f"Elemento SAP no encontrado tras {timeout:.1f}s: {selector}")

    def element_exists(self, selector: str) -> bool:
        try:
            return self.session.findById(selector) is not None
        except Exception:
            return False

    def set_text(self, selector: str, text_value: str, timeout: float = 5.0) -> None:
        el = self.find_element(selector, timeout=timeout)
        el.text = str(text_value)

    def press_button(self, selector: str, timeout: float = 5.0) -> None:
        el = self.find_element(selector, timeout=timeout)
        el.press()

    def send_vkey(self, key_code: int = BTN_ENTER_KEY, window_id: str = WND_MAIN) -> None:
        el = self.find_element(window_id, timeout=5.0)
        el.sendVKey(key_code)

    def get_status_message(self) -> tuple[str, str]:
        try:
            sbar = self.session.findById(STATUS_BAR)
            return str(sbar.messageType), str(sbar.text)
        except Exception:
            return "", ""

    def handle_multilogon_if_present(self, selectors: Any = None) -> bool:
        from itacamba_reportes.sap.selectors import SELECTORES_SAP

        sel = selectors or SELECTORES_SAP.login
        if self.element_exists(sel.multilogon_opt2):
            logger.info("Detectado popup de Multi-Logon, seleccionando continuar...")
            self.session.findById(sel.multilogon_opt2).select()
            self.send_vkey(SELECTORES_SAP.barra.btn_enter_key, window_id=SELECTORES_SAP.ventana.modal_1)
            return True
        return False
