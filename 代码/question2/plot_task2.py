#!/usr/bin/env python3
"""
Quick visualization for Task 2 results.
Reads summary.json and runs.csv from question2/results and outputs PNG charts.
"""

import argparse
import json
import csv
import pathlib
import matplotlib.pyplot as plt

# Low-saturation Morandi palette: pale blue, pale purple, deep green, light pink
PALETTE = ["#AFC3D8", "#C7C4DD", "#5E7767", "#F3C7C7"]

def normalize_scenario(value: str) -> str:
    key = value.strip().upper()
    if key in ("1", "A"):
        return "A"
    if key in ("2", "B"):
        return "B"
    if key in ("3", "C"):
        return "C"
    raise ValueError("scenario must be A/B/C or 1/2/3")


def resolve_base_dir(results_arg: str | None, scenario_arg: str) -> pathlib.Path:
    scenario = normalize_scenario(scenario_arg)
    if results_arg:
        return pathlib.Path(results_arg)
    return pathlib.Path(__file__).resolve().parent / "results" / f"scenario_{scenario}"


def load_summary(base: pathlib.Path):
    with open(base / "summary.json", "r", encoding="utf-8") as f:
        return json.load(f)


def load_runs(base: pathlib.Path):
    rows = []
    with open(base / "runs.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows


def plot_completion(summary: dict, outdir: pathlib.Path):
    fig, ax = plt.subplots(figsize=(4, 3))
    t = summary.get("mean_T", 0)
    ax.bar(["mean_T"], [t], color=PALETTE[0])
    ax.set_ylabel("Completion time T* (years)")
    ax.set_title("Task2 Completion Time")
    for i, v in enumerate([t]):
        ax.text(i, v, f"{v:.1f}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(outdir / "task2_Tstar.png", dpi=200)


def plot_failures_launches(summary: dict, outdir: pathlib.Path):
    fig, ax = plt.subplots(figsize=(4.5, 3))
    labels = ["Failures", "Launches"]
    vals = [summary.get("mean_failures", 0), summary.get("mean_launches", 0)]
    ax.bar(labels, vals, color=[PALETTE[2], PALETTE[0]])
    ax.set_ylabel("Count")
    ax.set_title("Task2 Failures vs Launches")
    for i, v in enumerate(vals):
        ax.text(i, v, f"{v:.0f}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(outdir / "task2_failures.png", dpi=200)


def main():
    parser = argparse.ArgumentParser(description="Plot Task2 summary/runs")
    parser.add_argument("--results", type=str, default=None, help="Path to directory containing summary.json/runs.csv")
    parser.add_argument("--scenario", type=str, default="A", help="Scenario A/B/C or 1/2/3")
    args = parser.parse_args()

    base = resolve_base_dir(args.results, args.scenario)
    outdir = pathlib.Path(__file__).resolve().parent
    summary = load_summary(base)
    plot_completion(summary, outdir)
    plot_failures_launches(summary, outdir)
    print(f"Saved plots for scenario {normalize_scenario(args.scenario)} to {outdir}")


if __name__ == "__main__":
    main()
