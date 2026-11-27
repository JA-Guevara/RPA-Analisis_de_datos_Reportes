from __future__ import annotations

import html
import json
import logging
import os
import socket
import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

from itacamba_reportes.core.settings import EnvConfig

logger = logging.getLogger(__name__)


def parse_recipient_list(value: str | None) -> list[str]:
    if not value:
        return []
    raw = value.replace(";", ",")
    return [item.strip() for item in raw.split(",") if item.strip()]


def classify_alert_category(error_message: str) -> tuple[str, str]:
    msg = (error_message or "").lower()
    if "[auth_sap]" in msg or any(k in msg for k in (
        "saplogon", "credencial", "password", "clave", "bloquead", "locked",
        "caduc", "expir", "sso", "sap_user", "sap_password", "sap_ambient",
        "no se pudo autenticar", "logon no longer possible",
    )):
        return (
            "Autenticación / Sesión SAP vencida",
            "Verificar credenciales SAP (SAP_USER / SAP_PASSWORD), desbloquear o renovar clave en SAP GUI y confirmar sesión SSO en el equipo.",
        )
    if any(k in msg for k in ("vpn", "sql server", "pyodbc", "odbc", "connectionerror", "08001", "login failed for user")):
        return (
            "Conectividad SQL Server / VPN",
            "Confirmar que la VPN corporativa esté conectada en el equipo y probar la conexión SQL desde Configuración (.env).",
        )
    if any(k in msg for k in (
        "winerror 5", "acceso denegado", "onedrive", "path_insumos", "path_reportes",
        "filenotfounderror", "no se encontró", "permiso de escritura",
    )):
        return (
            "OneDrive / Rutas de archivos o sesión Microsoft",
            "Verificar que OneDrive esté iniciado y sincronizando en este equipo, y validar PATH_INSUMOS_FIJOS, PATH_INSUMOS_DINAMICOS y PATH_REPORTES_SALIDA en .env.",
        )
    if any(k in msg for k in ("columna", "hoja", "sheetnotfound", "missingcolumns", "sin filas válidas")):
        return (
            "Validación de estructura Excel",
            "Revisar el archivo fuente (hojas y encabezados requeridos); la base de datos previa fue protegida y no se sobrescribió con datos vacíos.",
        )
    return (
        "Error operativo del pipeline",
        "Revisar el detalle del paso fallido en la pestaña 'Registro de ejecución' o en storage/logs.",
    )


