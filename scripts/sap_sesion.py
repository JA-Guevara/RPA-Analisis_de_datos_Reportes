"""Sesion SAP por GUI Scripting, sin imagenes y sin grabador.

El grabador de SAP GUI solo graba DENTRO de una sesion: no ve SAP Logon ni la
pantalla de login. Este script cubre esa parte con la API de scripting:

  entradas  Lista las entradas de SAP Logon con su nombre EXACTO, leyendo
            SAPUILandscape.xml. No abre SAP.
  listar    Se engancha a un SAP ya abierto (entraste a mano) y muestra cada
            conexion: nombre exacto, sistema, mandante, usuario, idioma,
            servidor y transaccion. Solo lectura.
  campos    Muestra los IDs de la ventana activa de una sesion abierta: lo que
            el grabador no captura (por ejemplo, la pantalla de login).
            Las claves salen como ***.
  abrir     Abre la entrada por nombre, inicia sesion (SSO o usuario/clave),
            verifica sistema y mandante, muestra la info y cierra con /nex.
            No entra a ninguna transaccion.

Ejemplos (PowerShell, desde la raiz del proyecto):
  python scripts/sap_sesion.py entradas
  python scripts/sap_sesion.py listar
  python scripts/sap_sesion.py abrir --entrada "NOMBRE EXACTO" --sin-login
  python scripts/sap_sesion.py campos
  python scripts/sap_sesion.py abrir --entrada "NOMBRE EXACTO" --sistema E05 --mandante NNN --usuario USUARIO

La clave NUNCA va por linea de comandos: se pide por teclado (no se ve al
escribirla) o se toma de la variable de entorno SAP_PASSWORD. Nunca se imprime.

Requiere: pip install pywin32
"""

from __future__ import annotations

import argparse
import getpass
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

try:  # el .env del proyecto puede traer SAP_ENTRADA, SAP_SISTEMA, etc.
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass

ID_USUARIO = "wnd[0]/usr/txtRSYST-BNAME"
ID_CLAVE = "wnd[0]/usr/pwdRSYST-BCODE"
ID_MANDANTE = "wnd[0]/usr/txtRSYST-MANDT"
ID_IDIOMA = "wnd[0]/usr/txtRSYST-LANGU"
ID_OKCODE = "wnd[0]/tbar[0]/okcd"
ID_SBAR = "wnd[0]/sbar"
ID_MULTILOGON_CONTINUAR = "wnd[1]/usr/radMULTI_LOGON_OPT2"
ID_CAMBIO_CLAVE = "wnd[1]/usr/pwdRSYST-NCODE"

SAPLOGON_RUTAS = (
    r"C:\Program Files (x86)\SAP\FrontEnd\SAPgui\saplogon.exe",
    r"C:\Program Files\SAP\FrontEnd\SAPgui\saplogon.exe",
)


# ── utilidades ────────────────────────────────────────────────────────

def _ok(msg: str) -> None:
    print(f"  [  OK  ] {msg}")


def _aviso(msg: str) -> None:
    print(f"  [ AVISO] {msg}")


def _falla(msg: str, sugerencia: str | None = None) -> int:
    print(f"  [ FALLA] {msg}")
    if sugerencia:
        print(f"           -> {sugerencia}")
    return 1


def _win32():
    try:
        import win32com.client  # noqa: PLC0415
    except ImportError:
        sys.exit("Falta pywin32. Instalar en el venv: python -m pip install pywin32")
    return win32com.client


def _motor(timeout: float = 0.0):
    """Scripting engine de SAP GUI. Requiere SAP Logon abierto."""
    client = _win32()
    limite = time.time() + timeout
    while True:
        try:
            return client.GetObject("SAPGUI").GetScriptingEngine
        except Exception as exc:
            if time.time() >= limite:
                raise RuntimeError(
                    "No se pudo enganchar a SAP GUI: SAP Logon no esta abierto o el "
                    "scripting esta deshabilitado en el cliente "
                    "(SAP GUI > Opciones > Accesibilidad y scripting > Scripting).",
                ) from exc
            time.sleep(0.5)


