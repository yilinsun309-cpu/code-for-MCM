"""Compute Task 2 coupling efficiency coefficients for scenarios A/B/C."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Iterable, List

import matplotlib.pyplot as plt

from Q2 import Task2Params, apply_overrides, load_config


SCENARIO_PROGRAMS: Dict[str, List[int]] = {
    "A": [3, 4],
    "B": [2, 3, 5],
    "C": [2, 3, 4],
}

SCENARIO_LABELS: Dict[str, str] = {
    "A": "Scenario A",
    "B": "Scenario B",
    "C": "Scenario C",
}


def coupling_efficiency(p_fail: Dict[int, float], programs: Iterable[int]) -> float:
    coeff = 1.0
    for prog in programs:
        pf = float(p_fail.get(int(prog), 0.0))
        if pf < 0.0 or pf >= 1.0:
            raise ValueError(f"p_fail for program {prog} must be in [0, 1)")
        coeff *= (1.0 - pf)
    return coeff


def build_params(config_path: str | None) -> Task2Params:
    params = Task2Params()
    if config_path:
        overrides = load_config(config_path)
        params = apply_overrides(params, overrides)
    return params


def write_outputs(outdir: Path, results: Dict[str, float]) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    json_path = outdir / "coupling_efficiency.json"
    csv_path = outdir / "coupling_efficiency.csv"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["scenario", "coupling_efficiency"])
        for key in ("A", "B", "C"):
            writer.writerow([key, results[key]])


def plot_results(outdir: Path, results: Dict[str, float]) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    labels = [SCENARIO_LABELS[k] for k in ("A", "B", "C")]
    values = [results[k] for k in ("A", "B", "C")]

    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    bars = ax.bar(labels, values, color=["#4C78A8", "#F58518", "#54A24B"], edgecolor="black")
    min_val = min(values)
    max_val = max(values)
    span = max_val - min_val
    pad = 0.01 if span < 0.05 else 0.03
    ymin = max(0.0, min_val - pad)
    ymax = min(1.05, max_val + pad)
    ax.set_ylim(ymin, ymax)
    ax.set_ylabel("Coupling efficiency (eta_c)")
    ax.set_title("Task 2 Coupling Efficiency by Scenario")
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    text_offset = (ymax - ymin) * 0.03
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            val + text_offset,
            f"{val:.4f}",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    fig.tight_layout()
    out_path = outdir / "coupling_efficiency.png"
    fig.savefig(out_path, dpi=200)
    plt.close(fig)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute Task 2 coupling efficiency coefficients for scenarios A/B/C"
    )
    parser.add_argument("--config", type=str, default=None, help="Optional JSON config")
    parser.add_argument("--outdir", type=str, default="results/task2", help="Output directory")
    parser.add_argument("--no-plot", action="store_true", help="Skip PNG plot")
    args = parser.parse_args()

    params = build_params(args.config)
    p_fail = params.p_fail

    results = {
        key: coupling_efficiency(p_fail, programs)
        for key, programs in SCENARIO_PROGRAMS.items()
    }

    print(json.dumps({"coupling_efficiency": results}, indent=2))

    outdir = Path(args.outdir)
    write_outputs(outdir, results)
    if not args.no_plot:
        plot_results(outdir, results)


if __name__ == "__main__":
    main()
