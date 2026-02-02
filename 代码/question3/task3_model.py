#!/usr/bin/env python3
"""Task 3 water buffer model aligned with latex.tex.

Implements a one-year water inventory simulation with:
- continuous consumption and discrete arrivals
- Task 2-style DES for rocket cycles and failures
- elevator supply coupling for scenarios 1/3
- quantile-based safety stock estimate
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
import heapq
import json
import math
import random
from typing import Any, Dict, List, Optional, Sequence, Tuple

DAYS_PER_YEAR = 365.0
INF = 1.0e30

# -------------------- Defaults from latex.tex (Task 3) --------------------
DEFAULT_SCENARIO = 3

DEFAULT_N = 100000
DEFAULT_D_DAYS = 365.0
DEFAULT_W_PERSON = 3.8
DEFAULT_R_BASE = 0.98
DEFAULT_DELTA_R = 0.0
DEFAULT_R_DEGRADE_START = None
DEFAULT_R_DEGRADE_END = None
DEFAULT_S_MOON = 0.0

DEFAULT_ETA_PACK = 0.9
DEFAULT_KAPPA_SVC = 1.0

DEFAULT_CAP_SE = 5.37e5
DEFAULT_CAP_ROCK = 125.0
DEFAULT_F_TOTAL = 3844.0

DEFAULT_TAU_DAYS = {1: 3.0, 2: 3.0, 3: 3.0, 4: 3.0, 5: 3.0}
DEFAULT_DELTA_TAU_DAYS = 0.0
DEFAULT_ELEVATOR_DELAY_DAYS = 14.0
DEFAULT_MIN_CYCLE_DAYS = 6.0

DEFAULT_P_LAUNCH = 1.78e-2
DEFAULT_P_DOCK_AUTO = 1.03e-2
DEFAULT_P_LAND = 1.0e-3
DEFAULT_P_RETURN = 3.60e-4

DEFAULT_DELTA_REPLACEMENT_DAYS = 14.0
DEFAULT_DOWN_RATIO = 0.0
DEFAULT_INITIAL_ROCKETS = None

DEFAULT_ALPHA = 0.99
DEFAULT_SEED = 1

DEFAULT_C_LAUNCH = 1.5e7
DEFAULT_C_ELEC_UNIT = 7156.8
DEFAULT_C_MAINT = 1.2e8
DEFAULT_C_TV_FIXED = 3.0e8


def _default_p_fail() -> Dict[int, float]:
    p16 = 1.0 - (1.0 - DEFAULT_P_LAUNCH) * (1.0 - DEFAULT_P_DOCK_AUTO)
    return {
        1: p16,
        2: DEFAULT_P_LAUNCH,
        3: DEFAULT_P_LAND,
        4: DEFAULT_P_DOCK_AUTO,
        5: DEFAULT_P_RETURN,
    }


@dataclass(frozen=True)
class Task3Params:
    scenario: int = DEFAULT_SCENARIO
    N: int = DEFAULT_N
    d_days: float = DEFAULT_D_DAYS
    w_person: float = DEFAULT_W_PERSON
    r_base: float = DEFAULT_R_BASE
    delta_r: float = DEFAULT_DELTA_R
    r_degrade_start: Optional[float] = DEFAULT_R_DEGRADE_START
    r_degrade_end: Optional[float] = DEFAULT_R_DEGRADE_END
    S_moon: float = DEFAULT_S_MOON
    eta_pack: float = DEFAULT_ETA_PACK
    kappa_svc: float = DEFAULT_KAPPA_SVC
    Cap_SE: float = DEFAULT_CAP_SE
    Cap_Rock: float = DEFAULT_CAP_ROCK
    f_total: float = DEFAULT_F_TOTAL
    tau: Dict[int, float] = field(
        default_factory=lambda: {
            k: v / DAYS_PER_YEAR for k, v in DEFAULT_TAU_DAYS.items()
        }
    )
    delta_tau: float = DEFAULT_DELTA_TAU_DAYS / DAYS_PER_YEAR
    elevator_delay: float = DEFAULT_ELEVATOR_DELAY_DAYS / DAYS_PER_YEAR
    min_delivery_interval: float = DEFAULT_MIN_CYCLE_DAYS / DAYS_PER_YEAR
    p_fail: Dict[int, float] = field(default_factory=_default_p_fail)
    I_safe: Optional[int] = DEFAULT_INITIAL_ROCKETS
    delta_replacement: float = DEFAULT_DELTA_REPLACEMENT_DAYS / DAYS_PER_YEAR
    down_ratio: float = DEFAULT_DOWN_RATIO
    initial_rockets: Optional[int] = DEFAULT_INITIAL_ROCKETS
    seed: int = DEFAULT_SEED
    alpha: float = DEFAULT_ALPHA
    C_launch: float = DEFAULT_C_LAUNCH
    C_elec_unit: float = DEFAULT_C_ELEC_UNIT
    C_maint: float = DEFAULT_C_MAINT
    C_TV_fixed: float = DEFAULT_C_TV_FIXED


@dataclass
class SimulationResult:
    stockout: bool
    stockout_time_year: Optional[float]
    stockout_duration_days: float
    min_inventory: float
    max_gap_days: float
    arrivals: int
    direct_arrivals: int
    failures: int
    launches: int
    max_deficit: int
    max_inventory_queue: int
    max_inventory_wait_days: float
    max_launch_wait_days: float
    down_ratio: float
    W_end: float


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
    loaded_from_elevator: Optional[bool] = None
    last_delivery_time: Optional[float] = None


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


def apply_overrides(params: Task3Params, overrides: Dict[str, Any]) -> Task3Params:
    data = asdict(params)
    for key, value in overrides.items():
        if key in data:
            data[key] = value

    if "tau" in overrides:
        data["tau"] = _normalize_int_key_dict(overrides["tau"])
    if "tau_days" in overrides:
        tau_days = _normalize_int_key_dict(overrides["tau_days"])
        data["tau"] = {k: v / DAYS_PER_YEAR for k, v in tau_days.items()}
    if "min_cycle_days" in overrides:
        data["min_delivery_interval"] = float(overrides["min_cycle_days"]) / DAYS_PER_YEAR
    if "p_fail" in overrides:
        data["p_fail"] = _normalize_int_key_dict(overrides["p_fail"])
    if isinstance(data.get("f_total"), list):
        data["f_total"] = float(sum(data["f_total"]))

    return Task3Params(**data)


def validate_params(params: Task3Params) -> None:
    if params.scenario not in (1, 2, 3):
        raise ValueError("scenario must be 1, 2, or 3")
    if params.N <= 0:
        raise ValueError("N must be > 0")
    if params.d_days <= 0:
        raise ValueError("d_days must be > 0")
    if params.w_person <= 0:
        raise ValueError("w_person must be > 0")
    if not (0.0 <= params.r_base <= 1.0):
        raise ValueError("r_base must be within [0, 1]")
    if params.delta_r < 0:
        raise ValueError("delta_r must be >= 0")
    if params.r_base - params.delta_r < 0:
        raise ValueError("r_base - delta_r must be >= 0")
    if params.S_moon < 0:
        raise ValueError("S_moon must be >= 0")
    if not (0.0 < params.eta_pack <= 1.0):
        raise ValueError("eta_pack must be within (0, 1]")
    if params.kappa_svc <= 0:
        raise ValueError("kappa_svc must be > 0")
    if params.Cap_Rock <= 0:
        raise ValueError("Cap_Rock must be > 0")
    if params.f_total <= 0:
        raise ValueError("f_total must be > 0")
    if params.elevator_delay < 0:
        raise ValueError("elevator_delay must be >= 0")
    if params.min_delivery_interval < 0:
        raise ValueError("min_delivery_interval must be >= 0")
    if not (0.0 <= params.down_ratio < 1.0):
        raise ValueError("down_ratio must be within [0, 1)")
    if not (0.0 < params.alpha <= 1.0):
        raise ValueError("alpha must be within (0, 1]")
    if params.r_degrade_start is not None and params.r_degrade_end is not None:
        if params.r_degrade_start >= params.r_degrade_end:
            raise ValueError("r_degrade_start must be < r_degrade_end")
    for l in range(1, 6):
        if l not in params.tau:
            raise ValueError("tau missing program {}".format(l))


def compute_i_safe(params: Task3Params) -> int:
    if params.min_delivery_interval <= 0:
        return 0
    f_cycle = DAYS_PER_YEAR / (params.min_delivery_interval * DAYS_PER_YEAR)
    if f_cycle <= 0:
        return 0
    return int(math.ceil(params.Cap_SE / (f_cycle * params.Cap_Rock)))


def phi_for_scenario(scenario: int) -> Dict[int, int]:
    if scenario == 1:
        return {1: 3, 3: 4, 4: 3}
    if scenario == 2:
        return {2: 3, 3: 5, 5: 2}
    return {2: 3, 3: 4, 4: 3}


def start_state_for_scenario(scenario: int) -> int:
    return 1 if scenario == 1 else 2


def requires_inventory(scenario: int, from_state: int, to_state: int) -> bool:
    if to_state != 3:
        return False
    if scenario == 1:
        return True
    if scenario == 3:
        return from_state == 4
    return False


def gross_per_day(params: Task3Params) -> float:
    return params.N * params.w_person / 1000.0


def _segments_in_days(
    d0: float,
    d1: float,
    params: Task3Params,
    gross_day: float,
) -> List[Tuple[float, float, float]]:
    if (
        params.delta_r <= 0
        or params.r_degrade_start is None
        or params.r_degrade_end is None
    ):
        c_day = gross_day * (1.0 - params.r_base)
        return [(d0, d1, c_day)]
    start = max(0.0, min(params.d_days, float(params.r_degrade_start)))
    end = max(0.0, min(params.d_days, float(params.r_degrade_end)))
    if end <= start or d1 <= start or d0 >= end:
        c_day = gross_day * (1.0 - params.r_base)
        return [(d0, d1, c_day)]
    segments: List[Tuple[float, float, float]] = []
    if d0 < start:
        c_day = gross_day * (1.0 - params.r_base)
        segments.append((d0, min(d1, start), c_day))
    if d1 > start and d0 < end:
        c_day = gross_day * (1.0 - (params.r_base - params.delta_r))
        segments.append((max(d0, start), min(d1, end), c_day))
    if d1 > end:
        c_day = gross_day * (1.0 - params.r_base)
        segments.append((max(d0, end), d1, c_day))
    return segments


def quantile(data: List[float], alpha: float) -> float:
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = int(math.ceil(alpha * len(sorted_data))) - 1
    idx = max(0, min(idx, len(sorted_data) - 1))
    return float(sorted_data[idx])


class Task3DES:
    def __init__(self, params: Task3Params, seed: int) -> None:
        self.params = params
        self.rng = random.Random(seed)

        self.phi = phi_for_scenario(params.scenario)
        self.start_state = start_state_for_scenario(params.scenario)
        self.tau_robust = {
            k: params.kappa_svc * (params.tau[k] + params.delta_tau)
            for k in params.tau
        }

        self.I_safe = params.I_safe
        if self.I_safe is None:
            self.I_safe = compute_i_safe(params)

        self.t = 0.0
        self.S = 0.0
        self.W = params.S_moon
        self.min_W = params.S_moon

        self.failures = 0
        self.launches = 0
        self.max_deficit = 0
        self.pending_replacements = 0
        self.next_launch_slot = 0.0
        self.next_rid = 1

        self.inventory_event_time: Optional[float] = None
        self.max_inventory_queue = 0
        self.max_inventory_wait = 0.0
        self.max_launch_wait = 0.0

        self.stockout = False
        self.stockout_time: Optional[float] = None
        self.last_arrival_day = 0.0
        self.max_gap_days = 0.0
        self.arrivals = 0
        self.direct_arrivals = 0

        self.cap_eff = 0.0
        if params.scenario in (1, 3):
            self.cap_eff = (1.0 - params.down_ratio) * params.Cap_SE

        self.q_water = params.eta_pack * params.Cap_Rock
        self.gross_day = gross_per_day(params)

        self.rocks: Dict[int, Rocket] = {}
        self.waiting: List[int] = []
        self.waiting_since: Dict[int, float] = {}
        self.pq: List[Event] = []
        self.seq = 0

    def schedule_event(self, time: float, etype: str, rid: Optional[int] = None) -> None:
        self.seq += 1
        heapq.heappush(self.pq, Event(time=time, seq=self.seq, etype=etype, rid=rid))

    def active_count(self) -> int:
        return sum(1 for r in self.rocks.values() if r.state != 6)

    def update_deficit(self) -> None:
        deficit = max(0, int(self.I_safe or 0) - self.active_count())
        if deficit > self.max_deficit:
            self.max_deficit = deficit

    def add_rocket(self, init_state: int) -> None:
        rid = self.next_rid
        self.next_rid += 1
        self.rocks[rid] = Rocket(rid=rid, state=init_state, payload=self.q_water)
        self.schedule_event(self.t + self.tau_robust[init_state], "rocket", rid=rid)

    def schedule_program3(self, rid: int, start_time: float) -> None:
        r = self.rocks.get(rid)
        if r is None:
            return
        completion = start_time + self.tau_robust[3]
        if r.last_delivery_time is not None:
            min_complete = r.last_delivery_time + self.params.min_delivery_interval
            if completion < min_complete:
                completion = min_complete
        self.schedule_event(completion, "rocket", rid=rid)

    def consume_until(self, new_t: float) -> float:
        if self.stockout:
            return self.t
        d0 = self.t * DAYS_PER_YEAR
        d1 = new_t * DAYS_PER_YEAR
        if d1 <= d0:
            return self.t
        current_W = self.W
        segments = _segments_in_days(d0, d1, self.params, self.gross_day)
        for seg_start, seg_end, c_day in segments:
            dt_days = seg_end - seg_start
            if dt_days <= 0:
                continue
            if c_day <= 0:
                continue
            needed = c_day * dt_days
            if current_W > needed:
                current_W -= needed
            else:
                time_to_zero = current_W / c_day if c_day > 0 else INF
                t_hit_day = seg_start + time_to_zero
                self.stockout = True
                self.stockout_time = t_hit_day / DAYS_PER_YEAR
                self.W = 0.0
                self.min_W = 0.0
                return self.stockout_time
        self.W = current_W
        if self.W < self.min_W:
            self.min_W = self.W
        return new_t

    def fluid_update(self, new_t: float) -> None:
        if new_t <= self.t:
            return
        start_t = self.t
        reached_t = self.consume_until(new_t)
        dt = reached_t - start_t
        if dt < 0:
            return
        if self.cap_eff > 0:
            delay = self.params.elevator_delay
            dt_supply = max(0.0, reached_t - delay) - max(0.0, start_t - delay)
            if dt_supply > 0:
                self.S += self.cap_eff * dt_supply
        self.t = reached_t

    def schedule_inventory_event(self) -> None:
        if not self.waiting or self.cap_eff <= 0:
            return
        rid = self.waiting[0]
        r = self.rocks.get(rid)
        if r is None:
            return
        needed = r.payload - self.S
        if needed <= 0:
            return
        delay = self.params.elevator_delay
        if self.t < delay:
            ready_time = delay + needed / self.cap_eff
        else:
            ready_time = self.t + needed / self.cap_eff
        if self.inventory_event_time is None or ready_time < self.inventory_event_time:
            self.inventory_event_time = ready_time
            self.schedule_event(ready_time, "inventory")

    def release_waiting(self) -> None:
        while self.waiting:
            rid = self.waiting[0]
            r = self.rocks.get(rid)
            if r is None or r.state == 6:
                self.waiting.pop(0)
                self.waiting_since.pop(rid, None)
                continue
            if self.S < r.payload:
                break
            self.waiting.pop(0)
            wait_start = self.waiting_since.pop(rid, None)
            if wait_start is not None:
                wait_days = (self.t - wait_start) * DAYS_PER_YEAR
                if wait_days > self.max_inventory_wait:
                    self.max_inventory_wait = wait_days
            self.S -= r.payload
            self.schedule_program3(rid, self.t)
        if self.waiting:
            self.schedule_inventory_event()

    def order_replacements(self) -> None:
        target = int(self.I_safe or 0)
        deficit = max(0, target - (self.active_count() + self.pending_replacements))
        if deficit <= 0:
            return
        for _ in range(deficit):
            t_ready = self.t + self.params.delta_replacement
            t_start = max(t_ready, self.next_launch_slot)
            wait = t_start - t_ready
            if wait * DAYS_PER_YEAR > self.max_launch_wait:
                self.max_launch_wait = wait * DAYS_PER_YEAR
            self.next_launch_slot = t_start + 1.0 / self.params.f_total
            self.pending_replacements += 1
            self.schedule_event(t_start, "insert")

    def handle_insert(self) -> None:
        self.pending_replacements = max(0, self.pending_replacements - 1)
        self.add_rocket(self.start_state)
        self.launches += 1
        self.update_deficit()

    def record_arrival(self, rid: int, from_elevator: Optional[bool]) -> None:
        arrival_day = self.t * DAYS_PER_YEAR
        gap = arrival_day - self.last_arrival_day
        if gap > self.max_gap_days:
            self.max_gap_days = gap
        self.last_arrival_day = arrival_day
        self.arrivals += 1
        if from_elevator is False:
            self.direct_arrivals += 1
        self.W += self.q_water
        if self.W < self.min_W:
            self.min_W = self.W
        r = self.rocks.get(rid)
        if r is not None:
            r.last_delivery_time = self.t

    def handle_rocket_event(self, rid: int) -> None:
        r = self.rocks.get(rid)
        if r is None or r.state == 6:
            return
        state = r.state
        pf = self.params.p_fail.get(state, 0.0)
        if self.rng.random() < pf:
            r.state = 6
            self.failures += 1
            self.order_replacements()
            self.update_deficit()
            return

        if state == 3:
            self.record_arrival(rid, r.loaded_from_elevator)

        next_state = self.phi.get(state)
        if next_state is None:
            return
        r.state = next_state

        if next_state == 3 and requires_inventory(self.params.scenario, state, next_state):
            r.loaded_from_elevator = True
            if self.cap_eff <= 0:
                return
            if self.S >= r.payload:
                self.S -= r.payload
                self.schedule_program3(rid, self.t)
            else:
                self.waiting.append(rid)
                self.waiting_since[rid] = self.t
                if len(self.waiting) > self.max_inventory_queue:
                    self.max_inventory_queue = len(self.waiting)
                self.schedule_inventory_event()
        else:
            if next_state == 3:
                r.loaded_from_elevator = False
                self.schedule_program3(rid, self.t)
            else:
                self.schedule_event(self.t + self.tau_robust[next_state], "rocket", rid=rid)

    def run(self) -> SimulationResult:
        init_count = self.params.initial_rockets
        if init_count is None:
            init_count = int(self.I_safe or 0)

        for _ in range(int(init_count)):
            self.add_rocket(self.start_state)

        t_end = self.params.d_days / DAYS_PER_YEAR
        while self.pq:
            ev = heapq.heappop(self.pq)
            if ev.time > t_end:
                break
            self.fluid_update(ev.time)
            if self.stockout:
                break

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

        if not self.stockout:
            self.fluid_update(t_end)

        gap_end = self.params.d_days - self.last_arrival_day
        if gap_end > self.max_gap_days:
            self.max_gap_days = gap_end

        stockout_duration = 0.0
        if self.stockout and self.stockout_time is not None:
            stockout_duration = max(
                0.0, self.params.d_days - self.stockout_time * DAYS_PER_YEAR
            )

        return SimulationResult(
            stockout=self.stockout,
            stockout_time_year=self.stockout_time,
            stockout_duration_days=stockout_duration,
            min_inventory=self.min_W,
            max_gap_days=self.max_gap_days,
            arrivals=self.arrivals,
            direct_arrivals=self.direct_arrivals,
            failures=self.failures,
            launches=self.launches,
            max_deficit=self.max_deficit,
            max_inventory_queue=self.max_inventory_queue,
            max_inventory_wait_days=self.max_inventory_wait,
            max_launch_wait_days=self.max_launch_wait,
            down_ratio=self.params.down_ratio,
            W_end=self.W,
        )


def summarize_results(
    results: List[SimulationResult],
    params: Task3Params,
) -> Dict[str, Any]:
    gross_day = gross_per_day(params)
    W_gross = gross_day * params.d_days
    W_net_base = W_gross * (1.0 - params.r_base)
    min_r = max(0.0, params.r_base - params.delta_r)
    W_net_max = W_gross * (1.0 - min_r)
    c_base = gross_day * (1.0 - params.r_base)
    c_max = gross_day * (1.0 - min_r)

    max_gaps = [r.max_gap_days for r in results]
    gap_q = quantile(max_gaps, params.alpha)
    S_moon_star = c_max * gap_q

    stockout_runs = sum(1 for r in results if r.stockout)
    feasible_runs = len(results) - stockout_runs

    def mean(values: Sequence[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    arrivals = [r.arrivals for r in results]
    direct_arrivals = [r.direct_arrivals for r in results]
    failures = [r.failures for r in results]
    launches = [r.launches for r in results]
    min_inv = [r.min_inventory for r in results]
    max_inv_queue = [r.max_inventory_queue for r in results]
    max_inv_wait = [r.max_inventory_wait_days for r in results]
    max_launch_wait = [r.max_launch_wait_days for r in results]

    costs: List[float] = []
    year_scale = params.d_days / DAYS_PER_YEAR
    q_water = params.eta_pack * params.Cap_Rock
    for r in results:
        if params.scenario == 1:
            M_se_water = W_net_base
        elif params.scenario == 2:
            M_se_water = 0.0
        else:
            M_se_water = max(0.0, W_net_base - r.direct_arrivals * q_water)
        if params.scenario == 2:
            C_water = params.C_launch * r.arrivals
        else:
            C_water = (
                params.C_launch * r.arrivals
                + params.C_elec_unit * M_se_water
                + params.C_maint * year_scale
                + params.C_TV_fixed
            )
        costs.append(C_water)

    summary = {
        "runs": len(results),
        "feasible_runs": feasible_runs,
        "stockout_runs": stockout_runs,
        "W_gross_ton": W_gross,
        "W_net_base_ton": W_net_base,
        "W_net_max_ton": W_net_max,
        "c_base_ton_per_day": c_base,
        "c_max_ton_per_day": c_max,
        "max_gap_quantile_days": gap_q,
        "S_moon_star_ton": S_moon_star,
        "mean_min_inventory_ton": mean(min_inv),
        "min_inventory_ton": min(min_inv) if min_inv else 0.0,
        "mean_arrivals": mean(arrivals),
        "mean_direct_arrivals": mean(direct_arrivals),
        "mean_failures": mean(failures),
        "mean_launches": mean(launches),
        "max_inventory_queue": max(max_inv_queue) if max_inv_queue else 0,
        "max_inventory_wait_days": max(max_inv_wait) if max_inv_wait else 0.0,
        "max_launch_wait_days": max(max_launch_wait) if max_launch_wait else 0.0,
        "mean_cost_usd": mean(costs),
        "min_cost_usd": min(costs) if costs else 0.0,
        "max_cost_usd": max(costs) if costs else 0.0,
    }
    return summary


def run_monte_carlo(
    params: Task3Params,
    n_runs: int,
) -> Tuple[List[SimulationResult], Dict[str, Any]]:
    results: List[SimulationResult] = []
    for i in range(n_runs):
        sim = Task3DES(params, seed=params.seed + i)
        results.append(sim.run())
    summary = summarize_results(results, params)
    return results, summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Task 3 one-year water buffer model (latex-aligned)"
    )
    parser.add_argument("--config", type=str, default=None, help="Path to JSON config")
    parser.add_argument("--scenario", type=int, default=None, help="Scenario 1/2/3")
    parser.add_argument("--n-mc", type=int, default=50, help="Monte Carlo runs")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument("--S-moon", type=float, default=None, help="Initial safety stock (ton)")
    parser.add_argument("--w-person", type=float, default=None, help="Per-capita gross water use (kg/day)")
    parser.add_argument("--r-base", type=float, default=None, help="Baseline recovery rate")
    parser.add_argument("--delta-r", type=float, default=None, help="Recovery drop during degradation")
    parser.add_argument("--r-degrade-start", type=float, default=None, help="Degradation start day")
    parser.add_argument("--r-degrade-end", type=float, default=None, help="Degradation end day")
    parser.add_argument("--eta-pack", type=float, default=None, help="Water packing efficiency")
    parser.add_argument("--kappa-svc", type=float, default=None, help="Service time multiplier")
    parser.add_argument("--alpha", type=float, default=None, help="Confidence level for safety stock")
    args = parser.parse_args()

    params = Task3Params()
    if args.config:
        overrides = load_config(args.config)
        params = apply_overrides(params, overrides)
    data = asdict(params)
    if args.scenario is not None:
        data["scenario"] = args.scenario
    if args.seed is not None:
        data["seed"] = args.seed
    if args.S_moon is not None:
        data["S_moon"] = args.S_moon
    if args.w_person is not None:
        data["w_person"] = args.w_person
    if args.r_base is not None:
        data["r_base"] = args.r_base
    if args.delta_r is not None:
        data["delta_r"] = args.delta_r
    if args.r_degrade_start is not None:
        data["r_degrade_start"] = args.r_degrade_start
    if args.r_degrade_end is not None:
        data["r_degrade_end"] = args.r_degrade_end
    if args.eta_pack is not None:
        data["eta_pack"] = args.eta_pack
    if args.kappa_svc is not None:
        data["kappa_svc"] = args.kappa_svc
    if args.alpha is not None:
        data["alpha"] = args.alpha

    params = Task3Params(**data)
    validate_params(params)

    _, summary = run_monte_carlo(params, n_runs=args.n_mc)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
