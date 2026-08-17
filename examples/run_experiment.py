"""Run the Phase 4 baseline sweep and print the aggregated table.

Runs the full matrix (models x scenarios x doors x conditions x repeats) with
defenses off, persists raw results under runs/, and prints per-cell rates.

Run:
    python examples/run_experiment.py [repeats]        # default 5 repeats
    python examples/run_experiment.py --slice sonnet   # cheap Sonnet confirmation
    python examples/run_experiment.py --aggregate runs/<timestamp>
    python examples/run_experiment.py --resume runs/<timestamp>
"""

from __future__ import annotations

import asyncio
import logging
import sys

from mcpoison.experiment import (
    aggregate,
    build_sonnet_slice,
    load_records,
    print_table,
    run_sweep,
    write_aggregate,
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("mcp").setLevel(logging.WARNING)


def _print_and_save(out_dir) -> None:
    rows = aggregate(load_records(out_dir))
    write_aggregate(out_dir, rows)
    print()
    print_table(rows)


async def _main() -> None:
    if len(sys.argv) > 2 and sys.argv[1] == "--aggregate":
        _print_and_save(sys.argv[2])
        return

    if len(sys.argv) > 2 and sys.argv[1] == "--resume":
        out_dir = await run_sweep(resume_dir=sys.argv[2])
        _print_and_save(out_dir)
        return

    if len(sys.argv) > 1 and sys.argv[1] == "--slice":
        name = sys.argv[2] if len(sys.argv) > 2 else "sonnet"
        if name != "sonnet":
            raise SystemExit(f"unknown slice {name!r}; known: sonnet")
        out_dir = await run_sweep(
            cells=build_sonnet_slice(),
            models=["claude-sonnet-4-5-20250929"],
            repeats=5,
            slice_name="sonnet",
        )
        print(f"\nraw results -> {out_dir}")
        _print_and_save(out_dir)
        return

    repeats = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    out_dir = await run_sweep(repeats=repeats)
    print(f"\nraw results -> {out_dir}")
    _print_and_save(out_dir)


if __name__ == "__main__":
    asyncio.run(_main())
