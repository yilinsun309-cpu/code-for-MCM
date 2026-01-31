#!/usr/bin/env python3
"""Monte Carlo perturbation simulation for imperfect operations."""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple


DEFAULT_CONFIG: Dict[str, Any] = {
    "base": {
        "M_goal": 1.0e8,
        "Cap_SE": 5.37e5,
        "Cap_rock": 125.0,
        "f_total": 300.0,
        "C_launch": 1.5e8,
        "C_elec_unit": 4.15,
        "C_maint": 1.2e8,
        "C_TV_fixed": 3.0e8,
    },
    "elec_formula": {
        "use_formula": False,
        "N_SE": 1.0,
        "E_week": 0.0,
        "P_elec": 0.0,
    },
    "uncertainty": {
        "oscillation": {
            "model": "angle",
            "theta1": 0.4,
            "theta2": 0.7,
            "r": 0.7,
            "theta_mu": 0.55,
            "theta_sigma": 0.12,
            "samples": 52,
            "p1_mean": 0.2,
            "p2_mean": 0.05,
            "p_conc": 120.0,
        },
        "rocket": {
            "p_f": 0.05,
            "p_p": 0.07,
            "alpha": 0.3,
            "p_conc": 200.0,
            "D_mean": 0.1,
            "D_sigma": 0.02,
            "C_mishap": 0.0,
        },
        "elevator": {
            "MTBF": 2.0,
            "MTTR": 0.1,
            "MTBF_sigma": 0.3,
            "MTTR_sigma": 0.05,
            "mu": 0.4,
            "mu_cut": 0.05,
            "beta": 0.7,
            "repair_severe_years": 0.5,
            "C_damage_minor": 0.0,
            "C_damage_severe": 0.0,
        },
    },
}


@dataclass
class TrialResult:
    T: float
    cost: float
    N_rock: int
    f_osc: float
    f_dmg: float
    A_mech: float
    A_rocket: float
    M_rocket_target: float


