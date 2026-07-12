"""One-shot pipeline refresh, used locally and by GitHub Actions.

Appends one synthetic remit cycle, reloads DuckDB, rebuilds + retests dbt.
Pass --base to regenerate from scratch instead of appending.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def dbt_exe() -> str:
    candidate = Path(sys.executable).parent / ("dbt.exe" if sys.platform == "win32" else "dbt")
    return str(candidate) if candidate.exists() else (shutil.which("dbt") or "dbt")


def run(cmd: list[str], cwd: Path = ROOT) -> None:
    print(f"\n$ {' '.join(str(c) for c in cmd)}", flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def main() -> None:
    append = "--base" not in sys.argv
    run([sys.executable, "data_gen/generate.py"] + (["--append"] if append else []))
    run([sys.executable, "warehouse/load_raw.py"])
    run([dbt_exe(), "build", "--profiles-dir", "."], cwd=ROOT / "dbt_project")


if __name__ == "__main__":
    main()
