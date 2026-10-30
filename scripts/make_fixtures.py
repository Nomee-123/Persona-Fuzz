from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    subprocess.check_call([sys.executable, "-m", "engine.cli", "personas", "--n", "200"], cwd=ROOT)
    subprocess.check_call([sys.executable, "-m", "engine.cli", "make-sample", "--force"], cwd=ROOT)


if __name__ == "__main__":
    main()
