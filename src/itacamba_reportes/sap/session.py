from __future__ import annotations

import logging
import os
import subprocess
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

    @staticmethod
    def kill_sap_processes() -> list[str]:
        # Cierra de forma forzada procesos colgados de SAP GUI y SAP Logon.
        killed: list[str] = []
        for proc in ("saplogon.exe", "sapgui.exe"):
            try:
                res = subprocess.run(
                    ["taskkill", "/F", "/IM", proc, "/T"],
                    capture_output=True,
                    text=True,
                )
                if res.returncode == 0:
                    killed.append(proc)
            except Exception:
                pass
        time.sleep(1.0)
        if killed:
            logger.info("Procesos SAP cerrados: %s", ", ".join(killed))
        return killed

    def close_sap(self, close_logon: bool = True) -> list[str]:
        # Cierra la sesion activa via /nex y opcionalmente cierra el proceso de SAP Logon.
        if self._session is not None:
            try:
                from itacamba_reportes.sap.actions.logout_action import execute_logout
                execute_logout(self)
                time.sleep(0.5)
            except Exception:
                pass
            finally:
                self._session = None
                self._connection = None

        if close_logon:
            return self.kill_sap_processes()
        return []

    @classmethod
    def close_all(cls, session_manager: SapSessionManager | None = None) -> list[str]:
        # Cierra cualquier sesion activa y termina los procesos de SAP en Windows.
        if session_manager is not None:
            return session_manager.close_sap(close_logon=True)
        return cls.kill_sap_processes()

    @staticmethod
    def is_saplogon_running() -> bool:
        # Comprueba si el ejecutable saplogon o sapgui esta activo en Windows.
        try:
            output = subprocess.check_output(
                ["tasklist", "/FI", "IMAGENAME eq sap*", "/FO", "CSV", "/NH"],
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="ignore",
            )
            return any("saplogon" in line.lower() or "sapgui" in line.lower() for line in output.splitlines())
        except Exception:
            return False

    @classmethod
    def launch_saplogon(cls, sap_path: str | None = None, wait_timeout: float = 30.0) -> None:
        # Inicia SAP Logon en segundo plano si no esta en ejecucion y espera al scripting engine.
        from itacamba_reportes.core.settings import EnvConfig

        executable = sap_path or os.getenv("SAP_LOGON_PATH") or os.getenv("SAP_URL") or EnvConfig.SAP_LOGON_PATH
        if not cls.is_saplogon_running():
            logger.info("Iniciando SAP Logon desde: %s", executable)
            subprocess.Popen([executable])
            time.sleep(3.0)

        import win32com.client
        start = time.perf_counter()
        while time.perf_counter() - start < wait_timeout:
            try:
                sap_gui_auto = win32com.client.GetObject("SAPGUI")
                if sap_gui_auto and sap_gui_auto.GetScriptingEngine:
                    logger.info("Scripting Engine de SAPGUI detectado y listo")
                    return
            except Exception:
                time.sleep(0.5)
        raise SapConnectionError(f"Tiempo de espera agotado ({wait_timeout}s) esperando a SAP Logon / SAPGUI")

    def open_connection(self, ambient: str | None = None, sync: bool = True) -> Any:
        # Abre una conexion hacia el ambiente SAP especificado por nombre exacto en SAP Logon.
        from itacamba_reportes.core.settings import EnvConfig

        raw_ambient = ambient or os.getenv("SAP_AMBIENT") or EnvConfig.SAP_AMBIENT
        target_ambient = str(raw_ambient).strip().strip('"').strip("'")
        logger.info("Abriendo conexion SAP al ambiente: %s", target_ambient)

        if self._application is None:
            import win32com.client
            sap_gui_auto = win32com.client.GetObject("SAPGUI")
            self._application = sap_gui_auto.GetScriptingEngine

        if self._application.Connections.Count == 0:
            self._connection = self._application.OpenConnection(target_ambient, sync)
        else:
            self._connection = self._application.Children(self.connection_index)

        time.sleep(1.0)
        self._session = self._connection.Children(self.session_index)
        logger.info("Sesion de SAP vinculada en conexion al ambiente '%s'", target_ambient)
        return self._session

    def ensure_connected_and_ready(
        self,
        ambient: str | None = None,
        auto_launch: bool = True,
        kill_existing: bool = False,
    ) -> Any:
        # Ciclo completo de inicializacion: mata si se pide, arranca, conecta, y maneja SSO o login clasico.
        from itacamba_reportes.core.settings import EnvConfig
        from itacamba_reportes.sap.actions.login_action import execute_login
        from itacamba_reportes.sap.selectors import SELECTORES_SAP

        if kill_existing:
            self.kill_sap_processes()

        if auto_launch and not self.is_saplogon_running():
            self.launch_saplogon()

        raw_ambient = ambient or EnvConfig.SAP_AMBIENT
        target_ambient = str(raw_ambient).strip().strip('"').strip("'")
        session = self.open_connection(target_ambient)
        self.maximize()

        time.sleep(1.0)
        wnd_title = ""
        try:
            wnd_title = session.ActiveWindow.Text or ""
        except Exception:
            pass

        # Si existe el campo de usuario de login, es obligatorio ingresar credenciales
        if self.element_exists(SELECTORES_SAP.login.usuario, timeout=5.0):
            logger.info("Detectada pantalla de login en SAP (campo de usuario visible). Ejecutando autenticacion...")
            execute_login(
                self,
                user=EnvConfig.SAP_USER,
                password=EnvConfig.SAP_PASSWORD,
                client=EnvConfig.SAP_MANDANTE,
            )
        elif "Easy Access" in wnd_title or "Menú" in wnd_title:
            logger.info("SSO activo detectado en SAP (%s). Sesion lista.", wnd_title)
        else:
            execute_login(
                self,
                user=EnvConfig.SAP_USER,
                password=EnvConfig.SAP_PASSWORD,
                client=EnvConfig.SAP_MANDANTE,
            )

        return session

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
            if self._application.Connections.Count == 0:
                from itacamba_reportes.core.settings import EnvConfig
                return self.open_connection(EnvConfig.SAP_AMBIENT)

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

    def element_exists(self, selector: str, timeout: float = 0.0, step: float = 0.5) -> bool:
        if timeout <= 0.0:
            try:
                return self.session.findById(selector) is not None
            except Exception:
                return False
        elapsed = 0.0
        while elapsed < timeout:
            try:
                if self.session.findById(selector) is not None:
                    return True
            except Exception:
                pass
            time.sleep(step)
            elapsed += step
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
