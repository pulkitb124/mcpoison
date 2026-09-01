"""Phase 6 analysis: turn raw run records into the figures the writeup uses.

Everything here is pure aggregation over the JSONL that `experiment.py` writes,
plus matplotlib rendering. Two families of figure:

  * Attack-success heatmap (Phase 4): how often each payload style lands, per
    scenario x door, with defenses off. This is the "shape of the problem".
  * Defense figures (Phase 5): a per-cell reduction heatmap (which defense
    closes which leak) and a safety/utility scatter (attack success vs. the
    task success it costs). This is the "what to do about it".

Kept deliberately dependency-light: matplotlib only, no pandas/seaborn.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless; we only ever save PNGs
import matplotlib.pyplot as plt

from .experiment import aggregate, load_records

STYLE_ORDER = ["(baseline)", "blunt", "authority", "remediation", "covert", "obfuscated"]
DEFENSE_ORDER = ["none", "instruction_hierarchy", "spotlight", "sanitize"]
DEFENSE_LABEL = {
    "none": "none",
    "instruction_hierarchy": "instruction\nhierarchy",
    "spotlight": "spotlight",
    "sanitize": "sanitize",
}
HAIKU = "claude-haiku-4-5-20251001"


def _rate_lookup(rows: list[dict], field: str) -> dict[tuple, float | None]:
    """Map (scenario, door, payload, defense) -> rate for one metric."""
    return {
        (r["scenario"], r["door"], r["payload"], r.get("defense", "none")): r[field]
        for r in rows
    }


def _heatmap(ax, matrix, row_labels, col_labels, title, cmap="Reds"):
    data = [[(v if v is not None else 0.0) for v in row] for row in matrix]
    ax.imshow(data, cmap=cmap, vmin=0.0, vmax=1.0, aspect="auto")
    ax.set_xticks(range(len(col_labels)))
    ax.set_xticklabels(col_labels, rotation=30, ha="right", fontsize=9)
    ax.set_yticks(range(len(row_labels)))
    ax.set_yticklabels(row_labels, fontsize=9)
    ax.set_title(title, fontsize=11)
    for i, row in enumerate(matrix):
        for j, v in enumerate(row):
            label = "-" if v is None else f"{v:.0%}"
            shade = 0.0 if v is None else v
            ax.text(
                j, i, label, ha="center", va="center", fontsize=9,
                color="white" if shade > 0.55 else "black",
            )


# --- Phase 4: attack-success heatmap -------------------------------------------


def attack_heatmap(records: list[dict], out_path: Path) -> Path:
    rows = [r for r in aggregate(records) if r["model"] == HAIKU and r.get("defense", "none") == "none"]
    succ = _rate_lookup(rows, "succeeded")
    cells = [("devops", "output"), ("devops", "description"),
             ("support", "output"), ("support", "description")]
    row_labels = [f"{s} / {d}" for s, d in cells]
    matrix = [[succ.get((s, d, style, "none")) for style in STYLE_ORDER] for s, d in cells]

    fig, ax = plt.subplots(figsize=(8, 3.6))
    _heatmap(ax, matrix, row_labels, STYLE_ORDER,
             "Successful exfiltration rate (Haiku 4.5, R=5, no defense)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


# --- Phase 5: which defense closes which leak ----------------------------------


def _attacked_cells(rows: list[dict]) -> list[tuple[str, str, str]]:
    seen = []
    for r in rows:
        key = (r["scenario"], r["door"], r["payload"])
        if r["payload"] != "(baseline)" and key not in seen:
            seen.append(key)
    return seen


def defense_reduction_heatmap(records: list[dict], out_path: Path) -> Path:
    rows = aggregate(records)
    succ = _rate_lookup(rows, "succeeded")
    attacked = _attacked_cells([r for r in rows if r.get("defense", "none") == "none"])
    row_labels = [f"{s} / {d} / {p}" for s, d, p in attacked]
    matrix = [[succ.get((s, d, p, dfn)) for dfn in DEFENSE_ORDER] for s, d, p in attacked]

    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    _heatmap(ax, matrix, row_labels, [DEFENSE_LABEL[d] for d in DEFENSE_ORDER],
             "Successful exfiltration rate by defense (Haiku 4.5, R=5)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


# --- Phase 5: safety / utility tradeoff ----------------------------------------


def tradeoff_summary(records: list[dict]) -> list[dict]:
    """Per defense: mean attack success on attacked cells, mean task success on
    both the attacked cells and the clean baselines."""
    rows = aggregate(records)
    out: list[dict] = []
    for dfn in DEFENSE_ORDER:
        drows = [r for r in rows if r.get("defense", "none") == dfn]
        attacked = [r for r in drows if r["payload"] != "(baseline)"]
        baseline = [r for r in drows if r["payload"] == "(baseline)"]

        def mean(rs, field):
            vals = [r[field] for r in rs if r[field] is not None]
            return sum(vals) / len(vals) if vals else None

        out.append({
            "defense": dfn,
            "attack_success": mean(attacked, "succeeded"),
            "task_success_attacked": mean(attacked, "task_success"),
            "task_success_baseline": mean(baseline, "task_success"),
        })
    return out


def tradeoff_scatter(records: list[dict], out_path: Path) -> Path:
    summary = tradeoff_summary(records)
    fig, ax = plt.subplots(figsize=(6.8, 5.4))
    seen: dict[tuple, int] = {}
    for row in summary:
        x = (row["task_success_baseline"] or 0.0) * 100
        y = (row["attack_success"] or 0.0) * 100
        # stack labels (and nudge markers) when defenses land on the same point
        stack = seen.get((round(x), round(y)), 0)
        seen[(round(x), round(y))] = stack + 1
        ax.scatter(x + stack * 0.6, y, s=130, zorder=3)
        ax.annotate(
            row["defense"].replace("_", " "),
            (x, y),
            textcoords="offset points",
            xytext=(10, 6 - stack * 14),
            fontsize=9,
        )
    ax.set_xlabel("Task success on clean baselines  (utility %)")
    ax.set_ylabel("Successful exfiltration on attacked cells  (attack %)")
    ax.set_title("Safety vs. utility (Haiku 4.5, R=5)\nbottom-right is best")
    ax.set_xlim(0, 112)
    ax.set_ylim(-6, 106)
    ax.grid(True, alpha=0.3, zorder=0)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def defense_bars(records: list[dict], out_path: Path) -> Path:
    summary = tradeoff_summary(records)
    labels = [DEFENSE_LABEL[r["defense"]] for r in summary]
    attack = [(r["attack_success"] or 0.0) * 100 for r in summary]
    task = [(r["task_success_baseline"] or 0.0) * 100 for r in summary]
    x = range(len(labels))
    w = 0.38

    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.bar([i - w / 2 for i in x], attack, w, label="attack success (attacked)", color="#c0392b")
    ax.bar([i + w / 2 for i in x], task, w, label="task success (baseline)", color="#27ae60")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("rate (%)")
    ax.set_ylim(0, 105)
    ax.set_title("Each defense: attack cut vs. task kept (Haiku 4.5, R=5)")
    ax.legend(fontsize=9)
    for i, v in enumerate(attack):
        ax.text(i - w / 2, v + 2, f"{v:.0f}", ha="center", fontsize=8)
    for i, v in enumerate(task):
        ax.text(i + w / 2, v + 2, f"{v:.0f}", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def generate_all(phase4_dir: str | Path, phase5_dir: str | Path, out_dir: str | Path) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    made: list[Path] = []
    made.append(attack_heatmap(load_records(phase4_dir), out_dir / "phase4_attack_heatmap.png"))
    p5 = load_records(phase5_dir)
    made.append(defense_reduction_heatmap(p5, out_dir / "phase5_reduction_heatmap.png"))
    made.append(tradeoff_scatter(p5, out_dir / "phase5_tradeoff.png"))
    made.append(defense_bars(p5, out_dir / "phase5_defense_bars.png"))
    return made