def deep_update(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_update(base[key], value)
        else:
            base[key] = value
    return base


def load_config(path: Path | None) -> Dict[str, Any]:
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    if path is None:
        return config
    with path.open("r", encoding="utf-8") as handle:
        user_cfg = json.load(handle)
    return deep_update(config, user_cfg)


def compute_elec_unit(config: Dict[str, Any]) -> float:
    base = config["base"]
    formula = config["elec_formula"]
    if not formula.get("use_formula"):
        return float(base["C_elec_unit"])
    cap_se = float(base["Cap_SE"])
    n_se = float(formula["N_SE"])
    e_week = float(formula["E_week"])
    p_elec = float(formula["P_elec"])
    return (n_se * e_week * 52.0 * 1000.0 * p_elec) / cap_se


def sample_beta(mean: float, conc: float, rng: random.Random) -> float:
    mean = min(max(mean, 1e-6), 1.0 - 1e-6)
    conc = max(conc, 2.0)
    a = mean * conc
    b = (1.0 - mean) * conc
    return rng.betavariate(a, b)


def sample_positive_normal(mu: float, sigma: float, rng: random.Random) -> float:
    if sigma <= 0:
        return max(mu, 1e-6)
    value = rng.gauss(mu, sigma)
    return max(value, 1e-6)


def sample_poisson(mu: float, rng: random.Random) -> int:
    if mu <= 0:
        return 0
    limit = math.exp(-mu)
    k = 0
    prod = 1.0
    while prod > limit:
        k += 1
        prod *= rng.random()
    return k - 1


def oscillation_factor(cfg: Dict[str, Any], rng: random.Random) -> float:
    model = cfg.get("model", "angle")
    theta1 = float(cfg["theta1"])
    theta2 = float(cfg["theta2"])
    r = float(cfg["r"])
    if model == "p1p2":
        p1 = sample_beta(float(cfg["p1_mean"]), float(cfg["p_conc"]), rng)
        p2 = sample_beta(float(cfg["p2_mean"]), float(cfg["p_conc"]), rng)
        p2 = min(p2, p1)
        return (1.0 - p1) + (p1 - p2) * r
    samples = int(cfg.get("samples", 52))
    theta_mu = float(cfg["theta_mu"])
    theta_sigma = float(cfg["theta_sigma"])
    total = 0.0
    for _ in range(samples):
        theta = abs(rng.gauss(theta_mu, theta_sigma))
        if theta <= theta1:
            total += 1.0
        elif theta <= theta2:
            total += r
    return total / float(samples)


def elevator_damage_factor(cfg: Dict[str, Any], rng: random.Random) -> Tuple[float, float, float]:
    mu = float(cfg["mu"])
    mu_cut = float(cfg["mu_cut"])
    beta = float(cfg["beta"])
    n_cut = sample_poisson(mu_cut, rng)
    if n_cut > 0:
        return 0.0, float(cfg["C_damage_severe"]), float(cfg["repair_severe_years"])
    n_total = sample_poisson(mu, rng)
    if n_total > 0:
        return beta, float(cfg["C_damage_minor"]), 0.0
    return 1.0, 0.0, 0.0


def mech_availability(cfg: Dict[str, Any], rng: random.Random) -> float:
    mtbf = sample_positive_normal(float(cfg["MTBF"]), float(cfg["MTBF_sigma"]), rng)
    mttr = sample_positive_normal(float(cfg["MTTR"]), float(cfg["MTTR_sigma"]), rng)
    return mtbf / (mtbf + mttr)


def rocket_rates(cfg: Dict[str, Any], f_total: float, rng: random.Random) -> Tuple[float, float, float]:
    p_f = sample_beta(float(cfg["p_f"]), float(cfg["p_conc"]), rng)
    p_p = sample_beta(float(cfg["p_p"]), float(cfg["p_conc"]), rng)
    p_p = min(p_p, 0.95 - p_f)
    p_mishap = p_f + p_p
    d_mean = float(cfg["D_mean"])
    d_sigma = float(cfg["D_sigma"])
    downtime = sample_positive_normal(d_mean, d_sigma, rng)
    a_rocket = 1.0 / (1.0 + f_total * p_mishap * downtime)
    return p_f, p_p, a_rocket


def percentile(values: List[float], q: float) -> float:
    if not values:
        return float("nan")
    values = sorted(values)
    if len(values) == 1:
        return values[0]
    pos = (len(values) - 1) * (q / 100.0)
    lower = math.floor(pos)
    upper = math.ceil(pos)
    if lower == upper:
        return values[int(pos)]
    weight = pos - lower
    return values[lower] * (1.0 - weight) + values[upper] * weight


def simulate(config: Dict[str, Any], trials: int, seed: int, m_se: float) -> List[TrialResult]:
    rng = random.Random(seed)
    base = config["base"]
    uncertainty = config["uncertainty"]
    m_goal = float(base["M_goal"])
    cap_se = float(base["Cap_SE"])
    cap_rock = float(base["Cap_rock"])
    f_total = float(base["f_total"])
    c_launch = float(base["C_launch"])
    c_maint = float(base["C_maint"])
    c_fixed = float(base["C_TV_fixed"])
    c_elec_unit = compute_elec_unit(config)
    m_rocket_target = max(m_goal - m_se, 0.0)

    results: List[TrialResult] = []
    for _ in range(trials):
        f_osc = oscillation_factor(uncertainty["oscillation"], rng)
        f_dmg, damage_cost, repair_years = elevator_damage_factor(uncertainty["elevator"], rng)
        a_mech = mech_availability(uncertainty["elevator"], rng)
        cap_se_eff = cap_se * a_mech * f_osc * f_dmg
        if cap_se_eff <= 0.0 and m_se > 0:
            t_se = float("inf")
        else:
            t_se = 0.0 if m_se <= 0 else (m_se / cap_se_eff)
        if math.isfinite(t_se):
            t_se += repair_years

        p_f, p_p, a_rocket = rocket_rates(uncertainty["rocket"], f_total, rng)
        alpha = float(uncertainty["rocket"]["alpha"])
        m_eff = cap_rock * (1.0 - p_f - alpha * p_p)
        m_eff = max(m_eff, 1e-6)
        n_rock = math.ceil(m_rocket_target / m_eff) if m_rocket_target > 0 else 0
        f_eff = f_total * a_rocket
        t_rocket = (n_rock / f_eff) if f_eff > 0 else float("inf")

        p_mishap = p_f + p_p
        mishap_count = sample_poisson(n_rock * p_mishap, rng)
        cost_mishap = mishap_count * float(uncertainty["rocket"]["C_mishap"])

        t_total = max(t_se, t_rocket)
        cost = m_se * c_elec_unit + n_rock * c_launch + t_total * c_maint + c_fixed
        cost += damage_cost + cost_mishap
        results.append(
            TrialResult(
                T=t_total,
                cost=cost,
                N_rock=n_rock,
                f_osc=f_osc,
                f_dmg=f_dmg,
                A_mech=a_mech,
                A_rocket=a_rocket,
                M_rocket_target=m_rocket_target,
            )
        )
    return results


def summarize(results: List[TrialResult]) -> Dict[str, Any]:
    t_vals = [r.T for r in results if math.isfinite(r.T)]
    c_vals = [r.cost for r in results if math.isfinite(r.cost)]
    n_vals = [float(r.N_rock) for r in results]
    infeasible = len(results) - len(t_vals)
    summary = {
        "trials": len(results),
        "infeasible": infeasible,
        "T_mean": statistics.mean(t_vals) if t_vals else float("inf"),
        "T_p50": percentile(t_vals, 50.0),
        "T_p90": percentile(t_vals, 90.0),
        "cost_mean": statistics.mean(c_vals) if c_vals else float("inf"),
        "cost_p50": percentile(c_vals, 50.0),
        "cost_p90": percentile(c_vals, 90.0),
        "N_rock_mean": statistics.mean(n_vals) if n_vals else 0.0,
        "N_rock_p50": percentile(n_vals, 50.0),
        "N_rock_p90": percentile(n_vals, 90.0),
    }
    return summary


def write_trials_csv(results: List[TrialResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "T",
                "cost",
                "N_rock",
                "f_osc",
                "f_dmg",
                "A_mech",
                "A_rocket",
                "M_rocket_target",
            ]
        )
        for r in results:
            writer.writerow(
                [
                    f"{r.T:.6f}",
                    f"{r.cost:.6f}",
                    r.N_rock,
                    f"{r.f_osc:.6f}",
                    f"{r.f_dmg:.6f}",
                    f"{r.A_mech:.6f}",
                    f"{r.A_rocket:.6f}",
                    f"{r.M_rocket_target:.6f}",
                ]
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--dump-config", action="store_true")
    parser.add_argument("--trials", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--se-share", type=float, default=0.5)
    parser.add_argument("--m-se", type=float, default=None)
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.dump_config:
        print(json.dumps(DEFAULT_CONFIG, indent=2))
        return

    config = load_config(args.config)
    base = config["base"]
    m_goal = float(base["M_goal"])
    if args.m_se is None:
        m_se = m_goal * float(args.se_share)
    else:
        m_se = float(args.m_se)

    results = simulate(config, args.trials, args.seed, m_se)
    summary = summarize(results)
    print(json.dumps(summary, indent=2))

    if args.output:
        write_trials_csv(results, args.output)


if __name__ == "__main__":
    main()
