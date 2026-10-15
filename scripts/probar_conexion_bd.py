"""Prueba de conexion a la BD de reportes - SOLO LECTURA.

Usa exactamente la misma configuracion que el bot (.env -> persistence/engine.py):
si esta prueba pasa, el bot se conecta igual.

No escribe, no borra y no crea nada: solo ejecuta SELECT y al final hace rollback.
No imprime contrasenas.

Uso (desde la raiz del proyecto, con el python del venv del proyecto):
    python scripts/probar_conexion_bd.py
    python scripts/probar_conexion_bd.py --timeout 10

Devuelve exit code 1 si hubo alguna FALLA.
"""

from __future__ import annotations

import argparse
import importlib
import os
import pkgutil
import re
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Respaldo por si no se pudieran importar los modelos.
TABLAS_RESPALDO = (
    "int_cartera", "int_despacho_bi", "int_despacho_mes", "int_gd20",
    "int_query", "int_ventas_bi", "pipeline_executions",
    "int_ref_almacen", "int_ref_centro", "int_ref_equipo",
    "int_ref_localidad", "int_ref_material", "int_ref_semana",
    "stg_cartera", "stg_gd20", "stg_query",
)

# Claves de la cadena ODBC que es seguro mostrar (nunca PWD).
CLAVES_VISIBLES = {
    "driver", "server", "database", "trusted_connection",
    "trustservercertificate", "encrypt", "authentication",
}

# Permisos que el bot necesita sobre sus tablas:
#   SELECT/INSERT/UPDATE/DELETE -> carga y MERGE del historico
#   ALTER                        -> TRUNCATE TABLE
PERMISOS_TABLA = ("SELECT", "INSERT", "UPDATE", "DELETE", "ALTER")

_fallas = 0


def ok(msg: str) -> None:
    print(f"  [  OK  ] {msg}")


def aviso(msg: str, sugerencia: str | None = None) -> None:
    print(f"  [ AVISO] {msg}")
    if sugerencia:
        print(f"           -> {sugerencia}")


def falla(msg: str, sugerencia: str | None = None) -> None:
    global _fallas
    _fallas += 1
    print(f"  [ FALLA] {msg}")
    if sugerencia:
        print(f"           -> {sugerencia}")


def info(msg: str) -> None:
    print(f"           {msg}")


def titulo(texto: str) -> None:
    print(f"\n{texto}")


def fin() -> int:
    print()
    if _fallas:
        print(f"RESULTADO: {_fallas} falla(s). Revisa las sugerencias de arriba.")
        return 1
    print("RESULTADO: conexion OK.")
    return 0


def _pares_odbc(cadena: str) -> list[tuple[str, str]]:
    pares = []
    for parte in cadena.split(";"):
        if "=" in parte:
            clave, valor = parte.split("=", 1)
            pares.append((clave.strip(), valor.strip()))
    return pares


def _cadena_segura(cadena: str) -> str:
    return ";".join(
        f"{k}={v}" for k, v in _pares_odbc(cadena) if k.lower() in CLAVES_VISIBLES
    )


def _usa_usuario_sql(cadena: str) -> bool:
    return any(k.lower() == "uid" and v for k, v in _pares_odbc(cadena))


def _host_y_puerto(cadena: str) -> tuple[str | None, int]:
    for clave, valor in _pares_odbc(cadena):
        if clave.lower() in ("server", "address", "addr"):
            valor = valor.strip("{}")
            if valor.lower().startswith("tcp:"):
                valor = valor[4:]
            host, _, puerto = valor.partition(",")
            return host.strip(), int(puerto) if puerto.strip().isdigit() else 1433
    return None, 1433


def _sugerencia_login(msg: str) -> str:
    m = msg.lower()
    if "im002" in m or "can't open lib" in m or "data source name not found" in m:
        return ("No esta instalado el driver indicado en DB_DRIVER. "
                "Verifica con: Get-OdbcDriver -Name 'ODBC Driver 17*'")
    if "untrusted domain" in m or "18452" in m:
        return ("El servidor no confia en tu usuario/equipo: el equipo no esta en el dominio, "
                "o estas con un usuario local de Windows. Inicia sesion con tu usuario de dominio.")
    if "sspi" in m:
        return ("Fallo Kerberos/SSPI. Prueba con el nombre completo del servidor (FQDN) en DB_SERVER "
                "y confirma con el DBA que el SPN del servicio SQL esta registrado.")
    if "login failed for user ''" in m or "anonymous" in m:
        return ("El servidor recibio un usuario anonimo: tu sesion de Windows no esta pasando "
                "credenciales de dominio. Revisa que estes logueado con tu cuenta de dominio.")
    if "18456" in m or "login failed" in m:
        return ("El servidor no tiene un login para tu usuario de Windows (o esta deshabilitado). "
                "Pide al DBA un login de Windows para tu cuenta y un usuario en la BD.")
    if "4060" in m or "cannot open database" in m:
        return ("El login existe pero no tiene acceso a la BD (o el nombre en DB_NAME esta mal). "
                "Pide al DBA que cree tu usuario en esa BD.")
    if "timeout" in m or "08001" in m or "hyt00" in m:
        return "No se llega al servicio SQL: VPN, firewall, nombre de instancia o puerto."
    return "Revisa el mensaje de error completo con el DBA."


