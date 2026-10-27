from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from itacamba_reportes.core.db.connection import get_engine
from itacamba_reportes.core.db.schema import drop_all_tables, truncate_all_tables
from itacamba_reportes.core.settings import EnvConfig


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Script de limpieza y vaciado de todas las tablas en la Base de Datos SQL Server.",
    )
    parser.add_argument(
        "--force", "-y",
        action="store_true",
        help="Omite la confirmación interactiva de seguridad.",
    )
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Elimina las tablas por completo (DROP) en lugar de solo vaciarlas (TRUNCATE/DELETE).",
    )
    args = parser.parse_args()

    print("==================================================")
    print("=== LIMPIEZA DE BASE DE DATOS - BOT ITACAMBA   ===")
    print("==================================================")
    print(f"Servidor SQL      : {EnvConfig.DB_SERVER}")
    print(f"Base de Datos     : {EnvConfig.DB_NAME}")
    print(f"Modo              : {'DROP TABLE (Eliminación completa)' if args.drop else 'TRUNCATE/DELETE (Vaciado de datos)'}")
    print("--------------------------------------------------")

    if not args.force:
        accion = "ELIMINAR COMPLETAMENTE" if args.drop else "VACIAR TODOS LOS DATOS DE"
        try:
            resp = input(f"¿Está 100% seguro de {accion} todas las tablas? (escriba 'SI' para confirmar): ").strip()
            if resp != "SI":
                print("\n[INFO] Operación cancelada por seguridad.")
                return 0
        except (KeyboardInterrupt, EOFError):
            print("\n[INFO] Cancelado por el usuario.")
            return 0

    print("\nEjecutando limpieza en SQL Server...")
    try:
        if args.drop:
            dropped = drop_all_tables(reset_state=True)
            print(f"[OK] Se eliminaron {len(dropped)} tablas y se reseteó el estado de firmas.")
            for t in dropped:
                print(f"  - Eliminada: {t}")
        else:
            cleared = truncate_all_tables(reset_state=True)
            print(f"[OK] Se vaciaron {len(cleared)} tablas y se reseteó el estado de firmas.")
            for t in cleared:
                print(f"  - Vaciada: {t}")
        print("\n==================================================")
        print("=== PROCESO DE LIMPIEZA FINALIZADO CON ÉXITO   ===")
        print("==================================================")
        return 0
    except Exception as exc:
        print(f"\n[ERROR] Falló la limpieza: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
