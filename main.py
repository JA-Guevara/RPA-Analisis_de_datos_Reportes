from __future__ import annotations

import sys
from pathlib import Path

src_path = str(Path(__file__).resolve().parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from itacamba_reportes.cli import main


if __name__ == "__main__":
    sys.exit(main())
