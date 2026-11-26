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
            )
        elif "Easy Access" in wnd_title or "Menú" in wnd_title:
            logger.info("SSO activo detectado en SAP (%s). Sesion lista.", wnd_title)
        else:
            execute_login(
                self,
                user=EnvConfig.SAP_USER,
                password=EnvConfig.SAP_PASSWORD,
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

    def _iter_gui_children(self, root: Any, max_depth: int = 3) -> list[Any]:
        collected: list[Any] = []
        queue: list[tuple[Any, int]] = [(root, 0)]
        while queue:
            node, depth = queue.pop(0)
            children = getattr(node, "Children", None)
            if children is None:
                continue
            try:
                child_list = list(children)
            except Exception:
                try:
                    count = int(getattr(children, "Count", 0))
                    child_list = [children(i) for i in range(count)]
                except Exception:
                    child_list = []
            for child in child_list:
                collected.append(child)
                if depth + 1 < max_depth:
                    queue.append((child, depth + 1))
        return collected

    def set_selection_field_by_label(
        self,
        labels: tuple[str, ...],
        value_low: str | int,
        value_high: str | int | None = None,
        field_hint_tokens: tuple[str, ...] = (),
    ) -> bool:
        import re

        try:
            usr_area = self.find_element("wnd[0]/usr", timeout=2.0)
        except Exception as exc:
            logger.debug("No se pudo inspeccionar wnd[0]/usr para ubicar campos: %s", exc)
            return False

        normalized_targets = {lbl.strip().rstrip(":").lower() for lbl in labels if lbl.strip()}
        children = self._iter_gui_children(usr_area, max_depth=3)

        matched_labels: list[Any] = []
        changeable_inputs: list[Any] = []
        for child in children:
            child_type = str(getattr(child, "Type", "") or "").lower()
            child_name = str(getattr(child, "Name", "") or "")
            child_name_upper = child_name.upper()
            if child_type == "guilabel" or "%-TEXT" in child_name_upper:
                lbl_text = str(getattr(child, "Text", "") or "").strip().rstrip(":").lower()
                if lbl_text in normalized_targets:
                    matched_labels.append(child)
                continue
            if any(tok in child_type for tok in ("label", "button", "check", "radio", "box")):
                continue
            if child_name and bool(getattr(child, "Changeable", True)):
                changeable_inputs.append(child)

        low_field = None
        high_field = None
        matched_label_text = ""

        for lbl in matched_labels:
            lbl_name_upper = str(getattr(lbl, "Name", "") or "").upper()
            matched_label_text = str(getattr(lbl, "Text", "") or "").strip()
            stem_match = re.search(r"%_([A-Z0-9_]+?)_%_APP_%", lbl_name_upper) or re.search(r"%_([A-Z0-9_]+)%", lbl_name_upper)
            if stem_match:
                stem = stem_match.group(1)
                low_field = next((c for c in changeable_inputs if str(getattr(c, "Name", "")).upper() == f"{stem}-LOW"), None)
                high_field = next((c for c in changeable_inputs if str(getattr(c, "Name", "")).upper() == f"{stem}-HIGH"), None)
                if low_field is not None:
                    break

            lbl_top = getattr(lbl, "Top", None)
            lbl_left = getattr(lbl, "Left", 0) or 0
            if lbl_top is not None:
                row_inputs = [
                    c for c in changeable_inputs
                    if getattr(c, "Top", None) is not None
                    and abs(int(c.Top) - int(lbl_top)) <= 4
                    and (getattr(c, "Left", 0) or 0) >= int(lbl_left)
                ]
                row_inputs.sort(key=lambda c: int(getattr(c, "Left", 0) or 0))
                low_field = next((c for c in row_inputs if str(getattr(c, "Name", "")).upper().endswith("-LOW")), None)
                if low_field is None:
                    low_field = next((c for c in row_inputs if not str(getattr(c, "Name", "")).upper().endswith("-HIGH")), None)
                high_field = next((c for c in row_inputs if str(getattr(c, "Name", "")).upper().endswith("-HIGH")), None)
                if low_field is not None:
                    break

        if low_field is None and field_hint_tokens:
            hints = tuple(tok.lower() for tok in field_hint_tokens)
            for inp in changeable_inputs:
                name_l = str(getattr(inp, "Name", "") or "").lower()
                if name_l.endswith("-low") and any(h in name_l for h in hints):
                    low_field = inp
                    high_name = str(getattr(inp, "Name", "")).upper()[:-4] + "-HIGH"
                    high_field = next((c for c in changeable_inputs if str(getattr(c, "Name", "")).upper() == high_name), None)
                    break

        if low_field is None:
            return False

        low_str = str(value_low).strip()
        low_field.text = low_str
        if high_field is not None:
            high_str = str(value_high).strip() if value_high is not None else ""
            if high_str and high_str != low_str:
                high_field.text = high_str
            elif str(getattr(high_field, "text", "") or "").strip():
                high_field.text = ""

        logger.info(
            "Campo SAP '%s' (%s) actualizado dinámicamente a: %s%s",
            matched_label_text or ",".join(labels),
            getattr(low_field, "Name", "campo"),
            low_str,
            f" .. {value_high}" if (value_high and str(value_high).strip() != low_str and high_field is not None) else "",
        )
        return True

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

    def _is_on_easy_access(self) -> bool:
        try:
            tx = str(getattr(self.session.Info, "Transaction", "") or "").strip().upper()
            if tx == "SESSION_MANAGER":
                return True
            title = str(getattr(self.session.ActiveWindow, "Text", "") or "")
            return "Easy Access" in title
        except Exception:
            return False

    def _is_logoff_popup(self) -> bool:
        try:
            title = str(getattr(self.session.ActiveWindow, "Text", "") or "").lower()
            return "salir del sistema" in title or "log off" in title
        except Exception:
            return False

    def return_to_main_menu(self) -> None:
        from itacamba_reportes.sap.selectors import SELECTORES_SAP

        logger.info("Retornando al menu principal de SAP (Easy Access)...")
        # 1. Resolver ventanas modales residuales sin confirmar un cierre de sesion
        for _ in range(3):
            try:
                active_wnd = getattr(self.session.ActiveWindow, "Name", "")
                if not active_wnd or active_wnd == "wnd[0]":
                    break
                if self._is_logoff_popup() and self.element_exists("wnd[1]/usr/btnSPOP-OPTION2", timeout=0.3):
                    self.press_button("wnd[1]/usr/btnSPOP-OPTION2")
                    time.sleep(0.4)
                    continue
                if self.element_exists("wnd[1]/usr/btnSPOP-OPTION1", timeout=0.3):
                    self.press_button("wnd[1]/usr/btnSPOP-OPTION1")
                    time.sleep(0.4)
                    continue
                if self.element_exists(f"{active_wnd}/tbar[0]/btn[12]", timeout=0.3):
                    self.press_button(f"{active_wnd}/tbar[0]/btn[12]")
                    time.sleep(0.4)
                    continue
            except Exception:
                pass

        # 2. Pulsar boton atras (btn[15]) solo mientras no estemos en Easy Access
        for _ in range(4):
            if self._is_on_easy_access():
                break
            try:
                self.press_button(SELECTORES_SAP.barra.btn_back)
                time.sleep(0.4)
                if self.element_exists("wnd[1]/usr/btnSPOP-OPTION1", timeout=0.4):
                    if self._is_logoff_popup() and self.element_exists("wnd[1]/usr/btnSPOP-OPTION2", timeout=0.2):
                        self.press_button("wnd[1]/usr/btnSPOP-OPTION2")
                        break
                    self.press_button("wnd[1]/usr/btnSPOP-OPTION1")
                    time.sleep(0.4)
            except Exception:
                break

        # 3. Enviar '/n' en okcode para garantizar retorno limpio a Easy Access sin /nex
        if not self._is_on_easy_access():
            try:
                if self.element_exists(SELECTORES_SAP.barra.okcode, timeout=2.0):
                    self.set_text(SELECTORES_SAP.barra.okcode, "/n")
                    self.send_vkey(SELECTORES_SAP.barra.btn_enter_key, window_id=SELECTORES_SAP.ventana.main)
                    time.sleep(0.5)
            except Exception:
                pass

        self.maximize()
        logger.info("SAP en menu principal listo para la siguiente transaccion")
