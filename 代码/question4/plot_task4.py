#!/usr/bin/env python3
"""
Quick bar plot for Task 4 environmental impact (total CO2e).
Reads scenario_{A,B,C}/summary.json under question4/results by default.
"""

import argparse
import json
import pathlib
from typing import List
import matplotlib.pyplot as plt

OUTDIR = pathlib.Path(__file__).resolve().parent
# Low-saturation Morandi palette
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


def load_impact(base: pathlib.Path, scenarios: List[str]) -> dict:
    data = {}
    for s in scenarios:
        path = base / f"scenario_{s}" / "summary.json"
        with open(path, "r", encoding="utf-8") as f:
            summary = json.load(f)
        data[s] = summary.get("total_co2e_ton", 0.0)
    return data


def main():
    parser = argparse.ArgumentParser(description="Plot Task4 environmental impact")
    parser.add_argument("--results", type=str, default=None, help="Base directory containing scenario_*/summary.json")
    parser.add_argument("--scenarios", type=str, default="A,B,C", help="Comma-separated scenarios to plot")
    args = parser.parse_args()

    base = pathlib.Path(args.results) if args.results else pathlib.Path(__file__).resolve().parent / "results"
    scenarios = [normalize_scenario(s) for s in args.scenarios.split(",") if s.strip()]
    impact = load_impact(base, scenarios)

    labels = list(impact.keys())
    vals = [impact[k] for k in labels]
    fig, ax = plt.subplots(figsize=(5, 3))
    colors = PALETTE[: len(labels)]
    ax.bar(labels, vals, color=colors)
    ax.set_ylabel("Total CO2e (ton)")
    ax.set_title("Task4 Environmental Impact")
    for i, v in enumerate(vals):
        txt = f"{v:,.0f}"
        ax.text(i, v, txt, ha="center", va="bottom", fontsize=8, rotation=45)
    fig.tight_layout()
    fig.savefig(OUTDIR / "task4_Eimpact.png", dpi=200)
    print("Saved task4_Eimpact.png")


if __name__ == "__main__":
    main()