def _motor_arrancando_saplogon(ruta: str | None):
    try:
        return _motor()
    except RuntimeError:
        pass
    candidatos = [ruta] if ruta else [os.getenv("SAP_LOGON_EXE"), *SAPLOGON_RUTAS]
    exe = next((c for c in candidatos if c and Path(c).exists()), None)
    if not exe:
        raise RuntimeError("No se encontro saplogon.exe. Indica la ruta con --saplogon.")
    print(f"  Abriendo SAP Logon: {exe}")
    subprocess.Popen([exe])
    return _motor(timeout=30)


def _buscar(session, id_: str):
    try:
        return session.findById(id_)
    except Exception:
        return None


def _esperar(session, timeout: float = 30.0) -> None:
    limite = time.time() + timeout
    while time.time() < limite:
        try:
            if not session.Busy:
                return
        except Exception:
            return
        time.sleep(0.2)


def _hijos(componente) -> list:
    try:
        coleccion = componente.Children
        return [coleccion(i) for i in range(coleccion.Count)]
    except Exception:
        return []


def _info(session) -> dict[str, str]:
    i = session.Info
    campos = ("SystemName", "Client", "User", "Language", "ApplicationServer",
              "Transaction", "Program")
    return {c: str(getattr(i, c, "") or "") for c in campos}


def _imprimir_info(inf: dict[str, str], sangria: str = "           ") -> None:
    print(f"{sangria}Sistema: {inf['SystemName']} | Mandante: {inf['Client']} | "
          f"Usuario: {inf['User'] or '-'} | Idioma: {inf['Language'] or '-'}")
    print(f"{sangria}Servidor: {inf['ApplicationServer']} | "
          f"Transaccion: {inf['Transaction']} ({inf['Program']})")


def _en_login(session) -> bool:
    return _info(session)["Program"].upper() == "SAPMSYST" or _buscar(session, ID_USUARIO) is not None


def _id_corto(id_completo: str) -> str:
    return re.sub(r"^/app/con\[\d+\]/ses\[\d+\]/", "", id_completo)


def _volcar(componente, nivel: int = 0, maximo: int = 400, contador: list | None = None) -> None:
    contador = contador if contador is not None else [0]
    for c in _hijos(componente):
        if contador[0] >= maximo:
            return
        contador[0] += 1
        tipo = str(getattr(c, "Type", ""))
        texto = "***" if tipo == "GuiPasswordField" else str(getattr(c, "Text", "") or "")
        editable = " (editable)" if getattr(c, "Changeable", False) else ""
        print(f"    {'  ' * nivel}{_id_corto(str(c.Id)):<55} {tipo:<20} {texto[:40]!r}{editable}")
        if getattr(c, "ContainerType", False):
            _volcar(c, nivel + 1, maximo, contador)


def _cerrar(session) -> None:
    """Cierra la sesion con /nex (sin popups de confirmacion)."""
    try:
        session.findById(ID_OKCODE).Text = "/nex"
        session.findById("wnd[0]").sendVKey(0)
        _ok("Sesion cerrada con /nex")
    except Exception as exc:
        _aviso(f"No se pudo cerrar con /nex ({exc}). Cierra la ventana a mano.")


# ── comandos ──────────────────────────────────────────────────────────

def cmd_entradas(args) -> int:
    archivo = Path(args.archivo) if args.archivo else (
        Path(os.getenv("APPDATA", "")) / "SAP" / "Common" / "SAPUILandscape.xml")
    print(f"ENTRADAS DE SAP LOGON ({archivo})")
    if not archivo.exists():
        return _falla("No existe el archivo de entradas",
                      "Indica la ruta con --archivo, o usa 'listar' con SAP abierto")
    raiz = ET.parse(archivo).getroot()
    servicios = [s for s in raiz.iter("Service") if s.get("type", "SAPGUI") == "SAPGUI"]
    if not servicios:
        _aviso("No hay entradas SAPGUI en el archivo")
    for s in servicios:
        snc = "si" if s.get("sncname") else "no"
        print(f"  {s.get('name', '')!r}")
        print(f"      sistema={s.get('systemid', '-')}  servidor={s.get('server', '-')}  SSO/SNC={snc}")
    for inc in raiz.iter("Include"):
        _aviso(f"Hay entradas centralizadas que no estan en este archivo: {inc.get('url')}")
    print("\n  Copia el nombre tal cual (entre comillas) para --entrada.")
    return 0


