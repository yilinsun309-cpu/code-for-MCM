#!/usr/bin/env python3
"""
Visualization for Task 3 one-year water supply results.
Reads summary.json under question3/results/scenario_{A,B,C}.
"""

import argparse
import json
import pathlib
from typing import List
import matplotlib.pyplot as plt

# Low-saturation Morandi palette: pale blue, pale purple, deep green, light pink
PALETTE = ["#AFC3D8", "#C7C4DD", "#5E7767", "#F3C7C7"]
OUTDIR = pathlib.Path(__file__).resolve().parent


def normalize_scenario(value: str) -> str:
    key = value.strip().upper()
    if key in ("1", "A"):
        return "A"
    if key in ("2", "B"):
        return "B"
    if key in ("3", "C"):
        return "C"
    raise ValueError("scenario must be A/B/C or 1/2/3")


def load_summary(base: pathlib.Path, scenario: str) -> dict:
    path = base / f"scenario_{scenario}" / "summary.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def collect_scenarios(base: pathlib.Path, scenarios: List[str]) -> dict:
    data = {}
    for s in scenarios:
        summary = load_summary(base, s)
        data[s] = {
            "S_moon_star": summary.get("S_moon_star_ton", 0.0),
            "S_moon_min": summary.get("S_moon_min_ton", 0.0),
            "max_gap_days": summary.get("max_gap_quantile_days", 0.0),
            "mean_failures": summary.get("mean_failures", 0.0),
            "mean_launches": summary.get("mean_launches", 0.0),
        }
    return data


def bar_metric(scenarios: dict, metric: str, ylabel: str, fname: str, fmt: str = "{:.0f}"):
    labels = list(scenarios.keys())
    vals = [scenarios[s][metric] for s in labels]
    fig, ax = plt.subplots(figsize=(5, 3))
    ax.bar(labels, vals, color=PALETTE[: len(labels)])
    ax.set_ylabel(ylabel)
    ax.set_title(metric)
    for i, v in enumerate(vals):
        ax.text(i, v, fmt.format(v), ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUTDIR / fname, dpi=200)


def main():
    parser = argparse.ArgumentParser(description="Plot Task3 summaries from results directory")
    parser.add_argument("--results", type=str, default=None, help="Base directory containing scenario_*/summary.json")
    parser.add_argument("--scenarios", type=str, default="A,B,C", help="Comma-separated scenarios to plot")
    args = parser.parse_args()

    base = pathlib.Path(args.results) if args.results else pathlib.Path(__file__).resolve().parent / "results"
    scenarios = [normalize_scenario(s) for s in args.scenarios.split(",") if s.strip()]
    scenario_data = collect_scenarios(base, scenarios)

    bar_metric(scenario_data, "S_moon_star", "Safety stock S_moon* (ton)", "task3_Smoon_star.png")
    bar_metric(scenario_data, "max_gap_days", "Max gap (days)", "task3_max_gap.png", "{:.2f}")
    bar_metric(scenario_data, "mean_failures", "Mean failures", "task3_failures.png", "{:.0f}")
    print(f"Saved Task3 figures for {', '.join(scenarios)} to {OUTDIR}")


if __name__ == "__main__":
    main()
