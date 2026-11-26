from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SECURITY_TITLES = ("seguridad sap gui", "sap gui security")
_OVERWRITE_TITLES = ("confirmar guardar como", "confirm save as")
_REMEMBER_TOKENS = ("recordar", "remember")
_ALLOW_TOKENS = ("permitir", "allow", "si", "sí", "yes")
_OVERWRITE_ALLOW_TOKENS = ("si", "sí", "yes", "reemplazar", "replace")


def _clean_caption(text: str) -> str:
    return (text or "").replace("&", "").strip().lower()


def _has_excel_window() -> bool:
    try:
        import win32gui
    except ImportError:
        return False

    found = {"value": False}

    def _enum_cb(hwnd: int, _extra: Any) -> bool:
        try:
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetClassName(hwnd) == "XLMAIN":
                found["value"] = True
                return False
        except Exception:
            pass
        return True

    try:
        win32gui.EnumWindows(_enum_cb, None)
    except Exception:
        pass
    return found["value"]


def dismiss_sap_security_popup(remember_decision: bool = True) -> int:
    try:
        import win32con
        import win32gui
    except ImportError:
        return 0

    handled = 0
    candidate_windows: list[tuple[int, str, str]] = []

    def _enum_top(hwnd: int, _extra: Any) -> bool:
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return True
            title = (win32gui.GetWindowText(hwnd) or "").strip()
            title_l = title.lower()
            if any(tok in title_l for tok in _SECURITY_TITLES):
                candidate_windows.append((hwnd, title, "security"))
            elif any(tok in title_l for tok in _OVERWRITE_TITLES):
                candidate_windows.append((hwnd, title, "overwrite"))
        except Exception:
            pass
        return True

    try:
        win32gui.EnumWindows(_enum_top, None)
    except Exception as exc:
        logger.debug("No se pudieron enumerar ventanas Win32: %s", exc)
        return 0

    for parent_hwnd, title, kind in candidate_windows:
        children: list[int] = []

        def _enum_child(child_hwnd: int, _extra: Any) -> bool:
            children.append(child_hwnd)
            return True

        try:
            win32gui.EnumChildWindows(parent_hwnd, _enum_child, None)
        except Exception:
            continue

        remember_hwnd: int | None = None
        allow_hwnd: int | None = None
        allow_caption = ""
        allowed_words = _ALLOW_TOKENS if kind == "security" else _OVERWRITE_ALLOW_TOKENS

        for ch in children:
            try:
                if not (win32gui.IsWindowVisible(ch) and win32gui.IsWindowEnabled(ch)):
                    continue
                cls_name = (win32gui.GetClassName(ch) or "").lower()
                if "button" not in cls_name:
                    continue
                caption_raw = win32gui.GetWindowText(ch) or ""
                caption = _clean_caption(caption_raw)
                if not caption:
                    continue
                if kind == "security" and any(tok in caption for tok in _REMEMBER_TOKENS):
                    remember_hwnd = ch
                elif caption in allowed_words or any(caption.startswith(w) for w in allowed_words):
                    if allow_hwnd is None:
                        allow_hwnd = ch
                        allow_caption = caption_raw.replace("&", "").strip()
            except Exception:
                continue

        if allow_hwnd is None:
            continue

        try:
            try:
                win32gui.SetForegroundWindow(parent_hwnd)
                time.sleep(0.05)
            except Exception:
                pass

            if remember_decision and remember_hwnd is not None:
                try:
                    checked = win32gui.SendMessage(remember_hwnd, win32con.BM_GETCHECK, 0, 0)
                    if checked != win32con.BST_CHECKED:
                        win32gui.SendMessage(remember_hwnd, win32con.BM_CLICK, 0, 0)
                        time.sleep(0.05)
                except Exception:
                    pass

            win32gui.PostMessage(allow_hwnd, win32con.BM_CLICK, 0, 0)
            handled += 1
            logger.info("Popup Win32 '%s' aceptado automáticamente (%s).", title, allow_caption or "Permitir")
        except Exception as exc:
            logger.debug("No se pudo confirmar popup '%s': %s", title, exc)

    return handled