def _tablas_esperadas() -> list[str]:
    try:
        from itacamba_reportes.persistence.base import Base
        import itacamba_reportes.persistence.models as paquete

        for mod in pkgutil.walk_packages(paquete.__path__, paquete.__name__ + "."):
            importlib.import_module(mod.name)
        nombres = sorted(t.name for t in Base.metadata.sorted_tables)
        if nombres:
            return nombres
    except Exception:
        pass
    return sorted(TABLAS_RESPALDO)


def _head_alembic() -> str | None:
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        return ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini"))).get_current_head()
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Prueba de conexion a la BD (solo lectura)")
    parser.add_argument("--timeout", type=int, default=5, help="segundos para la prueba TCP")
    args = parser.parse_args()

    print("PRUEBA DE CONEXION - BD de reportes (solo lectura)")

    # ------------------------------------------------------------------ 1
    titulo("1. CONFIGURACION (.env)")
    try:
        from sqlalchemy import text
        from sqlalchemy.engine import make_url

        from itacamba_reportes.config.env_config import EnvConfig
        from itacamba_reportes.persistence import engine as modulo_engine
    except ImportError as exc:
        falla(f"No se pudo importar: {exc}",
              "Usa el python del venv del proyecto e instala requirements.txt")
        return fin()

    engine = modulo_engine.engine
    if not modulo_engine.DATABASE_URL or engine is None:
        falla("No se pudo armar la conexion a la BD",
              "Revisa DATABASE_URL / DB_* en .env y que pyodbc este instalado")
        return fin()

    origen = "DATABASE_URL" if EnvConfig.DATABASE_URL else "variables DB_*"
    (cadena,), _ = engine.dialect.create_connect_args(make_url(modulo_engine.DATABASE_URL))
    ok(f"Conexion armada desde {origen}")
    info(f"ODBC: {_cadena_segura(cadena)}")

    if _usa_usuario_sql(cadena):
        info("Autenticacion: SQL Server (usuario y clave)")
    else:
        info("Autenticacion: Windows -> entra como el usuario de Windows que ejecuta este proceso")
        info(f"Usuario de Windows actual: {os.environ.get('USERDOMAIN', '?')}\\"
             f"{os.environ.get('USERNAME', '?')}")
        if EnvConfig.DB_USER or EnvConfig.DB_PASSWORD:
            aviso("DB_USER / DB_PASSWORD siguen en .env pero con autenticacion Windows no se usan",
                  "Conviene borrarlas para no dejar una clave guardada sin necesidad")

    # ------------------------------------------------------------------ 2
    titulo("2. RED")
    host, puerto = _host_y_puerto(cadena)
    if not host:
        falla("No se encontro el servidor en la cadena de conexion", "Revisa DB_SERVER")
        return fin()
    if "\\" in host:
        aviso(f"'{host}' es una instancia con nombre: se omite la prueba TCP directa")
    else:
        try:
            ip = socket.gethostbyname(host)
            ok(f"DNS {host} -> {ip}")
        except OSError:
            falla(f"DNS: no se resuelve '{host}'",
                  "Revisa VPN/red corporativa, o usa el nombre completo (FQDN) o la IP")
            return fin()
        try:
            socket.create_connection((host, puerto), timeout=args.timeout).close()
            ok(f"TCP {host}:{puerto} abierto")
        except OSError as exc:
            falla(f"TCP {host}:{puerto} no responde ({exc})",
                  "Firewall/VPN, o SQL Server escucha en otro puerto (instancia con nombre)")
            return fin()

    # ------------------------------------------------------------------ 3
    titulo("3. LOGIN")
    try:
        conn = engine.connect()
    except Exception as exc:
        msg = str(getattr(exc, "orig", exc))
        falla(f"No se pudo iniciar sesion: {msg[:400]}", _sugerencia_login(msg))
        return fin()

    with conn:
        fila = conn.execute(text(
            "SELECT SUSER_SNAME() AS login_sql, USER_NAME() AS usuario_bd, "
            "DB_NAME() AS bd, @@SERVERNAME AS servidor, "
            "CAST(SERVERPROPERTY('ProductVersion') AS nvarchar(64)) AS version"
        )).mappings().one()
        ok(f"Conectado como {fila['login_sql']} (usuario en la BD: {fila['usuario_bd']})")
        info(f"Servidor: {fila['servidor']} | BD: {fila['bd']} | SQL Server {fila['version']}")

        if EnvConfig.DB_NAME and str(fila["bd"]).lower() != EnvConfig.DB_NAME.lower():
            falla(f"Entraste a la BD '{fila['bd']}' y no a '{EnvConfig.DB_NAME}'",
                  "Revisa DB_NAME o el acceso de tu usuario a esa BD")

        try:
            esquema = conn.execute(text(
                "SELECT auth_scheme FROM sys.dm_exec_connections WHERE session_id = @@SPID"
            )).scalar()
            info(f"Protocolo de autenticacion: {esquema}")
        except Exception:
            conn.rollback()
            info("Protocolo de autenticacion: no visible (requiere VIEW SERVER STATE; no es problema)")

        # -------------------------------------------------------------- 4
        titulo("4. TABLAS Y MIGRACIONES")
        existentes = {
            r[0] for r in conn.execute(text(
                "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'"
            ))
        }
        esperadas = _tablas_esperadas()
        presentes = [t for t in esperadas if t in existentes]
        faltan = [t for t in esperadas if t not in existentes]

        head = _head_alembic()
        version_bd = None
        if "alembic_version" in existentes:
            version_bd = conn.execute(text("SELECT TOP 1 version_num FROM alembic_version")).scalar()

        if not presentes:
            aviso(f"La BD no tiene ninguna de las {len(esperadas)} tablas del bot (BD vacia)",
                  "Crear el esquema: python -m alembic upgrade head  (lo hace quien tenga permisos DDL)")
        elif faltan:
            falla(f"Faltan {len(faltan)} de {len(esperadas)} tablas: {', '.join(faltan)}",
                  "Revisa la migracion con: python -m alembic current")
        else:
            ok(f"Las {len(esperadas)} tablas del bot existen")

        if version_bd and head and version_bd != head:
            aviso(f"Migracion en BD: {version_bd} | ultima del codigo: {head}",
                  "Ejecutar: python -m alembic upgrade head")
        elif version_bd and head:
            ok(f"Migracion alembic al dia ({version_bd})")
        elif version_bd:
            info(f"Migracion en BD: {version_bd} (no se pudo leer la ultima del codigo)")
        elif presentes:
            aviso("Hay tablas pero no existe alembic_version",
                  "La BD no se creo con alembic; consultar antes de migrar")

        if presentes:
            conteos = dict(conn.execute(text(
                "SELECT t.name, SUM(p.rows) FROM sys.tables t "
                "JOIN sys.partitions p ON p.object_id = t.object_id AND p.index_id IN (0, 1) "
                "GROUP BY t.name"
            )).all())
            info("Filas por tabla (para comparar con el servidor anterior):")
            for t in presentes:
                info(f"  {t:<24} {int(conteos.get(t) or 0):>12,}")

        # -------------------------------------------------------------- 5
        titulo("5. PERMISOS")
        roles = conn.execute(text(
            "SELECT IS_ROLEMEMBER('db_owner'), IS_ROLEMEMBER('db_datareader'), "
            "IS_ROLEMEMBER('db_datawriter'), IS_ROLEMEMBER('db_ddladmin')"
        )).one()
        nombres_roles = ("db_owner", "db_datareader", "db_datawriter", "db_ddladmin")
        info("Roles: " + ", ".join(
            f"{n}={'si' if v == 1 else 'no'}" for n, v in zip(nombres_roles, roles)
        ))

        crear = conn.execute(text(
            "SELECT HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'CREATE TABLE')"
        )).scalar()
        if crear == 1:
            ok("Puede crear tablas (necesario para alembic upgrade)")
        else:
            aviso("No puede crear tablas",
                  "Solo importa para correr migraciones; el DBA puede correrlas por ti")

        # permiso faltante -> tablas afectadas
        sin_permiso: dict[str, list[str]] = {}
        for t in presentes:
            for permiso in PERMISOS_TABLA:
                tiene = conn.execute(
                    text("SELECT HAS_PERMS_BY_NAME(:obj, 'OBJECT', :perm)"),
                    {"obj": f"dbo.{t}", "perm": permiso},
                ).scalar()
                if tiene != 1:
                    sin_permiso.setdefault(permiso, []).append(t)
        if presentes and not sin_permiso:
            ok(f"Permisos {'/'.join(PERMISOS_TABLA)} en todas las tablas")
        for permiso, tablas in sin_permiso.items():
            alcance = "todas las tablas" if len(tablas) == len(presentes) else ", ".join(tablas)
            falla(f"Falta permiso {permiso} en {alcance}")
        if sin_permiso:
            info("-> El bot hace SELECT, INSERT, UPDATE (historico), DELETE y TRUNCATE (requiere ALTER).")
            info("   Pedir al DBA: db_datareader + db_datawriter + GRANT ALTER ON SCHEMA::dbo")

        conn.rollback()

    return fin()


if __name__ == "__main__":
    sys.exit(main())