class WebhookMailService:
    # Cliente HTTP compatible con el webhook Power Automate usado en Bot Itacamba v3.0.

    def __init__(self, url: str, key: str, timeout: int = 30, attempts: int = 3) -> None:
        clean_url = (url or "").strip()
        clean_key = (key or "").strip()
        if not clean_url or not clean_key:
            raise ValueError("Faltan MAIL_WEBHOOK_URL o MAIL_WEBHOOK_KEY en .env")
        self._url = clean_url
        self._key = clean_key
        self._timeout = max(5, int(timeout or 30))
        self._attempts = max(1, int(attempts or 3))

    def enviar(
        self,
        asunto: str,
        cuerpo: str,
        to: list[str],
        cc: list[str] | None = None,
        es_html: bool = False,
    ) -> bool:
        recipients = [r.strip() for r in to if r and r.strip()]
        if not recipients:
            logger.warning("Correo '%s' sin destinatarios; no se envía.", asunto)
            return False

        cc_list = [c.strip() for c in (cc or []) if c and c.strip()]
        payload = {
            "destinatarios": ";".join(recipients),
            "copia": ";".join(cc_list),
            "asunto": asunto,
            "cuerpo_html": cuerpo if es_html else f"<pre>{html.escape(cuerpo)}</pre>",
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        for attempt in range(1, self._attempts + 1):
            req = urllib.request.Request(
                self._url,
                data=data,
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "x-api-key": self._key,
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    status = getattr(resp, "status", 200)
                    if 200 <= status < 300:
                        logger.info("Alerta de correo enviada vía Webhook: %s", asunto)
                        return True
                    logger.warning("Webhook intento %d/%d devolvió HTTP %s", attempt, self._attempts, status)
            except urllib.error.HTTPError as exc:
                if exc.code in (400, 401, 403):
                    logger.error(
                        "Webhook rechazó '%s' (HTTP %s): verifica MAIL_WEBHOOK_URL, MAIL_WEBHOOK_KEY o destinatarios.",
                        asunto,
                        exc.code,
                    )
                    return False
                logger.warning("Webhook intento %d/%d falló con HTTP %s", attempt, self._attempts, exc.code)
            except Exception as exc:
                logger.warning("Webhook intento %d/%d sin respuesta: %s", attempt, self._attempts, exc)

            if attempt < self._attempts:
                time.sleep(min(8, 2 ** attempt))

        logger.error("No se pudo enviar correo '%s' tras %d intentos.", asunto, self._attempts)
        return False


def build_error_email_html(
    stage: str,
    error_message: str,
    category: str,
    suggested_action: str,
    profile_name: str | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    host_name = socket.gethostname()
    user_name = os.getenv("USERNAME") or os.getenv("USER") or "N/D"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows_html = [
        ("Bot", "Itacamba Reportes &amp; BI"),
        ("Equipo / Usuario", f"{html.escape(host_name)} ({html.escape(user_name)})"),
        ("Fecha y Hora", html.escape(now_str)),
        ("Tipo de Alerta", html.escape(category)),
        ("Etapa / Paso", html.escape(stage)),
    ]
    if profile_name:
        rows_html.append(("Perfil / Rutina", html.escape(profile_name)))
    if extra:
        for k, v in extra.items():
            if v not in (None, ""):
                rows_html.append((html.escape(str(k)), html.escape(str(v))))

    tr_block = "".join(
        f"<tr><td style='padding:6px 10px;border:1px solid #d9e2ec;font-weight:600;background:#f8fafc;width:190px'>{k}</td>"
        f"<td style='padding:6px 10px;border:1px solid #d9e2ec'>{v}</td></tr>"
        for k, v in rows_html
    )

    return (
        "<div style='font-family:Segoe UI,Arial,sans-serif;color:#1e293b;max-width:680px'>"
        "<h2 style='color:#b91c1c;margin:0 0 12px'>Alerta Operativa — Bot Itacamba Reportes</h2>"
        f"<table style='border-collapse:collapse;width:100%;font-size:13px;margin-bottom:14px'>{tr_block}</table>"
        "<div style='background:#fef2f2;border-left:4px solid #dc2626;padding:10px 12px;margin-bottom:14px'>"
        "<div style='font-weight:700;color:#991b1b;margin-bottom:4px'>Detalle del error</div>"
        f"<pre style='margin:0;white-space:pre-wrap;font-family:Consolas,monospace;font-size:12px'>{html.escape(error_message)}</pre>"
        "</div>"
        "<div style='background:#eff6ff;border-left:4px solid #2563eb;padding:10px 12px'>"
        "<div style='font-weight:700;color:#1e40af;margin-bottom:4px'>Acción sugerida</div>"
        f"<div style='font-size:13px'>{html.escape(suggested_action)}</div>"
        "</div>"
        "</div>"
    )


def notify_error_alert_from_env(
    stage: str,
    error_message: str,
    profile_name: str | None = None,
    extra: dict[str, Any] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    url = (os.getenv("MAIL_WEBHOOK_URL") or EnvConfig.MAIL_WEBHOOK_URL or "").strip()
    key = (os.getenv("MAIL_WEBHOOK_KEY") or EnvConfig.MAIL_WEBHOOK_KEY or "").strip()
    if not url or not key:
        return {"sent": False, "reason": "webhook_not_configured"}

    alert_enabled = str(os.getenv("MAIL_ALERT_ON_ERROR") or EnvConfig.MAIL_ALERT_ON_ERROR or "yes").strip().lower()
    if not force and alert_enabled in {"0", "false", "no", "off"}:
        return {"sent": False, "reason": "alerts_disabled"}

    to_list = parse_recipient_list(
        os.getenv("MAIL_SOPORTE")
        or EnvConfig.MAIL_SOPORTE
        or os.getenv("MAIL_GENERAL")
        or EnvConfig.MAIL_GENERAL
    )
    cc_list = parse_recipient_list(
        os.getenv("MAIL_COPIA_SOPORTE")
        or EnvConfig.MAIL_COPIA_SOPORTE
        or os.getenv("MAIL_COPIA_GENERAL")
        or EnvConfig.MAIL_COPIA_GENERAL
    )
    if not to_list:
        return {"sent": False, "reason": "no_recipients"}

    timeout = int(os.getenv("MAIL_WEBHOOK_TIMEOUT") or EnvConfig.MAIL_WEBHOOK_TIMEOUT or 30)
    category, suggested_action = classify_alert_category(error_message)
    asunto = f"[ALERTA BOT REPORTES] {category} — {stage}"
    cuerpo_html = build_error_email_html(
        stage=stage,
        error_message=error_message,
        category=category,
        suggested_action=suggested_action,
        profile_name=profile_name,
        extra=extra,
    )

    try:
        service = WebhookMailService(url=url, key=key, timeout=timeout)
        ok = service.enviar(asunto=asunto, cuerpo=cuerpo_html, to=to_list, cc=cc_list, es_html=True)
        return {"sent": ok, "to": to_list, "cc": cc_list, "category": category}
    except Exception as exc:
        logger.warning("No se pudo despachar alerta de correo vía Webhook: %s", exc)
        return {"sent": False, "reason": str(exc)}