class SapSecurityWatchdog:
    def __init__(self, remember_decision: bool = True, poll_interval: float = 0.35) -> None:
        self.remember_decision = remember_decision
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self.dismissed_count = 0

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.dismissed_count += dismiss_sap_security_popup(remember_decision=self.remember_decision)
            except Exception:
                pass
            self._stop_event.wait(self.poll_interval)

    def __enter__(self) -> SapSecurityWatchdog:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="SapSecurityWatchdog")
        self._thread.start()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.5)


def _matches_target(candidate_name: str, target_names: set[str], target_stems: set[str]) -> bool:
    if not candidate_name:
        return False
    p = Path(candidate_name)
    return p.name.lower() in target_names or p.stem.lower() in target_stems


def _close_matching_excel_once(target_names: set[str], target_stems: set[str]) -> int:
    try:
        import pythoncom
        import win32com.client
    except ImportError:
        return 0

    closed = 0
    touched_apps: list[Any] = []
    seen_app_ids: set[int] = set()
    com_initialized = False

    try:
        pythoncom.CoInitialize()
        com_initialized = True
    except Exception:
        pass

    try:
        # 1. Revisar Running Object Table (cubre multiples instancias de Excel)
        try:
            rot = pythoncom.GetRunningObjectTable()
            ctx = pythoncom.CreateBindCtx(0)
            enum = rot.EnumRunning()
            while True:
                monikers = enum.Next(1)
                if not monikers:
                    break
                moniker = monikers[0]
                try:
                    disp_name = moniker.GetDisplayName(ctx, None) or ""
                except Exception:
                    continue
                if not _matches_target(disp_name, target_names, target_stems):
                    continue
                try:
                    obj = rot.GetObject(moniker)
                    wb = win32com.client.Dispatch(obj.QueryInterface(pythoncom.IID_IDispatch))
                    app = getattr(wb, "Application", None)
                    wb.Close(SaveChanges=False)
                    closed += 1
                    logger.info("Libro Excel abierto por SAP cerrado automáticamente: %s", disp_name)
                    if app is not None and id(app) not in seen_app_ids:
                        seen_app_ids.add(id(app))
                        touched_apps.append(app)
                except Exception as exc:
                    logger.debug("No se pudo cerrar workbook ROT '%s': %s", disp_name, exc)
        except Exception:
            pass

        # 2. Revisar instancia activa primaria de Excel
        try:
            app = win32com.client.GetActiveObject("Excel.Application")
            for wb in list(getattr(app, "Workbooks", ()) or ()):
                wb_name = str(getattr(wb, "Name", "") or "")
                wb_full = str(getattr(wb, "FullName", "") or "")
                if _matches_target(wb_name, target_names, target_stems) or _matches_target(wb_full, target_names, target_stems):
                    try:
                        wb.Close(SaveChanges=False)
                        closed += 1
                        logger.info("Libro Excel cerrado automáticamente: %s", wb_name or wb_full)
                        if id(app) not in seen_app_ids:
                            seen_app_ids.add(id(app))
                            touched_apps.append(app)
                    except Exception as exc:
                        logger.debug("No se pudo cerrar workbook activo '%s': %s", wb_name, exc)
        except Exception:
            pass

        for app in touched_apps:
            try:
                workbooks = getattr(app, "Workbooks", None)
                if workbooks is not None:
                    wb_count = getattr(workbooks, "Count", None)
                    remaining = int(wb_count) if wb_count is not None else len(workbooks)
                    if remaining == 0:
                        app.DisplayAlerts = False
                        app.Quit()
                        logger.info("Instancia de Microsoft Excel sin libros cerrándose limpiamente.")
            except Exception:
                pass
    finally:
        if com_initialized:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass

    return closed


def close_excel_workbook_by_name(
    filenames: list[str] | tuple[str, ...],
    wait_timeout: float = 3.0,
) -> int:
    target_names = {Path(name).name.lower() for name in filenames if name}
    target_stems = {Path(name).stem.lower() for name in filenames if name}
    if not target_names:
        return 0

    total_closed = 0
    elapsed = 0.0
    step = 0.5
    max_wait = max(0.0, float(wait_timeout))

    while True:
        closed_now = _close_matching_excel_once(target_names, target_stems)
        total_closed += closed_now
        if total_closed > 0:
            return total_closed
        if elapsed >= max_wait:
            return total_closed
        if not _has_excel_window() and elapsed >= min(max_wait, 1.5):
            return total_closed
        time.sleep(step)
        elapsed += step
