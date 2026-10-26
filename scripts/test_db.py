from __future__ import annotations

import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sqlalchemy import text
from itacamba_reportes.core.db.connection import get_engine
from itacamba_reportes.core.settings import EnvConfig


def test_connection() -> int:
    print("==================================================")
    print("=== PROBANDO CONEXIÓN A SQL SERVER            ===")
    print("==================================================")
    print(f"Servidor configurado : {EnvConfig.DB_SERVER}")
    print(f"Puerto               : {EnvConfig.DB_PORT}")
    print(f"Base de datos        : {EnvConfig.DB_NAME}")
    print(f"Driver ODBC          : {EnvConfig.DB_DRIVER}")
    auth_type = f"SQL User ({EnvConfig.DB_USER})" if (EnvConfig.DB_USER and EnvConfig.DB_PASSWORD) else "Windows Authentication (SSPI / Trusted)"
    print(f"Modo autenticación   : {auth_type}")
    print(f"Trust Certificate    : {EnvConfig.DB_TRUST_CERT}")
    print("--------------------------------------------------")
    print("Intentando conectar...")

    t0 = perf_counter()
    try:
        eng = get_engine()
        with eng.connect() as conn:
            elapsed = perf_counter() - t0
            row = conn.execute(text("SELECT @@SERVERNAME, DB_NAME(), SUSER_SNAME(), @@VERSION")).fetchone()
            print()
            print(">>> ¡CONEXIÓN EXITOSA! <<<")
            print(f"Tiempo de respuesta  : {elapsed:.3f} s")
            print(f"Servidor SQL real    : {row[0]}")
            print(f"Base de datos activa : {row[1]}")
            print(f"Usuario autenticado  : {row[2]}")
            version_line = str(row[3]).splitlines()[0] if row[3] else "Desconocida"
            print(f"Versión de motor     : {version_line}")
            print("==================================================")
            return 0
    except Exception as exc:
        elapsed = perf_counter() - t0
        print()
        print(">>> ERROR AL CONECTAR <<<")
        print(f"Tiempo transcurrido  : {elapsed:.3f} s")
        print(f"Detalle del error    : {exc}")
        print("==================================================")
        print("Consejos para resolverlo:")
        print("1. Verifique que la VPN esté activa si está fuera de la red de la oficina.")
        print("2. Verifique que el servidor responda con ping: Test-NetConnection -ComputerName " + str(EnvConfig.DB_SERVER) + " -Port " + str(EnvConfig.DB_PORT))
        print("3. Si usa autenticación de Windows, verifique que su usuario tenga permisos en la base de datos.")
        return 1


if __name__ == "__main__":
    sys.exit(test_connection())
