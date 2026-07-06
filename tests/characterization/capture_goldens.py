"""Captura los goldens de caracterización con el código vigente.

Uso:
    python tests/characterization/capture_goldens.py --write

Escribe golden/goldens.json. Correr SOLO sobre el código cuyo
comportamiento se quiere fijar como referencia (pre-refactor).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
sys.path.insert(0, str(HERE))

from scenarios import compute_scenarios, get_world  # noqa: E402

GOLDEN_PATH = HERE / "golden" / "goldens.json"


def main() -> int:
    if "--write" not in sys.argv:
        print("Agrega --write para sobreescribir los goldens.")
        return 1
    world = get_world()
    print(f"Mundo detectado: {world.name}")
    data = compute_scenarios(world)
    GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN_PATH.write_text(
        json.dumps(data, indent=1, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    print(f"Goldens escritos: {GOLDEN_PATH} ({len(data)} escenarios)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
