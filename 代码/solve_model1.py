#!/usr/bin/env python3
"""Solve Model 1 (Scenario A/B/C) and export results.

This script implements closed-form solutions for Scenario A/B and
enumeration-based multi-objective optimization for Scenario C.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class Params:
    """Model parameters with units noted in comments."""

    # Global demand (ton)
    M_goal: float = 1.0e8

    # Capacity and rate parameters
    Cap_SE: float = 5.37e5  # ton/yr
    Cap_Rock: float = 125.0  # ton/launch
    f_total: float = 3834.0  # launches/yr
    f_cycle: float = 60.0  # cycles/yr per rocket

    # Cost parameters (USD)
    C_launch: float = 1.5e8  # USD/launch
    C_launch_mode: str = "constant"  # constant | avg15m | decay
    C_launch_C0: float = 1.5e8  # USD/launch at t0, for decay
    C_launch_k: float = 0.096  # 1/yr, for decay
    C_elec_unit: float = 4.15  # USD/ton
    C_maint: float = 1.2e8  # USD/yr
    C_TV_fixed: float = 3.0e8  # USD


def load_config(path: str) -> Dict[str, Any]:
    """Load configuration from YAML or JSON file."""
    if path.endswith(".json"):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "PyYAML is required to load YAML config. Install with: pip install pyyaml"
        ) from exc

    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def apply_overrides(params: Params, overrides: Dict[str, Any]) -> Params:
    """Override params from a dictionary and return new Params."""
    data = asdict(params)
    for key, value in overrides.items():
        if key in data:
            data[key] = value

    # Allow f_total to be a list
    f_total_val = data.get("f_total")
    if isinstance(f_total_val, list):
        data["f_total"] = float(sum(f_total_val))

    return Params(**data)


def validate_params(params: Params) -> None:
    """Validate parameter constraints."""
    if params.Cap_SE <= 0:
        raise ValueError("Cap_SE must be > 0")
    if params.Cap_Rock <= 0:
        raise ValueError("Cap_Rock must be > 0")
    if params.f_total <= 0:
        raise ValueError("f_total must be > 0")
    if params.f_cycle <= 0:
        raise ValueError("f_cycle must be > 0")

    if params.C_launch_mode not in {"constant", "avg15m", "decay"}:
        raise ValueError("C_launch_mode must be constant, avg15m, or decay")


def cost_per_launch(T: np.ndarray | float, params: Params) -> np.ndarray | float:
    """Return launch cost (USD/launch) depending on mode."""
    mode = params.C_launch_mode
    if mode == "avg15m":
        return 1.5e7
    if mode == "decay":
        # Average cost over [t0, t0 + T] using exponential decay.
        # Average = (C0 / (k * T)) * (1 - exp(-k * T))
        C0 = params.C_launch_C0
        k = params.C_launch_k
        if isinstance(T, np.ndarray):
            T_safe = np.where(T <= 0, 1.0, T)
            avg = (C0 / (k * T_safe)) * (1.0 - np.exp(-k * T_safe))
            avg = np.where(T <= 0, C0, avg)
            return avg
        if T <= 0:
            return C0
        if k == 0:
            return C0
        return (C0 / (k * T)) * (1.0 - math.exp(-k * T))
    return params.C_launch


def scenario_a(params: Params) -> Dict[str, Any]:
    """Closed-form solution for Scenario A (Pure Elevator)."""
    M_se = params.M_goal
    T = M_se / params.Cap_SE
    N_rock = int(math.ceil(params.Cap_SE / (params.f_cycle * params.Cap_Rock)))
    C_launch = float(cost_per_launch(T, params))

    cost_launch = C_launch * N_rock
    cost_elec = params.C_elec_unit * M_se
    cost_maint = params.C_maint * T
    cost_fixed = params.C_TV_fixed
    C_total = cost_launch + cost_elec + cost_maint + cost_fixed

    return {
        "T": T,
        "N_Rock": N_rock,
        "M_SE": M_se,
        "cost_launch": cost_launch,
        "cost_elec": cost_elec,
        "cost_maint": cost_maint,
        "cost_fixed": cost_fixed,
        "C_total": C_total,
    }


def scenario_b(params: Params) -> Dict[str, Any]:
    """Closed-form solution for Scenario B (Pure Rocket)."""
    N_rock = int(math.ceil(params.M_goal / params.Cap_Rock))
    T = N_rock / params.f_total
    C_launch = float(cost_per_launch(T, params))
    cost_launch = C_launch * N_rock
    cost_maint = params.C_maint * T
    C_total = cost_launch + cost_maint

    return {
        "T": T,
        "N_Rock": N_rock,
        "cost_launch": cost_launch,
        "cost_maint": cost_maint,
        "C_total": C_total,
    }


def pareto_front_mask(T: np.ndarray, C: np.ndarray) -> np.ndarray:
    """Compute Pareto front mask for minimizing (T, C)."""
    order = np.lexsort((C, T))
    best_c = np.inf
    mask = np.zeros_like(T, dtype=bool)
    for idx in order:
        if C[idx] < best_c:
            mask[idx] = True
            best_c = C[idx]
    return mask


def weighted_sum_solutions(
    T: np.ndarray,
    C: np.ndarray,
    alpha_grid: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """Return indices and objective values for weighted-sum solutions."""
    T_ref = float(np.max(T)) if np.max(T) > 0 else 1.0
    C_ref = float(np.max(C)) if np.max(C) > 0 else 1.0
    indices = np.zeros_like(alpha_grid, dtype=int)
    J_values = np.zeros_like(alpha_grid, dtype=float)

    for i, alpha in enumerate(alpha_grid):
        J = alpha * (T / T_ref) + (1.0 - alpha) * (C / C_ref)
        min_J = float(np.min(J))
        cand = np.where(np.isclose(J, min_J, rtol=1e-12, atol=1e-12))[0]
        if cand.size > 1:
            best = cand[np.lexsort((C[cand], T[cand]))[0]]
        else:
            best = cand[0]
        indices[i] = int(best)
        J_values[i] = float(J[best])
    return indices, J_values


def sample_indices(total: int, max_count: int) -> np.ndarray:
    """Deterministically sample indices if total exceeds max_count."""
    if total <= max_count:
        return np.arange(total, dtype=int)
    return np.unique(np.linspace(0, total - 1, max_count).astype(int))


def save_csv(path: str, header: List[str], data: np.ndarray) -> None:
    """Save numpy array to CSV with header."""
    fmt = ["%d"] + ["%.10g"] * (data.shape[1] - 1)
    np.savetxt(path, data, delimiter=",", header=",".join(header), comments="", fmt=fmt)


def scenario_c(
    params: Params,
    alpha_grid: np.ndarray,
    export_all: bool,
    max_export: int,
) -> Dict[str, Any]:
    """Enumerate and solve Scenario C (Hybrid) with Pareto analysis."""
    N_low = int(math.ceil(params.Cap_SE / (params.f_cycle * params.Cap_Rock)))
    N_high = int(math.ceil(params.M_goal / params.Cap_Rock))
    if N_low < 0:
        N_low = 0
    if N_low > N_high:
        N_low = N_high

    N = np.arange(N_low, N_high + 1, dtype=int)
    M_direct = N.astype(float) * params.Cap_Rock
    M_se = np.maximum(0.0, params.M_goal - M_direct)

    R = np.minimum(params.Cap_SE, N.astype(float) * params.f_cycle * params.Cap_Rock)

    T_remain = np.zeros_like(R, dtype=float)
    mask_R_pos = R > 0
    T_remain[mask_R_pos] = M_se[mask_R_pos] / R[mask_R_pos]
    mask_R_zero = ~mask_R_pos
    T_remain[mask_R_zero] = np.where(M_se[mask_R_zero] == 0.0, 0.0, np.inf)

    T_deploy = N.astype(float) / params.f_total
    T = np.maximum(T_deploy, T_remain)

    feasible_mask = np.isfinite(T)
    N_f = N[feasible_mask]
    M_se_f = M_se[feasible_mask]
    R_f = R[feasible_mask]
    T_f = T[feasible_mask]
    T_deploy_f = T_deploy[feasible_mask]
    T_remain_f = T_remain[feasible_mask]
    M_direct_f = M_direct[feasible_mask]

    C_launch = cost_per_launch(T_f, params)
    C_total = (
        C_launch * N_f
        + params.C_elec_unit * M_se_f
        + params.C_maint * T_f
        + params.C_TV_fixed
    )

    pareto_mask = pareto_front_mask(T_f, C_total)

    # Weighted sum solutions
    ws_indices, ws_J = weighted_sum_solutions(T_f, C_total, alpha_grid)

    # Knee point on Pareto front
    T_p = T_f[pareto_mask]
    C_p = C_total[pareto_mask]
    N_p = N_f[pareto_mask]
    M_se_p = M_se_f[pareto_mask]
    R_p = R_f[pareto_mask]

    T_min, T_max = float(np.min(T_p)), float(np.max(T_p))
    C_min, C_max = float(np.min(C_p)), float(np.max(C_p))
    if T_max > T_min:
        T_norm = (T_p - T_min) / (T_max - T_min)
    else:
        T_norm = np.zeros_like(T_p)
    if C_max > C_min:
        C_norm = (C_p - C_min) / (C_max - C_min)
    else:
        C_norm = np.zeros_like(C_p)
    dist = np.sqrt(T_norm**2 + C_norm**2)
    knee_idx = int(np.argmin(dist))

    recommended = {
        "N_Rock": int(N_p[knee_idx]),
        "T": float(T_p[knee_idx]),
        "C_total": float(C_p[knee_idx]),
        "M_SE": float(M_se_p[knee_idx]),
        "R": float(R_p[knee_idx]),
        "method": "normalized_distance_to_ideal",
    }

    # See if recommended is in weighted-sum set
    matched_alpha: Optional[float] = None
    for alpha, idx in zip(alpha_grid, ws_indices):
        if int(N_f[idx]) == recommended["N_Rock"]:
            matched_alpha = float(alpha)
            break
    if matched_alpha is not None:
        recommended["alpha"] = matched_alpha

    # Prepare export data
    all_data = np.column_stack(
        [
            N_f,
            T_f,
            C_total,
            M_se_f,
            R_f,
            T_deploy_f,
            T_remain_f,
            M_direct_f,
        ]
    )
    pareto_data = np.column_stack(
        [
            N_p,
            T_p,
            C_p,
            M_se_p,
            R_p,
            T_deploy_f[pareto_mask],
            T_remain_f[pareto_mask],
            M_direct_f[pareto_mask],
        ]
    )

    ws_data = np.column_stack(
        [
            alpha_grid,
            N_f[ws_indices],
            T_f[ws_indices],
            C_total[ws_indices],
            M_se_f[ws_indices],
            R_f[ws_indices],
            ws_J,
        ]
    )

    if export_all:
        export_indices = np.arange(all_data.shape[0], dtype=int)
    else:
        export_indices = sample_indices(all_data.shape[0], max_export)

    return {
        "N_low": N_low,
        "N_high": N_high,
        "feasible_count": int(all_data.shape[0]),
        "pareto_count": int(pareto_data.shape[0]),
        "all_data": all_data[export_indices],
        "pareto_data": pareto_data,
        "ws_data": ws_data,
        "recommended": recommended,
        "exported_count": int(export_indices.size),
    }


def plot_pareto(
    path: str,
    all_data: np.ndarray,
    pareto_data: np.ndarray,
    recommended: Dict[str, Any],
    ws_data: np.ndarray,
) -> None:
    """Plot Pareto scatter and annotate key points."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    T_all = all_data[:, 1]
    C_all = all_data[:, 2]
    T_p = pareto_data[:, 1]
    C_p = pareto_data[:, 2]

    plt.figure(figsize=(8, 6))
    plt.scatter(T_all, C_all, s=10, alpha=0.2, label="feasible")
    plt.scatter(T_p, C_p, s=18, alpha=0.8, label="pareto")

    # Recommended point
    plt.scatter(recommended["T"], recommended["C_total"], s=60, marker="*", label="recommended")
    plt.annotate(
        "recommended",
        (recommended["T"], recommended["C_total"]),
        textcoords="offset points",
        xytext=(6, 6),
    )

    # Alpha extremes: alpha=0 and alpha=1
    if ws_data.shape[0] > 0:
        alpha_vals = ws_data[:, 0]
        idx_alpha0 = int(np.argmin(np.abs(alpha_vals - 0.0)))
        idx_alpha1 = int(np.argmin(np.abs(alpha_vals - 1.0)))
        for idx, label in [(idx_alpha0, "alpha=0"), (idx_alpha1, "alpha=1")]:
            plt.scatter(ws_data[idx, 2], ws_data[idx, 3], s=45, marker="D", label=label)
            plt.annotate(
                label,
                (ws_data[idx, 2], ws_data[idx, 3]),
                textcoords="offset points",
                xytext=(6, -8),
            )

    plt.xlabel("T (years)")
    plt.ylabel("C (USD)")
    plt.title("Scenario C Pareto Frontier")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Solve Model 1 scenarios A/B/C")
    parser.add_argument("--config", type=str, default=None, help="Path to YAML/JSON config")
    parser.add_argument("--no-plot", action="store_true", help="Disable pareto plot")
    parser.add_argument("--alpha-steps", type=int, default=21, help="Number of alpha steps")
    parser.add_argument("--export-all", action="store_true", help="Export all feasible points")
    args = parser.parse_args()

    params = Params()
    config: Dict[str, Any] = {}
    if args.config:
        config = load_config(args.config)
        params = apply_overrides(params, config)

    validate_params(params)

    if "alpha_grid" in config:
        alpha_grid = np.array(config["alpha_grid"], dtype=float)
    else:
        alpha_grid = np.linspace(0.0, 1.0, int(args.alpha_steps))

    # Results directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(base_dir)
    results_dir = os.path.join(root_dir, "results", "model1")
    os.makedirs(results_dir, exist_ok=True)

    # Scenario A/B
    res_a = scenario_a(params)
    res_b = scenario_b(params)

    # Scenario C
    res_c = scenario_c(params, alpha_grid, args.export_all, max_export=200000)

    # Export CSVs
    header_common = [
        "N_Rock",
        "T",
        "C",
        "M_SE",
        "R",
        "T_deploy",
        "T_remain",
        "M_direct",
    ]
    save_csv(
        os.path.join(results_dir, "pareto_all_feasible.csv"),
        header_common,
        res_c["all_data"],
    )
    save_csv(
        os.path.join(results_dir, "pareto_front.csv"),
        header_common,
        res_c["pareto_data"],
    )

    header_ws = ["alpha", "N_Rock", "T", "C", "M_SE", "R", "J"]
    save_csv(
        os.path.join(results_dir, "weighted_sum_solutions.csv"),
        header_ws,
        res_c["ws_data"],
    )

    # Plot
    if not args.no_plot:
        plot_pareto(
            os.path.join(results_dir, "pareto.png"),
            res_c["all_data"],
            res_c["pareto_data"],
            res_c["recommended"],
            res_c["ws_data"],
        )

    # JSON summary
    summary = {
        "parameters": asdict(params),
        "scenario_a": res_a,
        "scenario_b": res_b,
        "scenario_c": {
            "N_low": res_c["N_low"],
            "N_high": res_c["N_high"],
            "feasible_count": res_c["feasible_count"],
            "pareto_count": res_c["pareto_count"],
            "exported_count": res_c["exported_count"],
            "recommended": res_c["recommended"],
        },
    }
    with open(
        os.path.join(results_dir, "scenario_summary.json"),
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(summary, f, indent=2)

    # Console summary
    print("Scenario A:")
    print(f"  T_A*: {res_a['T']:.6g} yr, N_A*: {res_a['N_Rock']}, C_A: {res_a['C_total']:.6g} USD")
    print("Scenario B:")
    print(f"  T_B*: {res_b['T']:.6g} yr, N_B*: {res_b['N_Rock']}, C_B: {res_b['C_total']:.6g} USD")
    print("Scenario C:")
    rec = res_c["recommended"]
    print(
        "  feasible: {fc}, pareto: {pc}, recommended N: {n}, T: {t:.6g}, C: {c:.6g}".format(
            fc=res_c["feasible_count"],
            pc=res_c["pareto_count"],
            n=rec["N_Rock"],
            t=rec["T"],
            c=rec["C_total"],
        )
    )


if __name__ == "__main__":
    main()
