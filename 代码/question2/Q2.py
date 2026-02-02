#!/usr/bin/env python3
"""Task 2: Reliability simulation with absorbing failures and DES.

Implements the Task 2 model described in the paper:
- absorbing Markov failures (state 6)
- event-driven discrete-event simulation (DES)
- Apex inventory coupling for elevator-supported scenarios
- replacement with latency and launch cadence constraint
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import argparse
import heapq
import json
import math
import os
import random
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Tuple

INF = 1.0e30
DAYS_PER_YEAR = 365.0

# -------------------- Global Defaults --------------------
DEFAULT_SCENARIO = 3
DEFAULT_M_GOAL = 1.0e8
DEFAULT_CAP_SE = 5.37e5
DEFAULT_CAP_ROCK = 125.0
DEFAULT_F_TOTAL = 3834.0
DEFAULT_TAU_DAYS = {1: 3.0, 2: 3.0, 3: 3.0, 4: 3.0, 5: 3.0}
DEFAULT_DELTA_TAU_DAYS = 0.0
DEFAULT_TAU_TRANSIT_DAYS = 14.0  # ground->apex elevator delay (paper baseline)
# Baseline failure probabilities mapped from segmented return/dock data (paper Table~failure_prob_task2)
# Failure probabilities (baseline): combine launch+dock for Program 1, keep direct launch for 2,
# keep burn leg for 3, combine return+dock for 4 (approx), small return for 5.
DEFAULT_P_FAIL = {
    1: 1.0 - (1.0 - 1.78e-2) * (1.0 - 1.03e-2),  # launch + dock combo ≈ 2.80%
    2: 1.78e-2,  # ground launch
    3: 1.0e-3,   # transfer leg
    4: 1.0 - (1.0 - 1.0e-3) * (1.0 - 1.03e-2),   # return + dock combo ≈ 1.13%
    5: 3.6e-4,   # return-to-site
}
DEFAULT_FAIL_COST = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0}
DEFAULT_C_LAUNCH = 1.5e7
DEFAULT_I_SAFE = 72
DEFAULT_DELTA_REPLACEMENT_DAYS = 14.0
DEFAULT_DOWN_RATIO = (0.0, 0.1)
DEFAULT_INITIAL_ROCKETS = None
DEFAULT_MAX_TIME_YEARS = 200.0
DEFAULT_SEED = 1
DEFAULT_LOG_EVERY = 10000
DEFAULT_MC_LOG_EVERY = 1
DEFAULT_VERBOSE = False


@dataclass(frozen=True)
class Task2Params:
    scenario: int = DEFAULT_SCENARIO
    M_goal: float = DEFAULT_M_GOAL
    Cap_SE: float = DEFAULT_CAP_SE
    Cap_Rock: float = DEFAULT_CAP_ROCK
    f_total: float = DEFAULT_F_TOTAL
    tau: Dict[int, float] = field(
        default_factory=lambda: {
            k: v / DAYS_PER_YEAR
            for k, v in DEFAULT_TAU_DAYS.items()
        }
    )
    delta_tau: float = DEFAULT_DELTA_TAU_DAYS / DAYS_PER_YEAR
    tau_transit: float = DEFAULT_TAU_TRANSIT_DAYS / DAYS_PER_YEAR
    p_fail: Dict[int, float] = field(
        default_factory=lambda: DEFAULT_P_FAIL.copy()
    )
    fail_cost: Dict[int, float] = field(
        default_factory=lambda: DEFAULT_FAIL_COST.copy()
    )
    C_launch: float = DEFAULT_C_LAUNCH
    I_safe: int = DEFAULT_I_SAFE
    delta_replacement: float = DEFAULT_DELTA_REPLACEMENT_DAYS / DAYS_PER_YEAR
    down_ratio: Tuple[float, float] = DEFAULT_DOWN_RATIO
    initial_rockets: Optional[int] = DEFAULT_INITIAL_ROCKETS
    max_time: float = DEFAULT_MAX_TIME_YEARS
    seed: int = DEFAULT_SEED


@dataclass
class SimulationResult:
    T_star: float
    delivered: float
    failures: int
    launches: int
    fail_cost: float
    fail_loss_cost: float
    replace_cost: float
    max_deficit: int
    completed: bool
    down_ratio: float


@dataclass
class Event:
    time: float
    seq: int
    etype: str
    rid: Optional[int] = None

    def __lt__(self, other: "Event") -> bool:
        if self.time != other.time:
            return self.time < other.time
        return self.seq < other.seq


@dataclass
class Rocket:
    rid: int
    state: int
    payload: float


def load_config(path: str) -> Dict[str, Any]:
    if not path.endswith(".json"):
        raise ValueError("Only JSON config is supported")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_int_key_dict(data: Dict[str, Any]) -> Dict[int, float]:
    out: Dict[int, float] = {}
    for k, v in data.items():
        out[int(k)] = float(v)
    return out


def parse_down_ratio(value: Any) -> Tuple[float, float]:
    if isinstance(value, (list, tuple)):
        if len(value) != 2:
            raise ValueError("down_ratio must be a float or a pair")
        return (float(value[0]), float(value[1]))
    return (float(value), float(value))


def apply_overrides(params: Task2Params, overrides: Dict[str, Any]) -> Task2Params:
    data = asdict(params)
    for key, value in overrides.items():
        if key in data:
            data[key] = value

    if "tau" in overrides:
        data["tau"] = _normalize_int_key_dict(overrides["tau"])
    if "tau_days" in overrides:
        tau_days = _normalize_int_key_dict(overrides["tau_days"])
        data["tau"] = {k: v / DAYS_PER_YEAR for k, v in tau_days.items()}
    if "p_fail" in overrides:
        data["p_fail"] = _normalize_int_key_dict(overrides["p_fail"])
    if "fail_cost" in overrides:
        data["fail_cost"] = _normalize_int_key_dict(overrides["fail_cost"])
    if "down_ratio" in overrides:
        data["down_ratio"] = parse_down_ratio(overrides["down_ratio"])

    return Task2Params(**data)


def validate_params(params: Task2Params) -> None:
    if params.scenario not in (1, 2, 3):
        raise ValueError("scenario must be 1, 2, or 3")
    if params.M_goal <= 0:
        raise ValueError("M_goal must be > 0")
    if params.Cap_Rock <= 0:
        raise ValueError("Cap_Rock must be > 0")
    if params.f_total <= 0:
        raise ValueError("f_total must be > 0")
    if params.I_safe < 0:
        raise ValueError("I_safe must be >= 0")
    if params.C_launch < 0:
        raise ValueError("C_launch must be >= 0")
    for l in range(1, 6):
        if l not in params.tau:
            raise ValueError("tau missing program {}".format(l))
        if l not in params.fail_cost:
            raise ValueError("fail_cost missing program {}".format(l))
        if params.fail_cost[l] < 0:
            raise ValueError("fail_cost must be >= 0")


def phi_for_scenario(scenario: int) -> Dict[int, int]:
    if scenario == 1:
        return {1: 3, 3: 4, 4: 3}
    if scenario == 2:
        return {2: 3, 3: 5, 5: 2}
    return {2: 3, 3: 4, 4: 3}


def start_state_for_scenario(scenario: int) -> int:
    # For Task 2 we assume the fleet has already been deployed (steady-state baseline).
    # Scenario 1/3: rockets reside at Apex ready to load/dispatch (state 4 -> 3).
    # Scenario 2: rockets start from ground launch cycle (state 2).
    return 4 if scenario in (1, 3) else 2


def requires_inventory(scenario: int, from_state: int, to_state: int) -> bool:
    if to_state != 3:
        return False
    if scenario == 1:
        return True
    if scenario == 3:
        return from_state == 4
    return False


class Task2Simulator:
    def __init__(self, params: Task2Params, seed: int) -> None:
        self.params = params
        self.rng = random.Random(seed)
        self.phi = phi_for_scenario(params.scenario)
        self.start_state = start_state_for_scenario(params.scenario)
        self.tau_robust = {k: params.tau[k] + params.delta_tau for k in params.tau}

        self.t = 0.0
        self.M = 0.0
        self.S = 0.0
        self.failures = 0
        self.launches = 0
        self.fail_loss_cost = 0.0
        self.replace_cost = 0.0
        self.max_deficit = 0
        self.pending_replacements = 0
        self.next_launch_slot = 0.0
        self.next_rid = 1
        self.inventory_event_time: Optional[float] = None

        dr_low, dr_high = params.down_ratio
        if dr_low == dr_high:
            self.down_ratio = dr_low
        else:
            self.down_ratio = self.rng.uniform(dr_low, dr_high)

        if params.scenario in (1, 3):
            self.cap_eff = (1.0 - self.down_ratio) * params.Cap_SE
        else:
            self.cap_eff = 0.0

        self.rocks: Dict[int, Rocket] = {}
        self.waiting: Deque[int] = deque()
        self.pq: List[Event] = []
        self.seq = 0

    def schedule_event(self, time: float, etype: str, rid: Optional[int] = None) -> None:
        self.seq += 1
        heapq.heappush(self.pq, Event(time=time, seq=self.seq, etype=etype, rid=rid))

    def active_count(self) -> int:
        return sum(1 for r in self.rocks.values() if r.state != 6)

    def update_deficit(self) -> None:
        deficit = max(0, self.params.I_safe - self.active_count())
        if deficit > self.max_deficit:
            self.max_deficit = deficit

    def add_rocket(self, init_state: int) -> None:
        rid = self.next_rid
        self.next_rid += 1
        self.rocks[rid] = Rocket(rid=rid, state=init_state, payload=self.params.Cap_Rock)
        self.schedule_event(self.t + self.tau_robust[init_state], "rocket", rid=rid)

    def fluid_update(self, new_t: float) -> None:
        dt = new_t - self.t
        if dt < 0:
            return
        if self.cap_eff > 0:
            # Elevator inflow starts after transit delay
            t0 = max(self.t, self.params.tau_transit)
            t1 = max(new_t, self.params.tau_transit)
            if t1 > t0:
                self.S += self.cap_eff * (t1 - t0)
        self.t = new_t

    def schedule_inventory_event(self) -> None:
        if not self.waiting:
            return
        if self.cap_eff <= 0:
            return
        rid = self.waiting[0]
        r = self.rocks.get(rid)
        if r is None:
            return
        needed = r.payload - self.S
        if needed <= 0:
            return
        start_flow = max(self.t, self.params.tau_transit)
        ready_time = start_flow + needed / self.cap_eff
        if self.inventory_event_time is None or ready_time < self.inventory_event_time:
            self.inventory_event_time = ready_time
            self.schedule_event(ready_time, "inventory")

    def release_waiting(self) -> None:
        while self.waiting:
            rid = self.waiting[0]
            r = self.rocks.get(rid)
            if r is None or r.state == 6:
                self.waiting.popleft()
                continue
            if self.S < r.payload:
                break
            self.waiting.popleft()
            self.S -= r.payload
            self.schedule_event(self.t + self.tau_robust[3], "rocket", rid=rid)
        if self.waiting:
            self.schedule_inventory_event()

    def order_replacements(self) -> None:
        deficit = max(0, self.params.I_safe - (self.active_count() + self.pending_replacements))
        if deficit <= 0:
            return
        for _ in range(deficit):
            t_ready = self.t + self.params.delta_replacement
            t_start = max(t_ready, self.next_launch_slot)
            self.next_launch_slot = t_start + 1.0 / self.params.f_total
            self.pending_replacements += 1
            self.schedule_event(t_start, "insert")

    def handle_insert(self) -> None:
        self.pending_replacements = max(0, self.pending_replacements - 1)
        self.add_rocket(self.start_state)
        self.launches += 1
        self.replace_cost += self.params.C_launch
        self.update_deficit()

    def handle_rocket_event(self, rid: int) -> None:
        r = self.rocks.get(rid)
        if r is None or r.state == 6:
            return
        state = r.state

        pf = self.params.p_fail.get(state, 0.0)
        if self.rng.random() < pf:
            r.state = 6
            self.failures += 1
            self.fail_loss_cost += self.params.fail_cost.get(state, 0.0)
            self.order_replacements()
            self.update_deficit()
            return

        if state == 3:
            # Only credit delivery after a successful leg
            self.M += r.payload

        next_state = self.phi.get(state)
        if next_state is None:
            return

        r.state = next_state
        if next_state == 3 and requires_inventory(self.params.scenario, state, next_state):
            if self.cap_eff <= 0:
                return
            if self.S >= r.payload:
                self.S -= r.payload
                self.schedule_event(self.t + self.tau_robust[3], "rocket", rid=rid)
            else:
                self.waiting.append(rid)
                self.schedule_inventory_event()
        else:
            self.schedule_event(self.t + self.tau_robust[next_state], "rocket", rid=rid)

    def run(
        self,
        log_every: int = DEFAULT_LOG_EVERY,
        verbose: bool = DEFAULT_VERBOSE,
    ) -> SimulationResult:
        init_count = self.params.initial_rockets
        if init_count is None:
            init_count = self.params.I_safe

        for _ in range(int(init_count)):
            self.add_rocket(self.start_state)

        completed = False
        event_count = 0
        if verbose:
            print(
                "[开始] "
                f"场景={self.params.scenario} I0={init_count} "
                f"M_goal={self.params.M_goal} cap_eff={self.cap_eff:.2f}",
                flush=True,
            )
        while self.pq:
            ev = heapq.heappop(self.pq)
            if ev.time > self.params.max_time:
                break
            self.fluid_update(ev.time)
            event_count += 1

            if ev.etype == "inventory":
                if self.inventory_event_time is None:
                    continue
                if abs(ev.time - self.inventory_event_time) > 1.0e-9:
                    continue
                self.inventory_event_time = None
                self.release_waiting()
            elif ev.etype == "insert":
                self.handle_insert()
            elif ev.etype == "rocket":
                if ev.rid is not None:
                    self.handle_rocket_event(int(ev.rid))

            self.release_waiting()
            if self.M >= self.params.M_goal:
                completed = True
                break

            if verbose and log_every > 0 and event_count % log_every == 0:
                pct = self.M / self.params.M_goal * 100.0
                total_cost = self.fail_loss_cost + self.replace_cost
                print(
                    "[进度] "
                    f"事件={event_count} t={self.t:.2f} "
                    f"M={self.M:.2f}/{self.params.M_goal:.2f}({pct:.2f}%) "
                    f"失败={self.failures} 成本={total_cost:.2f} 现役={self.active_count()} "
                    f"等待={len(self.waiting)} 库存={self.S:.2f}",
                    flush=True,
                )

        if verbose:
            pct = self.M / self.params.M_goal * 100.0
            total_cost = self.fail_loss_cost + self.replace_cost
            print(
                "[结束] "
                f"t={self.t:.2f} M={self.M:.2f}/{self.params.M_goal:.2f}({pct:.2f}%) "
                f"失败={self.failures} 成本={total_cost:.2f} 发射={self.launches} "
                f"(损失={self.fail_loss_cost:.2f}, 替换={self.replace_cost:.2f})",
                flush=True,
            )

        return SimulationResult(
            T_star=self.t,
            delivered=self.M,
            failures=self.failures,
            launches=self.launches,
            fail_cost=self.fail_loss_cost + self.replace_cost,
            fail_loss_cost=self.fail_loss_cost,
            replace_cost=self.replace_cost,
            max_deficit=self.max_deficit,
            completed=completed,
            down_ratio=self.down_ratio,
        )


def summarize_results(results: List[SimulationResult]) -> Dict[str, Any]:
    times = [r.T_star for r in results if r.completed]
    if not times:
        return {"completed_runs": 0, "total_runs": len(results)}

    mean_t = sum(times) / len(times)
    if len(times) > 1:
        var = sum((t - mean_t) ** 2 for t in times) / (len(times) - 1)
        std_t = math.sqrt(var)
    else:
        std_t = 0.0
    ci_half = 1.96 * std_t / math.sqrt(len(times)) if len(times) > 1 else 0.0

    return {
        "completed_runs": len(times),
        "total_runs": len(results),
        "mean_T": mean_t,
        "std_T": std_t,
        "ci95_T": (mean_t - ci_half, mean_t + ci_half),
        "mean_failures": sum(r.failures for r in results) / len(results),
        "mean_launches": sum(r.launches for r in results) / len(results),
        "mean_fail_cost": sum(r.fail_cost for r in results) / len(results),
        "mean_fail_loss_cost": sum(r.fail_loss_cost for r in results) / len(results),
        "mean_replace_cost": sum(r.replace_cost for r in results) / len(results),
        "max_deficit": max(r.max_deficit for r in results),
    }


def export_results(
    summary: Dict[str, Any],
    results: List[SimulationResult],
    outdir: str,
) -> None:
    """Write summary JSON and per-run CSV to outdir."""
    import os
    import csv

    os.makedirs(outdir, exist_ok=True)

    # Summary JSON
    with open(os.path.join(outdir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Per-run CSV (if any)
    if not results:
        return
    fieldnames = [
        "run",
        "T_star",
        "delivered",
        "failures",
        "launches",
        "fail_cost",
        "fail_loss_cost",
        "replace_cost",
        "max_deficit",
        "completed",
        "down_ratio",
    ]
    with open(os.path.join(outdir, "runs.csv"), "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i, r in enumerate(results, 1):
            writer.writerow(
                {
                    "run": i,
                    "T_star": r.T_star,
                    "delivered": r.delivered,
                    "failures": r.failures,
                    "launches": r.launches,
                    "fail_cost": r.fail_cost,
                    "fail_loss_cost": r.fail_loss_cost,
                    "replace_cost": r.replace_cost,
                    "max_deficit": r.max_deficit,
                    "completed": r.completed,
                    "down_ratio": r.down_ratio,
                }
            )


def run_monte_carlo(
    params: Task2Params,
    n_runs: int,
    verbose: bool = DEFAULT_VERBOSE,
    log_every: int = DEFAULT_LOG_EVERY,
    mc_log_every: int = DEFAULT_MC_LOG_EVERY,
) -> Tuple[List[SimulationResult], Dict[str, Any]]:
    results: List[SimulationResult] = []
    for i in range(n_runs):
        if mc_log_every > 0 and i % mc_log_every == 0:
            print(f"[MC] 运行 {i + 1}/{n_runs}", flush=True)
        sim = Task2Simulator(params, seed=params.seed + i)
        results.append(sim.run(verbose=verbose, log_every=log_every))
    summary = summarize_results(results)
    return results, summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Task 2 reliability simulation")
    parser.add_argument("--config", type=str, default=None, help="Path to JSON config")
    parser.add_argument("--scenario", type=int, default=None, help="Scenario 1/2/3")
    parser.add_argument("--n-mc", type=int, default=50, help="Monte Carlo runs")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument("--verbose", action="store_true", help="Enable per-event logs")
    parser.add_argument("--log-every", type=int, default=DEFAULT_LOG_EVERY, help="Log per N events")
    parser.add_argument("--mc-log-every", type=int, default=DEFAULT_MC_LOG_EVERY, help="Log per N MC runs")
    parser.add_argument("--outdir", type=str, default=None, help="Output directory for summary/runs")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(base_dir)
    default_outdir = os.path.join(root_dir, "results", "task2")

    params = Task2Params()
    if args.config:
        overrides = load_config(args.config)
        params = apply_overrides(params, overrides)
    if args.scenario is not None:
        params = Task2Params(**{**asdict(params), "scenario": args.scenario})
    if args.seed is not None:
        params = Task2Params(**{**asdict(params), "seed": args.seed})

    validate_params(params)

    results, summary = run_monte_carlo(
        params,
        n_runs=args.n_mc,
        verbose=args.verbose,
        log_every=args.log_every,
        mc_log_every=args.mc_log_every,
    )

    outdir = args.outdir or default_outdir
    export_results(summary, results, outdir)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
