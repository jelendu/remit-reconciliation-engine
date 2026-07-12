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


def publish_artifacts() -> None:
    """Copy dbt's manifest + run results where the dashboard can read them.

    target/ is gitignored; the dashboard's Pipeline page renders the lineage
    DAG and test results from these committed copies.
    """
    src = ROOT / "dbt_project" / "target"
    dst = ROOT / "dbt_project" / "artifacts"
    dst.mkdir(exist_ok=True)
    for name in ("manifest.json", "run_results.json"):
        shutil.copy2(src / name, dst / name)
        print(f"published {dst / name}")


def main() -> None:
    append = "--base" not in sys.argv
    run([sys.executable, "data_gen/generate.py"] + (["--append"] if append else []))
    run([sys.executable, "warehouse/load_raw.py"])
    run([dbt_exe(), "build", "--profiles-dir", "."], cwd=ROOT / "dbt_project")
    publish_artifacts()


if __name__ == "__main__":
    main()