def cmd_listar(args) -> int:
    print("CONEXIONES ABIERTAS EN SAP GUI (solo lectura)")
    try:
        motor = _motor()
    except RuntimeError as exc:
        return _falla(str(exc), "Abre SAP y entra a mano; luego vuelve a correr 'listar'")
    conexiones = _hijos(motor)
    if not conexiones:
        _aviso("SAP Logon esta abierto pero no hay conexiones")
        return 0
    for ci, con in enumerate(conexiones):
        print(f"\n  con[{ci}] nombre exacto: {str(con.Description)!r}")
        for si, ses in enumerate(_hijos(con)):
            print(f"    ses[{si}]")
            _imprimir_info(_info(ses), sangria="           ")
    return 0


def cmd_campos(args) -> int:
    try:
        motor = _motor()
    except RuntimeError as exc:
        return _falla(str(exc))
    conexiones = _hijos(motor)
    if args.conexion >= len(conexiones):
        return _falla(f"No existe la conexion con[{args.conexion}]", "Usa 'listar' para ver los indices")
    sesiones = _hijos(conexiones[args.conexion])
    if args.sesion >= len(sesiones):
        return _falla(f"No existe la sesion ses[{args.sesion}]")
    ses = sesiones[args.sesion]
    ventana = ses.ActiveWindow
    print(f"CAMPOS DE {ventana.Name} - {ventana.Text!r}  (con[{args.conexion}]/ses[{args.sesion}])")
    _imprimir_info(_info(ses), sangria="  ")
    print()
    _volcar(ventana)
    print("\n  Los IDs se usan tal cual con session.findById(\"...\").")
    return 0


def cmd_abrir(args) -> int:
    entrada = args.entrada or os.getenv("SAP_ENTRADA")
    sistema = (args.sistema or os.getenv("SAP_SISTEMA") or "").upper()
    mandante = args.mandante or os.getenv("SAP_MANDANTE") or ""
    print("ABRIR SESION SAP (sin transacciones)")
    if not entrada:
        return _falla("Falta --entrada", "Usa 'entradas' o 'listar' para ver el nombre exacto")

    try:
        motor = _motor_arrancando_saplogon(args.saplogon)
    except RuntimeError as exc:
        return _falla(str(exc))

    # Solo se reutiliza una conexion si tiene EXACTAMENTE ese nombre.
    con = next((c for c in _hijos(motor) if str(c.Description) == entrada), None)
    abierta_por_mi = con is None
    if con is None:
        print(f"  Abriendo entrada {entrada!r} ...")
        try:
            con = motor.OpenConnection(entrada, True)
        except Exception as exc:
            return _falla(
                f"SAP no abrio la entrada: {exc}",
                "Revisa el nombre exacto con 'entradas'. Si SAP GUI muestra un aviso de que un "
                "script quiere abrir una conexion, aceptalo (o pide a TI desactivar ese aviso).",
            )
    else:
        _aviso("Ya habia una conexion abierta con ese nombre: se reutiliza y no se cerrara")

    ses = _hijos(con)[0]
    _esperar(ses)

    if _en_login(ses):
        _ok("Pantalla de login (esta entrada no hace SSO automatico)")
        if args.sin_login:
            print("  Campos de la pantalla de login:")
            _volcar(ses.findById("wnd[0]/usr"))
            print("  La conexion queda abierta en el login (cierrala a mano o corre 'campos').")
            return 0
        codigo = _login(ses, args, mandante)
        if codigo:
            if abierta_por_mi:
                _cerrar(ses)
            return codigo
    else:
        _ok("Entro sin pedir credenciales (SSO o sesion ya iniciada)")

    inf = _info(ses)
    _imprimir_info(inf)

    errores = []
    if sistema and inf["SystemName"].upper() != sistema:
        errores.append(f"sistema {inf['SystemName']} (se esperaba {sistema})")
    if mandante and inf["Client"] != mandante:
        errores.append(f"mandante {inf['Client']} (se esperaba {mandante})")
    if errores:
        _falla("Sistema equivocado: " + ", ".join(errores),
               "No se continua. Revisa --entrada, --sistema y --mandante")
    elif sistema or mandante:
        _ok("Sistema y mandante verificados")
    else:
        _aviso("No se verifico sistema/mandante (usa --sistema y --mandante)")

    if abierta_por_mi and not args.dejar_abierta:
        _cerrar(ses)
    return 1 if errores else 0


