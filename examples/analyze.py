"""Phase 6: render the writeup figures from raw run records.

Auto-discovers the Phase 4 baseline (newest full R>=5 sweep) and the Phase 5
defense sweep (newest slice=phase5-defenses) unless given explicitly, then
writes PNGs into results/figures/.

Run:
    python examples/analyze.py
    python examples/analyze.py <phase4_run_dir> <phase5_run_dir>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from mcpoison.analysis import generate_all, tradeoff_summary
from mcpoison.experiment import load_records

RUNS = Path("runs")


def _meta(run_dir: Path) -> dict:
    path = run_dir / "meta.json"
    return json.loads(path.read_text()) if path.exists() else {}


def _discover() -> tuple[Path, Path]:
    dirs = sorted(p for p in RUNS.iterdir() if p.is_dir())
    phase5 = next((d for d in reversed(dirs) if _meta(d).get("slice") == "phase5-defenses"), None)
    phase4 = next(
        (d for d in reversed(dirs)
         if _meta(d).get("slice") is None and (_meta(d).get("repeats") or 0) >= 5),
        None,
    )
    if phase4 is None or phase5 is None:
        raise SystemExit("could not auto-discover runs; pass <phase4_dir> <phase5_dir>")
    return phase4, phase5


def main() -> None:
    if len(sys.argv) >= 3:
        phase4, phase5 = Path(sys.argv[1]), Path(sys.argv[2])
    else:
        phase4, phase5 = _discover()

    print(f"phase 4 baseline: {phase4}")
    print(f"phase 5 defenses: {phase5}")

    print("\nsafety / utility tradeoff:")
    print(f"  {'defense':<22}{'attack%':>9}{'task(atk)%':>12}{'task(base)%':>13}")
    for row in tradeoff_summary(load_records(phase5)):
        def pct(v):
            return "  -  " if v is None else f"{v:.0%}"
        print(f"  {row['defense']:<22}{pct(row['attack_success']):>9}"
              f"{pct(row['task_success_attacked']):>12}{pct(row['task_success_baseline']):>13}")

    made = generate_all(phase4, phase5, "results/figures")
    print("\nfigures written:")
    for p in made:
        print(f"  {p}")


if __name__ == "__main__":
    main()
