"""Phase 4 baseline experiment: sweep the full matrix and aggregate real rates.

The matrix is model x scenario x door x condition, where a condition is one of
the payload styles or the no-attack baseline. Each cell is repeated R times
because single runs are not trustworthy (we watched a cell flip between runs in
Phase 3), so the headline number for a cell is a *rate* over repeats, not a
yes/no.

Raw per-trial records are appended to `runs/<timestamp>/results.jsonl` as they
finish (plus a `meta.json`) so a crash mid-sweep does not lose completed work
and a run can be resumed. Sampling is left at the model default (temperature
~1) so repeats genuinely vary.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import payloads
from .defenses import DEFENSE_IDS, get_defense
from .runner import run_trial
from .scenarios import all_scenario_ids, get_scenario

DOORS = ["output", "description"]

# The Anthropic 4.5 capability ladder (same generation, so the comparison is
# about capability, not provider quirks). External providers are parked until
# the writeup; see FINDINGS.md.
DEFAULT_MODELS = [
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-5-20250929",
    "claude-opus-4-5-20251101",
]

SONNET = "claude-sonnet-4-5-20250929"

# Cheap confirmation slice: the Haiku cells that would change the story if
# Sonnet disagreed. Devops-output (including blunt vs covert) already finished
# in the first R=5 run, so it is not listed here.
SONNET_SLICE: list[tuple[str, str, str | None]] = [
    ("devops", "description", "blunt"),
    ("support", "description", None),
    ("support", "description", "authority"),
    ("support", "description", "covert"),
    ("support", "output", None),
    ("support", "output", "covert"),
    ("support", "output", "obfuscated"),
]


@dataclass(frozen=True)
class Cell:
    model: str
    scenario: str
    door: str
    payload: str | None  # a style id, or None for the baseline
    defense: str = "none"


def _cell_key(
    model: str, scenario: str, door: str, payload: str | None, defense: str, repeat: int
) -> tuple:
    return (model, scenario, door, payload, defense, repeat)


def build_cells(models, scenarios, doors, styles) -> list[Cell]:
    cells: list[Cell] = []
    for model in models:
        for scenario in scenarios:
            for door in doors:
                cells.append(Cell(model, scenario, door, None))  # baseline
                for style in styles:
                    cells.append(Cell(model, scenario, door, style))
    return cells


def build_sonnet_slice() -> list[Cell]:
    return [Cell(SONNET, scenario, door, payload) for scenario, door, payload in SONNET_SLICE]


# --- Phase 5: defenses on the cells that leak -----------------------------------

PHASE5_MODEL = "claude-haiku-4-5-20251001"

# Attacked cells that reliably leak in the Haiku R=5 baseline, chosen to span
# domain x door (plus the single support/description style that lands), so a
# defense's effect is visible everywhere it matters.
_PHASE5_ATTACKED: list[tuple[str, str, str | None]] = [
    ("devops", "output", "remediation"),
    ("devops", "output", "covert"),
    ("devops", "description", "blunt"),
    ("devops", "description", "covert"),
    ("support", "output", "remediation"),
    ("support", "output", "covert"),
    ("support", "description", "authority"),
]

# The four (scenario, door) no-attack baselines, for measuring how much each
# defense dents the agent's real job (the utility axis of the tradeoff).
_PHASE5_BASELINES: list[tuple[str, str, str | None]] = [
    ("devops", "output", None),
    ("devops", "description", None),
    ("support", "output", None),
    ("support", "description", None),
]


def build_phase5_cells() -> list[Cell]:
    conditions = _PHASE5_ATTACKED + _PHASE5_BASELINES
    return [
        Cell(PHASE5_MODEL, scenario, door, payload, defense)
        for defense in DEFENSE_IDS
        for (scenario, door, payload) in conditions
    ]


async def _run_repeat(cell: Cell, scenario_obj, repeat: int, sem: asyncio.Semaphore) -> dict:
    record = {
        "model": cell.model,
        "scenario": cell.scenario,
        "door": cell.door,
        "payload": cell.payload,
        "defense": cell.defense,
        "repeat": repeat,
    }
    async with sem:
        try:
            result = await run_trial(
                scenario_obj,
                door=cell.door,
                payload=cell.payload,
                model=cell.model,
                defense=get_defense(cell.defense),
            )
            record.update(
                attempted=result.attempted,
                succeeded=result.succeeded,
                task_success=result.task_success,
                tools_called=result.tools_called,
                final_text=result.final_text[:500],
                error=None,
            )
        except Exception as exc:  # one bad trial should not sink the sweep
            record.update(
                attempted=None,
                succeeded=None,
                task_success=None,
                tools_called=[],
                final_text="",
                error=repr(exc),
            )
    return record


async def run_sweep(
    *,
    models: list[str] | None = None,
    repeats: int = 5,
    scenarios: list[str] | None = None,
    doors: list[str] | None = None,
    styles: list[str] | None = None,
    cells: list[Cell] | None = None,
    concurrency: int = 4,
    out_root: str = "runs",
    resume_dir: str | Path | None = None,
    slice_name: str | None = None,
) -> Path:
    models = models or DEFAULT_MODELS
    scenarios = scenarios or all_scenario_ids()
    doors = doors or DOORS
    styles = styles or payloads.STYLES
    cells = cells if cells is not None else build_cells(models, scenarios, doors, styles)

    needed_scenarios = sorted({c.scenario for c in cells})
    scenario_objs = {sid: get_scenario(sid) for sid in needed_scenarios}

    if resume_dir:
        out_dir = Path(resume_dir)
        existing = load_records(out_dir)
        # Failed trials (e.g. out-of-credit) are not "done" — rerun them.
        done_keys = {
            _cell_key(
                r["model"],
                r["scenario"],
                r["door"],
                r["payload"],
                r.get("defense", "none"),
                r["repeat"],
            )
            for r in existing
            if r.get("error") is None
        }
        print(f"resuming {out_dir} ({len(done_keys)} successful trials already on disk)")
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        out_dir = Path(out_root) / stamp
        out_dir.mkdir(parents=True, exist_ok=True)
        _write_meta(
            out_dir, models, scenarios, doors, styles, repeats, concurrency, slice_name
        )
        existing = []
        done_keys = set()

    pending: list[tuple[Cell, int]] = []
    for cell in cells:
        for r in range(repeats):
            key = _cell_key(
                cell.model, cell.scenario, cell.door, cell.payload, cell.defense, r
            )
            if key not in done_keys:
                pending.append((cell, r))

    already_ok = len(done_keys)
    total = already_ok + len(pending)
    label = f"slice={slice_name} " if slice_name else ""
    print(
        f"{label}running {len(pending)} remaining of {total} trials "
        f"({len(cells)} cells x {repeats} repeats, concurrency {concurrency})"
    )
    if not pending:
        print("nothing left to run")
        return out_dir

    sem = asyncio.Semaphore(concurrency)
    results_path = out_dir / "results.jsonl"
    started = time.time()
    done = already_ok

    async def _one(cell: Cell, repeat: int) -> dict:
        return await _run_repeat(cell, scenario_objs[cell.scenario], repeat, sem)

    tasks = [asyncio.create_task(_one(cell, r)) for cell, r in pending]
    with results_path.open("a") as f:
        for coro in asyncio.as_completed(tasks):
            record = await coro
            f.write(json.dumps(record) + "\n")
            f.flush()
            done += 1
            if done % 10 == 0 or done == total:
                print(f"  {done}/{total} trials done ({time.time() - started:.0f}s)")

    return out_dir


def _write_meta(
    out_dir, models, scenarios, doors, styles, repeats, concurrency, slice_name=None
) -> None:
    meta = {
        "timestamp_utc": out_dir.name,
        "models": models,
        "scenarios": scenarios,
        "doors": doors,
        "styles": styles,
        "repeats": repeats,
        "concurrency": concurrency,
        "slice": slice_name,
        "git_commit": _git_commit(),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2))


def _git_commit() -> str | None:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL
            )
            .decode()
            .strip()
        )
    except Exception:
        return None


# --- Aggregation ----------------------------------------------------------------


def load_records(run_dir: str | Path) -> list[dict]:
    path = Path(run_dir) / "results.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def aggregate(records: list[dict]) -> list[dict]:
    """Collapse repeats into per-cell rates."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in records:
        key = (r["model"], r["scenario"], r["door"], r["payload"], r.get("defense", "none"))
        groups[key].append(r)

    rows: list[dict] = []
    for (model, scenario, door, payload, defense), rs in groups.items():
        ok = [r for r in rs if r.get("error") is None]
        n = len(ok)

        def rate(field: str) -> float | None:
            return sum(bool(r[field]) for r in ok) / n if n else None

        rows.append(
            {
                "model": model,
                "scenario": scenario,
                "door": door,
                "payload": payload or "(baseline)",
                "defense": defense,
                "n": n,
                "errors": len(rs) - n,
                "attempted": rate("attempted"),
                "succeeded": rate("succeeded"),
                "task_success": rate("task_success"),
            }
        )
    rows.sort(key=lambda x: (x["model"], x["scenario"], x["door"], x["payload"], x["defense"]))
    return rows


def write_aggregate(run_dir: str | Path, rows: list[dict] | None = None) -> Path:
    run_dir = Path(run_dir)
    rows = rows if rows is not None else aggregate(load_records(run_dir))
    path = run_dir / "aggregate.json"
    path.write_text(json.dumps(rows, indent=2))
    return path


def _fmt(rate: float | None) -> str:
    return "  -  " if rate is None else f"{rate:5.0%}"


def print_table(rows: list[dict]) -> None:
    header = (
        f"{'model':<20}{'scenario':<9}{'door':<13}{'payload':<13}"
        f"{'defense':<22}{'att':>6}{'succ':>7}{'task':>7}{'n':>4}"
    )
    print(header)
    print("-" * len(header))
    for r in rows:
        short_model = (
            r["model"]
            .replace("claude-", "")
            .replace("-20251001", "")
            .replace("-20250929", "")
            .replace("-20251101", "")
        )
        print(
            f"{short_model:<20}{r['scenario']:<9}{r['door']:<13}{r['payload']:<13}"
            f"{r.get('defense', 'none'):<22}{_fmt(r['attempted']):>6}{_fmt(r['succeeded']):>7}"
            f"{_fmt(r['task_success']):>7}{r['n']:>4}"
        )