def _login(ses, args, mandante: str) -> int:
    usuario = args.usuario or os.getenv("SAP_USUARIO")
    if not usuario:
        return _falla("Falta --usuario (o SAP_USUARIO en .env)")
    clave = os.getenv("SAP_PASSWORD") or getpass.getpass(f"  Clave SAP de {usuario} (no se muestra): ")

    if mandante and _buscar(ses, ID_MANDANTE) is not None:
        ses.findById(ID_MANDANTE).Text = mandante
    if args.idioma and _buscar(ses, ID_IDIOMA) is not None:
        ses.findById(ID_IDIOMA).Text = args.idioma
    ses.findById(ID_USUARIO).Text = usuario
    ses.findById(ID_CLAVE).Text = clave
    del clave
    ses.findById("wnd[0]").sendVKey(0)
    _esperar(ses)

    # Popups posteriores al login (hasta 3)
    for _ in range(3):
        ventana = ses.ActiveWindow
        if ventana.Name == "wnd[0]":
            break
        if _buscar(ses, ID_CAMBIO_CLAVE) is not None:
            return _falla("SAP pide cambiar la clave", "Cambiala a mano una vez y vuelve a probar")
        if _buscar(ses, ID_MULTILOGON_CONTINUAR) is not None:
            _aviso("El usuario ya tenia otra sesion abierta: se continua sin cerrarla")
            ses.findById(ID_MULTILOGON_CONTINUAR).Select()
        else:
            _aviso(f"Popup tras el login: {ventana.Text!r} -> se acepta")
        ses.findById(f"{ventana.Name}/tbar[0]/btn[0]").press()
        _esperar(ses)

    barra = _buscar(ses, ID_SBAR)
    if barra is not None and str(barra.MessageType) in ("E", "A"):
        return _falla(f"SAP rechazo el login: {barra.Text}")
    if _en_login(ses):
        texto = barra.Text if barra is not None else ""
        return _falla(f"Sigue en la pantalla de login. {texto}")
    _ok(f"Login correcto como {usuario}")
    return 0


# ── main ──────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sesion SAP por GUI Scripting (sin imagenes)")
    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("entradas", help="Lista las entradas de SAP Logon (nombre exacto)")
    p.add_argument("--archivo", help="Ruta a SAPUILandscape.xml")
    p.set_defaults(func=cmd_entradas)

    p = sub.add_parser("listar", help="Lista conexiones y sesiones abiertas (solo lectura)")
    p.set_defaults(func=cmd_listar)

    p = sub.add_parser("campos", help="Muestra los IDs de la ventana activa")
    p.add_argument("--conexion", type=int, default=0)
    p.add_argument("--sesion", type=int, default=0)
    p.set_defaults(func=cmd_campos)

    p = sub.add_parser("abrir", help="Abre la entrada, inicia sesion, verifica y cierra")
    p.add_argument("--entrada", help="Nombre EXACTO en SAP Logon (o SAP_ENTRADA en .env)")
    p.add_argument("--sistema", help="Sistema esperado, p. ej. E05 (o SAP_SISTEMA)")
    p.add_argument("--mandante", help="Mandante esperado (o SAP_MANDANTE)")
    p.add_argument("--usuario", help="Usuario SAP si no hay SSO (o SAP_USUARIO)")
    p.add_argument("--idioma", help="Idioma de login, p. ej. ES")
    p.add_argument("--saplogon", help="Ruta a saplogon.exe")
    p.add_argument("--sin-login", action="store_true",
                   help="Solo abrir y mostrar los campos del login, sin escribir nada")
    p.add_argument("--dejar-abierta", action="store_true", help="No cerrar la sesion al terminar")
    p.set_defaults(func=cmd_abrir)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
