#!/usr/bin/env python3
"""Task 4 environmental impact calculator."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

# -------------------- Global Defaults (from the paper) --------------------
M_GOAL_TON = 1.0e8
CAP_ROCK_TON = 125.0
CAP_SE_TON_PER_YEAR = 179_000.0
F_CYCLE_PER_YEAR = 60.0

RP1_TON_PER_LAUNCH = 395.5
LOX_TON_PER_LAUNCH = 937.1
CO2_FACTOR_RP1_KG_PER_KG = 3.153
CO2_TON_PER_LAUNCH = 1161.0
CO2E_TON_PER_LAUNCH = 2675.0
BC_EI_MIN_G_PER_KG = 10.0
BC_EI_MAX_G_PER_KG = 20.0
BC_EI_DEFAULT_G_PER_KG = 15.0
NOX_EI_G_PER_KG = 14.0

ELEVATOR_KWH_PER_KG = 14.8
GRID_CO2_INTENSITY = {
    "2020": 0.468,
    "2030": 0.138,
    "2050": 0.005,
}
DEFAULT_GRID_YEAR = "2050"

ALPHA_CLIMATE_PRESETS = {
    "baseline": 1.0,
    "clean": 0.10,
    "ultra": 0.02,
}
ALPHA_BC_DEFAULT = 0.1
BETA_STRAT_DEFAULT = 1.0

DEFAULT_SITE_CAPS = {
    "Alaska": 10.0,
    "Florida": 2300.0,
    "California": 950.0,
    "Texas": 190.0,
    "Virginia": 70.0,
    "Mahia": 140.0,
    "Taiyuan": 100.0,
    "SatishDhawan": 35.0,
    "Kazakhstan": 25.0,
    "FrenchGuiana": 24.0,
}


@dataclass(frozen=True)
class Task4Config:
    scenario: str
    total_mass_ton: float
    cap_rock_ton: float
    cap_se_ton_per_year: float
    f_cycle_per_year: float
    n_launch_total: Optional[int]
    project_years: float
    bc_ei_g_per_kg: float
    alpha_climate: float
    beta_strat: float
    grid_intensity: float
    site_caps: Dict[str, float]
    launch_plan: Optional[Dict[str, float]]


def normalize_scenario(value: str) -> str:
    key = value.strip().upper()
    if key in ("1", "A"):
        return "A"
    if key in ("2", "B"):
        return "B"
    if key in ("3", "C"):
        return "C"
    raise ValueError("scenario must be A/B/C or 1/2/3")


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def infer_n_launch_total(config: Task4Config) -> int:
    if config.scenario == "A":
        return 0
    if config.scenario == "B":
        return int(math.ceil(config.total_mass_ton / config.cap_rock_ton))
    return int(
        math.ceil(config.cap_se_ton_per_year / (config.f_cycle_per_year * config.cap_rock_ton))
    )


def elevator_mass(config: Task4Config, deliverable_ton: float, direct_mass_ton: float) -> float:
    if config.scenario == "B":
        return 0.0
    return max(0.0, deliverable_ton - direct_mass_ton)


def compute_rocket_emissions(n_launch_total: int, bc_ei_g_per_kg: float) -> Dict[str, float]:
    rp1_kg = RP1_TON_PER_LAUNCH * 1000.0
    fuel_kg = (RP1_TON_PER_LAUNCH + LOX_TON_PER_LAUNCH) * 1000.0

    co2_from_rp1_ton = rp1_kg * CO2_FACTOR_RP1_KG_PER_KG / 1000.0
    bc_ton = rp1_kg * bc_ei_g_per_kg / 1.0e6
    bc_ton_min = rp1_kg * BC_EI_MIN_G_PER_KG / 1.0e6
    bc_ton_max = rp1_kg * BC_EI_MAX_G_PER_KG / 1.0e6
    nox_ton = rp1_kg * NOX_EI_G_PER_KG / 1.0e6

    return {
        "n_launch_total": float(n_launch_total),
        "co2_ton_per_launch": CO2_TON_PER_LAUNCH,
        "co2e_ton_per_launch": CO2E_TON_PER_LAUNCH,
        "co2_from_rp1_ton_per_launch": co2_from_rp1_ton,
        "bc_ton_per_launch": bc_ton,
        "bc_ton_per_launch_min": bc_ton_min,
        "bc_ton_per_launch_max": bc_ton_max,
        "nox_ton_per_launch": nox_ton,
        "total_co2_ton": CO2_TON_PER_LAUNCH * n_launch_total,
        "total_co2e_ton": CO2E_TON_PER_LAUNCH * n_launch_total,
        "total_bc_ton": bc_ton * n_launch_total,
        "total_bc_ton_min": bc_ton_min * n_launch_total,
        "total_bc_ton_max": bc_ton_max * n_launch_total,
        "total_nox_ton": nox_ton * n_launch_total,
        "fuel_total_ton_per_launch": fuel_kg / 1000.0,
    }


def compute_elevator_emissions(mass_ton: float, grid_intensity: float) -> Dict[str, float]:
    mass_kg = mass_ton * 1000.0
    energy_kwh = mass_kg * ELEVATOR_KWH_PER_KG
    co2_kg = energy_kwh * grid_intensity
    return {
        "mass_ton": mass_ton,
        "energy_kwh": energy_kwh,
        "co2_ton": co2_kg / 1000.0,
    }


def compute_caps(
    site_caps: Dict[str, float],
    alpha_climate: float,
    launches_per_year: float,
    launch_plan: Optional[Dict[str, float]],
) -> Tuple[Dict[str, Dict[str, float]], Dict[str, float]]:
    k_env = 1.0 / alpha_climate if alpha_climate > 0 else float("inf")
    caps_env = {k: v * k_env for k, v in site_caps.items()}
    total_cap = sum(caps_env.values())

    if launch_plan:
        allocation = {k: float(launch_plan.get(k, 0.0)) for k in caps_env}
    elif total_cap > 0:
        allocation = {
            k: launches_per_year * (cap / total_cap) for k, cap in caps_env.items()
        }
    else:
        allocation = {k: 0.0 for k in caps_env}

    detail: Dict[str, Dict[str, float]] = {}
    for site, cap in caps_env.items():
        used = allocation.get(site, 0.0)
        util = used / cap if cap > 0 else 0.0
        detail[site] = {
            "cap_base": float(site_caps.get(site, 0.0)),
            "cap_env": float(cap),
            "launches": float(used),
            "utilization": float(util),
        }

    summary = {
        "k_env": k_env,
        "cap_total": total_cap,
        "launches_total": launches_per_year,
        "cap_violation": launches_per_year > total_cap if total_cap > 0 else False,
        "max_utilization": max((d["utilization"] for d in detail.values()), default=0.0),
    }
    return detail, summary


def build_config(args: argparse.Namespace) -> Task4Config:
    scenario = normalize_scenario(args.scenario)
    cap_rock = args.cap_rock if args.cap_rock is not None else CAP_ROCK_TON
    cap_se = args.cap_se if args.cap_se is not None else CAP_SE_TON_PER_YEAR
    f_cycle = args.f_cycle if args.f_cycle is not None else F_CYCLE_PER_YEAR

    if args.alpha_climate in ALPHA_CLIMATE_PRESETS:
        alpha_climate = ALPHA_CLIMATE_PRESETS[args.alpha_climate]
    else:
        alpha_climate = float(args.alpha_climate)

    if args.grid_intensity is not None:
        grid_intensity = float(args.grid_intensity)
    else:
        grid_intensity = GRID_CO2_INTENSITY.get(args.grid_year, GRID_CO2_INTENSITY[DEFAULT_GRID_YEAR])

    site_caps = DEFAULT_SITE_CAPS.copy()
    if args.site_caps:
        site_caps = {k: float(v) for k, v in load_json(args.site_caps).items()}

    launch_plan = None
    if args.launch_plan:
        launch_plan = {k: float(v) for k, v in load_json(args.launch_plan).items()}

    return Task4Config(
        scenario=scenario,
        total_mass_ton=args.total_mass if args.total_mass is not None else M_GOAL_TON,
        cap_rock_ton=cap_rock,
        cap_se_ton_per_year=cap_se,
        f_cycle_per_year=f_cycle,
        n_launch_total=args.n_launch,
        project_years=args.project_years,
        bc_ei_g_per_kg=args.bc_ei,
        alpha_climate=alpha_climate,
        beta_strat=args.beta_strat,
        grid_intensity=grid_intensity,
        site_caps=site_caps,
        launch_plan=launch_plan,
    )


def validate_config(config: Task4Config) -> None:
    if config.total_mass_ton <= 0:
        raise ValueError("total_mass must be > 0")
    if config.cap_rock_ton <= 0:
        raise ValueError("cap_rock must be > 0")
    if config.cap_se_ton_per_year <= 0:
        raise ValueError("cap_se must be > 0")
    if config.f_cycle_per_year <= 0:
        raise ValueError("f_cycle must be > 0")
    if config.project_years <= 0:
        raise ValueError("project_years must be > 0")
    if not (config.bc_ei_g_per_kg > 0):
        raise ValueError("bc_ei must be > 0")
    if config.alpha_climate <= 0:
        raise ValueError("alpha_climate must be > 0")
    if config.grid_intensity < 0:
        raise ValueError("grid_intensity must be >= 0")


def main() -> None:
    parser = argparse.ArgumentParser(description="Task 4 environmental impact calculator")
    parser.add_argument("--scenario", type=str, default="C", help="Scenario A/B/C (or 1/2/3)")
    parser.add_argument("--total-mass", type=float, default=None, help="Total mass to deliver (ton)")
    parser.add_argument("--cap-rock", type=float, default=None, help="Payload per launch (ton)")
    parser.add_argument("--cap-se", type=float, default=None, help="Elevator annual capacity (ton/yr)")
    parser.add_argument("--f-cycle", type=float, default=None, help="Cycles per year for orbital rockets")
    parser.add_argument("--n-launch", type=int, default=None, help="Total Earth launches")
    parser.add_argument("--project-years", type=float, default=1.0, help="Project duration (years)")
    parser.add_argument("--bc-ei", type=float, default=BC_EI_DEFAULT_G_PER_KG, help="BC EI (g/kg fuel)")
    parser.add_argument(
        "--alpha-climate",
        type=str,
        default="clean",
        help="alpha_climate preset: baseline/clean/ultra or numeric value",
    )
    parser.add_argument("--beta-strat", type=float, default=BETA_STRAT_DEFAULT, help="Proxy scaling beta")
    parser.add_argument("--grid-year", type=str, default=DEFAULT_GRID_YEAR, help="2020/2030/2050")
    parser.add_argument("--grid-intensity", type=float, default=None, help="Override grid CO2 intensity")
    parser.add_argument("--site-caps", type=str, default=None, help="JSON file for site caps")
    parser.add_argument("--launch-plan", type=str, default=None, help="JSON file for per-site launches")
    args = parser.parse_args()

    config = build_config(args)
    validate_config(config)

    n_launch_total = config.n_launch_total
    if n_launch_total is None:
        n_launch_total = infer_n_launch_total(config)

    direct_mass_ton = 0.0
    if config.scenario in ("B", "C"):
        direct_mass_ton = min(
            config.total_mass_ton, n_launch_total * config.cap_rock_ton
        )

    elev_cap_ton = 0.0
    orbit_cap_ton = 0.0
    deliverable_elevator_ton = 0.0
    if config.scenario in ("A", "C"):
        elev_cap_ton = config.cap_se_ton_per_year * config.project_years
        orbit_cap_ton = (
            n_launch_total
            * config.f_cycle_per_year
            * config.cap_rock_ton
            * config.project_years
        )
        remaining = max(0.0, config.total_mass_ton - direct_mass_ton)
        deliverable_elevator_ton = min(remaining, elev_cap_ton, orbit_cap_ton)

    deliverable_ton = direct_mass_ton + deliverable_elevator_ton
    if deliverable_ton > config.total_mass_ton:
        deliverable_ton = config.total_mass_ton
    infeasible = deliverable_ton + 1.0e-9 < config.total_mass_ton
    mass_elevator_ton = elevator_mass(config, deliverable_ton, direct_mass_ton)
    launches_per_year = n_launch_total / config.project_years

    rocket = compute_rocket_emissions(n_launch_total, config.bc_ei_g_per_kg)
    elevator = compute_elevator_emissions(mass_elevator_ton, config.grid_intensity)

    strat_proxy_ton = (
        rocket["fuel_total_ton_per_launch"]
        * n_launch_total
        * config.alpha_climate
        * config.beta_strat
    )

    total_co2e = rocket["total_co2e_ton"] + elevator["co2_ton"]
    if deliverable_ton > 0:
        ci = total_co2e / deliverable_ton
    else:
        ci = None

    years_needed_elevator = None
    if config.cap_se_ton_per_year > 0:
        years_needed_elevator = config.total_mass_ton / config.cap_se_ton_per_year

    caps_detail, caps_summary = compute_caps(
        config.site_caps,
        config.alpha_climate,
        launches_per_year,
        config.launch_plan,
    )

    summary = {
        "scenario": config.scenario,
        "total_mass_ton": config.total_mass_ton,
        "cap_rock_ton": config.cap_rock_ton,
        "cap_se_ton_per_year": config.cap_se_ton_per_year,
        "f_cycle_per_year": config.f_cycle_per_year,
        "project_years": config.project_years,
        "n_launch_total": n_launch_total,
        "launches_per_year": launches_per_year,
        "deliverable_ton": deliverable_ton,
        "deliverable_shortfall_ton": max(0.0, config.total_mass_ton - deliverable_ton),
        "infeasible": infeasible,
        "mass_rocket_direct_ton": direct_mass_ton,
        "mass_elevator_ton": mass_elevator_ton,
        "elevator_cap_ton": elev_cap_ton,
        "orbit_cap_ton": orbit_cap_ton,
        "years_needed_elevator": years_needed_elevator,
        "alpha_climate": config.alpha_climate,
        "grid_intensity": config.grid_intensity,
        "rocket_emissions": rocket,
        "elevator_emissions": elevator,
        "strat_proxy_ton_fuel": strat_proxy_ton,
        "total_co2e_ton": total_co2e,
        "carbon_intensity_ton_per_ton": ci,
        "site_caps": caps_detail,
        "site_caps_summary": caps_summary,
    }

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
