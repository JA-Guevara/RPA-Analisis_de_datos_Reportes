"""Manual DB connectivity check."""

import sys
from pathlib import Path
from time import perf_counter

from sqlalchemy import create_engine, text

# Add the package source path so the script can run from the repo root.
sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from itacamba_reportes.config.env_config import EnvConfig


def build_connection_string() -> str:
    """Build the SQLAlchemy connection string from EnvConfig."""
    return (
        f"mssql+pyodbc://{EnvConfig.DB_USER}:{EnvConfig.DB_PASSWORD}"
        f"@{EnvConfig.DB_SERVER}:{EnvConfig.DB_PORT}/{EnvConfig.DB_NAME}"
        f"?driver={EnvConfig.DB_DRIVER}&TrustServerCertificate=yes"
    )


def test_db_connection() -> None:
    """Open a DB connection and run a simple SELECT 1 health check."""
    print("\n=== TEST DB CONNECTION ===")

    conn_str = build_connection_string()

    print(f"Server: {EnvConfig.DB_SERVER}")
    print(f"Database: {EnvConfig.DB_NAME}")
    print(f"Driver: {EnvConfig.DB_DRIVER}")

    t0 = perf_counter()

    engine = create_engine(conn_str)

    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1 AS test"))
        value = result.scalar()

    t1 = perf_counter()

    assert value == 1, "La consulta no devolvio 1"

    print("\nRESULTADO:")
    print("Conexion exitosa")
    print(f"Tiempo conexion: {t1 - t0:.4f} segundos")


if __name__ == "__main__":
    test_db_connection()
