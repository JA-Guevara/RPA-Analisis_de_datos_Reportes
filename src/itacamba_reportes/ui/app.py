from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger("itacamba_reportes.ui")


def launch_gui(debug: bool = False) -> int:
    # Inicia la interfaz gráfica de usuario (GUI) en una ventana nativa de escritorio.
    try:
        import webview
    except ImportError:
        logger.error("El paquete 'pywebview' no está instalado en el entorno virtual.")
        print("\n[ERROR] El paquete 'pywebview' no está instalado.")
        print("Ejecuta en tu terminal: pip install pywebview\n")
        return 1

    from itacamba_reportes.ui.bridge import BotBridge

    html_path = Path(__file__).resolve().parent / "web" / "index.html"
    if not html_path.exists():
        logger.error("No se encontró el archivo de interfaz: %s", html_path)
        print(f"\n[ERROR] Archivo no encontrado: {html_path}\n")
        return 1

    bridge = BotBridge()

    logger.info("Iniciando ventana nativa de escritorio con PyWebView...")
    window = webview.create_window(
        title="Itacamba Cemento S.A. · Consola de Control de Reportes & BI v3.8",
        url=str(html_path),
        js_api=bridge,
        width=1340,
        height=880,
        min_size=(1024, 700),
        resizable=True,
    )

    webview.start(debug=debug)
    return 0


if __name__ == "__main__":
    sys.exit(launch_gui())
