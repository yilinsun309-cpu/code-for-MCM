import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from collections import defaultdict, deque
import heapq
import random
import math
import time
import os
from concurrent.futures import ProcessPoolExecutor, as_completed

# ============================================================
#                 Scenario 3 Simulation (Your model)
#      (保留核心逻辑；提供 quiet heapq run 以便优化更快)
# ============================================================

class Program(Enum):
    PROGRAM_2 = 2
    PROGRAM_3 = 3
    PROGRAM_4 = 4
    FAILURE = 6


@dataclass
class Rocket:
    launch_site_id: int
    rocket_id: int
    current_program: Program
    completion_time: float
    total_cargo: float
    total_fuel_cost: float
    cargo_capacity: float
    assigned_elevator: Optional[int] = None
    cargo_onboard: float = 0.0
    total_env_cost: float = 0.0


class SpaceElevatorLoadingQueue:
    def __init__(self, elevator_id: int, loading_capacity: float):
        self.elevator_id = elevator_id
        self.loading_capacity = float(loading_capacity)
        self.daily_loading = defaultdict(float)  # day -> used capacity

    def get_available_loading_time(self, arrival_time: float, cargo_amount: float) -> float:
        current_day = int(np.floor(arrival_time))
        day = current_day
        max_search_days = 200000  # 足够大防止极端
        for _ in range(max_search_days):
            used = self.daily_loading[day]
            if self.loading_capacity - used >= cargo_amount:
                start = max(arrival_time, float(day))
                self.daily_loading[day] += cargo_amount
                return start
            day += 1
        # 极端情况兜底
        return arrival_time


class LunarTransportSimulationScenario3:
    def __init__(
        self,
        total_demand: float = 1e8,
        t0: float = 0.0,
        seed: Optional[int] = 2026,
        annual_rocket_increase: int = 100,
        max_years: Optional[int] = None,
    ):
        self.total_demand = float(total_demand)
        self.t0 = float(t0)
        self.current_time = float(t0)
        self.rng = np.random.default_rng(seed)

        self.annual_rocket_increase = int(annual_rocket_increase)
        self.max_years = max_years

        self.rockets: List[Rocket] = []
        self.space_elevators: Dict[int, dict] = {}
        self.elevator_queues: Dict[int, SpaceElevatorLoadingQueue] = {}
        self.launch_sites: Dict[int, dict] = {}

        self.program_time: Dict[Program, float] = {
            Program.PROGRAM_2: 0.5,
            Program.PROGRAM_3: 3.0,
            Program.PROGRAM_4: 3.0,
        }
        self.program_fuel_cost: Dict[Program, float] = {
            Program.PROGRAM_2: 3000.0,
            Program.PROGRAM_3: 8.2,
            Program.PROGRAM_4: 2.353,
            Program.FAILURE: 0.0,
        }
        self.program_env_lambda: Dict[Program, float] = {
            Program.PROGRAM_2: 3.0,
            Program.PROGRAM_3: 0.1,
            Program.PROGRAM_4: 1.3,
            Program.FAILURE: 0.0,
        }
        self.elevator_env_lambda: float = 0.4

        self.failure_prob: Dict[Program, float] = {
            Program.PROGRAM_2: 0.02,
            Program.PROGRAM_3: 0.05,
            Program.PROGRAM_4: 0.03,
        }

        self.transition_det = {
            Program.PROGRAM_2: Program.PROGRAM_3,
            Program.PROGRAM_3: Program.PROGRAM_4,
            Program.PROGRAM_4: Program.PROGRAM_3,
        }

        self.programs_need_elevator_loading = {Program.PROGRAM_4}

        self.stats = {
            'total_deliveries': 0,
            'total_failures': 0,
            'rockets_by_site': defaultdict(int),
            'elevator_waiting_time': [],
            'total_expansions': 0,
        }

        self._next_expansion_time = self.t0 + 365.0
        self._expansion_count = 0
        self._event_seq = 0

    # ------- config -------
    def add_space_elevator(self, elevator_id: int, loading_capacity: float, unit_fuel_cost: float = 0.5):
        self.space_elevators[elevator_id] = {
            'loading_capacity': float(loading_capacity),
            'unit_fuel_cost': float(unit_fuel_cost)
        }
        self.elevator_queues[elevator_id] = SpaceElevatorLoadingQueue(elevator_id, loading_capacity)

    def add_launch_site(
        self,
        site_id: int,
        site_name: str,
        launch_interval: float,
        initial_launch_time: float,
        num_rockets_initial: int,
        rocket_capacity: float = 150.0
    ):
        self.launch_sites[site_id] = {
            'name': site_name,
            'launch_interval': float(launch_interval),
            'initial_launch_time': float(initial_launch_time),
            'num_rockets_initial': int(num_rockets_initial),
            'rocket_capacity': float(rocket_capacity),
            'next_rocket_id': 0,
        }

    # ------- launch windows (保留你原有实现；优化想更快可进一步改成纯解析) -------
    def get_launch_time_set(self, site_id: int, max_time: float = 100000.0):
        site = self.launch_sites[site_id]
        gamma = site['initial_launch_time']
        p = site['launch_interval']
        times = set()
        n = 0
        while True:
            t = gamma + n * p
            if t > max_time:
                break
            if t >= self.t0:
                times.add(t)
            n += 1
        return times

    def get_next_launch_time(self, site_id: int, current_time: float, launch_times=None) -> float:
        if launch_times is None:
            launch_times = self.get_launch_time_set(site_id)
        valid = [t for t in launch_times if t >= current_time]
        if valid:
            return min(valid)

        site = self.launch_sites[site_id]
        gamma = site['initial_launch_time']
        p = site['launch_interval']
        if current_time <= gamma:
            return gamma
        n = int(np.ceil((current_time - gamma) / p))
        return gamma + n * p

    # ------- costs -------
    def _add_cost(self, rocket: Rocket, fuel_delta: float, env_lambda: float):
        rocket.total_fuel_cost += float(fuel_delta)
        rocket.total_env_cost += float(env_lambda) * float(fuel_delta)

    def get_total_cargo(self) -> float:
        return sum(r.total_cargo for r in self.rockets)

    def get_total_fuel_cost(self) -> float:
        return sum(r.total_fuel_cost for r in self.rockets)

    def get_total_env_cost(self) -> float:
        return sum(r.total_env_cost for r in self.rockets)

    # ------- create rockets -------
    def _create_rocket(self, site_id: int, request_time: float) -> Rocket:
        site = self.launch_sites[site_id]
        rocket_id = site['next_rocket_id']
        site['next_rocket_id'] += 1

        initial_program = Program.PROGRAM_2

        launch_times = self.get_launch_time_set(site_id)
        launch_time = self.get_next_launch_time(site_id, request_time, launch_times)
        completion_time = launch_time + self.program_time[initial_program]

        assigned_elevator = list(self.space_elevators.keys())[0] if self.space_elevators else None

        rocket = Rocket(
            launch_site_id=site_id,
            rocket_id=rocket_id,
            current_program=initial_program,
            completion_time=completion_time,
            total_cargo=0.0,
            total_fuel_cost=0.0,
            cargo_capacity=site['rocket_capacity'],
            assigned_elevator=assigned_elevator,
            cargo_onboard=0.0,
            total_env_cost=0.0
        )
        self.stats['rockets_by_site'][site_id] += 1

        # 创建即计一次 PROGRAM_2 成本（与原一致）
        self._add_cost(rocket, self.program_fuel_cost[initial_program], self.program_env_lambda[initial_program])
        return rocket

    def initialize_rockets(self):
        for site_id, site in self.launch_sites.items():
            for _ in range(site['num_rockets_initial']):
                self.rockets.append(self._create_rocket(site_id, request_time=self.t0))

    def apply_annual_expansion(self, t_expand: float):
        if self.annual_rocket_increase <= 0:
            return
        if self.max_years is not None and self._expansion_count >= self.max_years:
            self._next_expansion_time = np.inf
            return

        for site_id in self.launch_sites.keys():
            for _ in range(self.annual_rocket_increase):
                self.rockets.append(self._create_rocket(site_id, request_time=t_expand))

        self._expansion_count += 1
        self.stats['total_expansions'] += 1
        self._next_expansion_time = self.t0 + 365.0 * (self._expansion_count + 1)

    # ------- stochastic transition -------
    def get_next_program_stochastic(self, current_program: Program) -> Program:
        if current_program == Program.FAILURE:
            return Program.FAILURE
        nxt = self.transition_det.get(current_program, current_program)
        if self.rng.random() < self.failure_prob.get(current_program, 0.0):
            return Program.FAILURE
        return nxt

    # ------- loading policy A -------
    def ground_load_if_needed(self, rocket: Rocket, entering_program: Program):
        if entering_program == Program.PROGRAM_2:
            rocket.cargo_onboard = rocket.cargo_capacity

    def elevator_load_and_get_time(self, rocket: Rocket, arrival_time: float) -> float:
        if rocket.assigned_elevator is None:
            return arrival_time
        q = rocket.cargo_capacity
        queue = self.elevator_queues[rocket.assigned_elevator]
        t_load = queue.get_available_loading_time(arrival_time, q)
        wait = t_load - arrival_time
        if wait > 0:
            self.stats['elevator_waiting_time'].append(wait)
        rocket.cargo_onboard = q
        return t_load

    # ------- update rocket -------
    def update_rocket_state(self, rocket: Rocket):
        cur = rocket.current_program
        if cur == Program.FAILURE:
            rocket.completion_time = np.inf
            return

        # unload at PROGRAM_3
        if cur == Program.PROGRAM_3:
            delivered = rocket.cargo_onboard
            if delivered > 0:
                rocket.total_cargo += delivered
                self.stats['total_deliveries'] += 1
            rocket.cargo_onboard = 0.0

        # cost of current program (与你原逻辑一致：到达事件时加一次)
        self._add_cost(rocket, self.program_fuel_cost[cur], self.program_env_lambda.get(cur, 0.0))

        # extra elevator fuel + env when PROGRAM_3
        if cur == Program.PROGRAM_3 and rocket.assigned_elevator is not None:
            elev_id = rocket.assigned_elevator
            elevator_fuel = rocket.cargo_capacity * self.space_elevators[elev_id]['unit_fuel_cost']
            self._add_cost(rocket, elevator_fuel, self.elevator_env_lambda)

        nxt = self.get_next_program_stochastic(cur)
        if nxt == Program.FAILURE:
            rocket.current_program = Program.FAILURE
            rocket.completion_time = np.inf
            self.stats['total_failures'] += 1
            return

        base_t = rocket.completion_time
        entering = nxt

        # load on ground if enter program2
        self.ground_load_if_needed(rocket, entering)

        start_t = base_t
        if entering == Program.PROGRAM_2:
            launch_times = self.get_launch_time_set(rocket.launch_site_id)
            start_t = self.get_next_launch_time(rocket.launch_site_id, base_t, launch_times)

        finish_t = start_t + self.program_time[entering]
        rocket.current_program = entering
        rocket.completion_time = finish_t

        # program4 needs elevator loading then immediate transition
        if entering in self.programs_need_elevator_loading and rocket.assigned_elevator is not None:
            arrival = finish_t
            load_time = self.elevator_load_and_get_time(rocket, arrival)

            after_load = self.get_next_program_stochastic(entering)
            if after_load == Program.FAILURE:
                rocket.current_program = Program.FAILURE
                rocket.completion_time = np.inf
                self.stats['total_failures'] += 1
                return

            self.ground_load_if_needed(rocket, after_load)
            rocket.current_program = after_load
            rocket.completion_time = load_time + self.program_time[after_load]

    # ------- heap events -------
    def _push_event(self, heap: List[Tuple[float, int, str, Any]], t: float, etype: str, payload: Any):
        if not np.isfinite(t):
            return
        self._event_seq += 1
        heapq.heappush(heap, (float(t), self._event_seq, etype, payload))


def setup_scenario_3(
    total_demand: float = 1e6,
    num_rockets_per_site_initial: int = 10,
    elevator_capacity: float = 1000.0,
    seed: Optional[int] = 2026,
    annual_increase: int = 100
) -> LunarTransportSimulationScenario3:
    sim = LunarTransportSimulationScenario3(
        total_demand=total_demand,
        t0=0.0,
        seed=seed,
        annual_rocket_increase=annual_increase,
        max_years=None
    )

    sim.add_space_elevator(elevator_id=1, loading_capacity=elevator_capacity, unit_fuel_cost=0.5)

    launch_sites_data = [
        (1, "加利福尼亚", 10.14, 9,   num_rockets_per_site_initial, 150),
        (2, "德克萨斯",   73.0, 15,  num_rockets_per_site_initial, 150),
        (3, "佛罗里达",   36.5, 3,   num_rockets_per_site_initial, 150),
        (4, "弗吉尼亚",   365.0, 351, num_rockets_per_site_initial, 150),
        (5, "哈萨克斯坦", 60.83, 57,  num_rockets_per_site_initial, 150),
        (6, "法属圭亚那", 52.14, 64,  num_rockets_per_site_initial, 150),
        (7, "印度",       73.0, 28,  num_rockets_per_site_initial, 150),
        (8, "中国",       30.42, 22,  num_rockets_per_site_initial, 150),
        (9, "新西兰",     21.47, 38,  num_rockets_per_site_initial, 150),
    ]
    for site_data in launch_sites_data:
        sim.add_launch_site(*site_data)
    return sim


# ============================================================
#          Quiet run for Scenario 3 (same idea as scenario2)
# ============================================================

def _scenario3_run_heapq_quiet(
    self: LunarTransportSimulationScenario3,
    log_level: int = 0,
    record_interval: int = 10**9,
    print_every: int = 10**9,
    iteration_limit: int = 2_000_000_000
) -> Dict[str, Any]:

    self.initialize_rockets()

    heap: List[Tuple[float, int, str, Any]] = []
    self._push_event(heap, self._next_expansion_time, 'expand', None)

    for idx, r in enumerate(self.rockets):
        self._push_event(heap, r.completion_time, 'rocket', idx)

    iteration = 0
    termination_reason = "unknown"

    while True:
        if self.get_total_cargo() >= self.total_demand:
            termination_reason = "demand_met"
            break
        if not heap:
            termination_reason = "all_failed_or_stalled"
            break

        t = heap[0][0]
        self.current_time = t

        events_at_t = []
        while heap and abs(heap[0][0] - t) < 1e-12:
            events_at_t.append(heapq.heappop(heap))

        for _, _, etype, payload in events_at_t:
            if etype == 'expand':
                if abs(self._next_expansion_time - t) > 1e-9:
                    continue
                old_len = len(self.rockets)
                self.apply_annual_expansion(t)
                new_len = len(self.rockets)
                for idx2 in range(old_len, new_len):
                    self._push_event(heap, self.rockets[idx2].completion_time, 'rocket', idx2)
                self._push_event(heap, self._next_expansion_time, 'expand', None)
                iteration += 1

            elif etype == 'rocket':
                idx = int(payload)
                if idx < 0 or idx >= len(self.rockets):
                    continue
                r = self.rockets[idx]
                if not np.isfinite(r.completion_time):
                    continue
                if abs(r.completion_time - t) > 1e-9:
                    continue

                self.update_rocket_state(r)
                if np.isfinite(r.completion_time) and r.current_program != Program.FAILURE:
                    self._push_event(heap, r.completion_time, 'rocket', idx)
                iteration += 1

            else:
                raise RuntimeError(f"Unknown event type: {etype}")

            if iteration > iteration_limit:
                termination_reason = "iteration_limit"
                break

        if termination_reason == "iteration_limit":
            break

    return {
        'completion_time': float(self.current_time),
        'total_fuel_cost': float(self.get_total_fuel_cost()),
        'total_env_cost': float(self.get_total_env_cost()),
        'termination_reason': termination_reason,
    }

# monkey patch
LunarTransportSimulationScenario3.run = _scenario3_run_heapq_quiet


# ============================================================
#                  NSGA-II 
# ============================================================

@dataclass(frozen=True)
class Decision:
    num_rockets_per_site_initial: int
    annual_increase: int


@dataclass
class Individual:
    x: Decision
    f: Tuple[float, float, float] = (math.inf, math.inf, math.inf)
    rank: int = 10**9
    crowding: float = 0.0


def dominates(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> bool:
    return all(x <= y for x, y in zip(a, b)) and any(x < y for x, y in zip(a, b))


def fast_non_dominated_sort(pop: List[Individual]) -> List[List[Individual]]:
    S: Dict[int, List[int]] = {}
    n = [0] * len(pop)
    fronts: List[List[int]] = [[]]

    for p in range(len(pop)):
        S[p] = []
        n[p] = 0
        for q in range(len(pop)):
            if p == q:
                continue
            if dominates(pop[p].f, pop[q].f):
                S[p].append(q)
            elif dominates(pop[q].f, pop[p].f):
                n[p] += 1
        if n[p] == 0:
            pop[p].rank = 0
            fronts[0].append(p)

    i = 0
    while fronts[i]:
        next_front = []
        for p in fronts[i]:
            for q in S[p]:
                n[q] -= 1
                if n[q] == 0:
                    pop[q].rank = i + 1
                    next_front.append(q)
        i += 1
        fronts.append(next_front)

    out: List[List[Individual]] = []
    for fr in fronts[:-1]:
        out.append([pop[idx] for idx in fr])
    return out


def crowding_distance(front: List[Individual]) -> None:
    if not front:
        return
    m = 3
    for ind in front:
        ind.crowding = 0.0

    for obj in range(m):
        front.sort(key=lambda x: x.f[obj])
        front[0].crowding = float("inf")
        front[-1].crowding = float("inf")

        f_min = front[0].f[obj]
        f_max = front[-1].f[obj]
        if f_max - f_min < 1e-12:
            continue

        for i in range(1, len(front) - 1):
            front[i].crowding += (front[i + 1].f[obj] - front[i - 1].f[obj]) / (f_max - f_min)


def tournament_select(pop: List[Individual], k: int = 2) -> Individual:
    cand = random.sample(pop, k)
    cand.sort(key=lambda ind: (ind.rank, -ind.crowding))
    return cand[0]


def clip_int(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(v)))


def crossover(p1: Decision, p2: Decision, pc: float = 0.9) -> Tuple[Decision, Decision]:
    if random.random() > pc:
        return p1, p2
    if random.random() < 0.5:
        return Decision(p1.num_rockets_per_site_initial, p2.annual_increase), Decision(p2.num_rockets_per_site_initial, p1.annual_increase)
    return Decision(p2.num_rockets_per_site_initial, p1.annual_increase), Decision(p1.num_rockets_per_site_initial, p2.annual_increase)


def mutate(x: Decision, pm: float = 0.30) -> Decision:
    n0 = x.num_rockets_per_site_initial
    ainc = x.annual_increase

    if random.random() < pm:
        n0 += random.choice([-10, -5, -3, -2, -1, 1, 2, 3, 5, 10]) if random.random() < 0.85 else random.randint(-30, 30)
    if random.random() < pm:
        ainc += random.choice([-3, -2, -1, 1, 2, 3]) if random.random() < 0.85 else random.randint(-6, 6)

    # ✅ 按你要求：n0 ∈ [50,100], ainc ∈ [0,10]
    return Decision(clip_int(n0, 50, 100), clip_int(ainc, 0, 10))


def _fmt_hms(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}h{m:02d}m{s:02d}s"
    if m > 0:
        return f"{m}m{s:02d}s"
    return f"{s}s"


# ============================================================
#     Parallel worker: Evaluate one (n0, ainc) with multiple seeds
# ============================================================

def _worker_eval_one_s3(args: Tuple[float, float, int, int, List[int], bool, int]) -> Tuple[Tuple[int, int], Tuple[float, float, float]]:
    """
    args = (total_demand, elevator_capacity, n0, ainc, seeds, use_median, sim_iteration_limit)
    return ((n0, ainc), (T, Fuel, Env))
    """
    total_demand, elevator_capacity, n0, ainc, seeds, use_median, sim_iteration_limit = args

    vals = []
    for sd in seeds:
        sim = setup_scenario_3(
            total_demand=total_demand,
            elevator_capacity=elevator_capacity,
            seed=int(sd),
            num_rockets_per_site_initial=int(n0),
            annual_increase=int(ainc)
        )
        res = sim.run(iteration_limit=int(sim_iteration_limit))
        vals.append((res["completion_time"], res["total_fuel_cost"], res["total_env_cost"]))

    arr = np.array(vals, dtype=float)
    f = tuple((np.median(arr, axis=0) if use_median else np.mean(arr, axis=0)).tolist())
    return (int(n0), int(ainc)), (float(f[0]), float(f[1]), float(f[2]))


class Scenario3Evaluator:
    """
    与情景2一致：主进程 cache + 并行批量评估
    """
    def __init__(
        self,
        total_demand: float,
        elevator_capacity: float,
        base_seed: int = 2026,
        replications: int = 1,
        use_median: bool = False,
        sim_iteration_limit: int = 2_000_000_000,
    ):
        self.total_demand = float(total_demand)
        self.elevator_capacity = float(elevator_capacity)
        self.base_seed = int(base_seed)
        self.replications = int(replications)
        self.use_median = bool(use_median)

        rng = np.random.default_rng(self.base_seed)
        self.seeds = [int(s) for s in rng.integers(1, 2_000_000_000, size=self.replications)]

        self.cache: Dict[Tuple[int, int], Tuple[float, float, float]] = {}
        self.calls = 0
        self.cache_hits = 0
        self.sim_iteration_limit = int(sim_iteration_limit)

    def evaluate_one_cached(self, x: Decision) -> Optional[Tuple[float, float, float]]:
        self.calls += 1
        key = (x.num_rockets_per_site_initial, x.annual_increase)
        if key in self.cache:
            self.cache_hits += 1
            return self.cache[key]
        return None

    def put_cache(self, key: Tuple[int, int], f: Tuple[float, float, float]) -> None:
        self.cache[key] = f


class NSGA2Optimizer:
    def __init__(
        self,
        evaluator: Scenario3Evaluator,
        pop_size: int = 40,
        generations: int = 25,
        seed: int = 123,
        verbose: bool = True,
        parallel: bool = True,
        n_jobs: Optional[int] = None,
        eval_progress_every: int = 5,
        eval_progress_secs: float = 2.0,
        eval_timing_window: int = 10,
    ):
        self.evaluator = evaluator
        self.pop_size = int(pop_size)
        self.generations = int(generations)
        self.seed = int(seed)
        self.verbose = bool(verbose)

        self.parallel = bool(parallel)
        if n_jobs is None:
            cpu = os.cpu_count() or 2
            self.n_jobs = max(1, cpu - 1)
        else:
            self.n_jobs = max(1, int(n_jobs))

        self.eval_progress_every = max(1, int(eval_progress_every))
        self.eval_progress_secs = float(eval_progress_secs)
        self.eval_timing_window = max(3, int(eval_timing_window))

        random.seed(self.seed)
        np.random.seed(self.seed)

        self._t0 = None
        self._last_heartbeat_t = 0.0
        self._recent_task_times = deque(maxlen=self.eval_timing_window)
        self._last_eval_f: Optional[Tuple[float, float, float]] = None

    def _random_decision(self) -> Decision:
        # ✅ 按你要求范围
        return Decision(random.randint(50, 100), random.randint(0, 10))

    def _maybe_heartbeat(self, stage: str, done: int, total: int):
        if not self.verbose:
            return
        now = time.perf_counter()
        if now - self._last_heartbeat_t < self.eval_progress_secs:
            return
        if (done % self.eval_progress_every != 0) and (done != total):
            return

        self._last_heartbeat_t = now
        elapsed = now - self._t0 if self._t0 else 0.0
        hit_rate = (self.evaluator.cache_hits / self.evaluator.calls) if self.evaluator.calls else 0.0

        if len(self._recent_task_times) >= 3:
            avg = sum(self._recent_task_times) / len(self._recent_task_times)
            eta = avg * max(0, total - done)
            eta_str = _fmt_hms(eta)
            avg_str = f"{avg:.2f}s/task"
        else:
            eta_str = "estimating..."
            avg_str = "n/a"

        last = self._last_eval_f
        last_str = f"last(T={last[0]:.1f},F={last[1]:.2e},E={last[2]:.2e})" if last else "last(None)"

        print(
            f"[NSGA-II][{stage}] {done}/{total} | jobs={self.n_jobs} "
            f"| cache={len(self.evaluator.cache)} hit={hit_rate*100:4.1f}% "
            f"| avg={avg_str} ETA={eta_str} | {last_str} | elapsed={_fmt_hms(elapsed)}"
        )

    def _eval_pop(self, pop: List[Individual], stage: str) -> None:
        targets = [ind for ind in pop if not np.isfinite(ind.f[0])]
        if not targets:
            return

        uniq: Dict[Tuple[int, int], List[Individual]] = defaultdict(list)
        for ind in targets:
            key = (ind.x.num_rockets_per_site_initial, ind.x.annual_increase)
            uniq[key].append(ind)

        pending_keys: List[Tuple[int, int]] = []
        for key, inds in uniq.items():
            cached = self.evaluator.evaluate_one_cached(inds[0].x)
            if cached is not None:
                for ii in inds:
                    ii.f = cached
                self._last_eval_f = cached
            else:
                pending_keys.append(key)

        total_tasks = len(pending_keys)
        if total_tasks == 0:
            return

        done_tasks = 0
        t_stage_start = time.perf_counter()

        if self.parallel and self.n_jobs > 1 and total_tasks > 1:
            args_list = [
                (self.evaluator.total_demand, self.evaluator.elevator_capacity, n0, ainc,
                 self.evaluator.seeds, self.evaluator.use_median, self.evaluator.sim_iteration_limit)
                for (n0, ainc) in pending_keys
            ]
            with ProcessPoolExecutor(max_workers=self.n_jobs) as ex:
                futures = {ex.submit(_worker_eval_one_s3, args): args for args in args_list}

                for fut in as_completed(futures):
                    t1 = time.perf_counter()
                    key, f = fut.result()
                    t2 = time.perf_counter()

                    self.evaluator.put_cache(key, f)

                    for ii in uniq[key]:
                        ii.f = f

                    self._last_eval_f = f
                    done_tasks += 1

                    self._recent_task_times.append(t2 - t1)
                    self._maybe_heartbeat(stage, done_tasks, total_tasks)

        else:
            for key in pending_keys:
                n0, ainc = key
                t1 = time.perf_counter()
                key2, f = _worker_eval_one_s3(
                    (self.evaluator.total_demand, self.evaluator.elevator_capacity, n0, ainc,
                     self.evaluator.seeds, self.evaluator.use_median, self.evaluator.sim_iteration_limit)
                )
                t2 = time.perf_counter()

                self.evaluator.put_cache(key2, f)
                for ii in uniq[key2]:
                    ii.f = f

                self._last_eval_f = f
                done_tasks += 1
                self._recent_task_times.append(t2 - t1)
                self._maybe_heartbeat(stage, done_tasks, total_tasks)

        if self.verbose:
            elapsed_stage = time.perf_counter() - t_stage_start
            self._last_heartbeat_t = 0.0
            self._maybe_heartbeat(stage, total_tasks, total_tasks)
            print(f"[NSGA-II][{stage}] stage_done | tasks={total_tasks} | stage_elapsed={_fmt_hms(elapsed_stage)}")

    def _assign_rank_and_crowding(self, pop: List[Individual]) -> List[List[Individual]]:
        fronts = fast_non_dominated_sort(pop)
        for fr in fronts:
            crowding_distance(fr)
        return fronts

    def _make_offspring(self, pop: List[Individual]) -> List[Individual]:
        offspring: List[Individual] = []
        while len(offspring) < self.pop_size:
            p1 = tournament_select(pop).x
            p2 = tournament_select(pop).x
            c1x, c2x = crossover(p1, p2, pc=0.9)
            c1x = mutate(c1x, pm=0.30)
            c2x = mutate(c2x, pm=0.30)
            offspring.append(Individual(x=c1x))
            if len(offspring) < self.pop_size:
                offspring.append(Individual(x=c2x))
        return offspring

    def optimize(self) -> Dict[str, Any]:
        self._t0 = time.perf_counter()
        self._last_heartbeat_t = self._t0

        if self.verbose:
            print(f"[NSGA-II] start | pop={self.pop_size} | gens={self.generations} "
                  f"| rep={self.evaluator.replications} | jobs={self.n_jobs} | parallel={self.parallel}")

        pop = [Individual(x=self._random_decision()) for _ in range(self.pop_size)]

        if self.verbose:
            print("[NSGA-II] [Stage Init-Eval] evaluating initial population...")
        self._eval_pop(pop, stage="Init-Eval")
        self._assign_rank_and_crowding(pop)

        for g in range(1, self.generations + 1):
            if self.verbose:
                print(f"[NSGA-II] [Stage Reproduce] gen={g}: creating offspring...")
            offspring = self._make_offspring(pop)

            if self.verbose:
                print(f"[NSGA-II] [Stage Offspring-Eval] gen={g}: evaluating offspring...")
            self._eval_pop(offspring, stage=f"Offspring-Eval(g={g})")

            combined = pop + offspring
            fronts = self._assign_rank_and_crowding(combined)

            new_pop: List[Individual] = []
            for fr in fronts:
                if len(new_pop) + len(fr) <= self.pop_size:
                    new_pop.extend(fr)
                else:
                    fr.sort(key=lambda ind: -ind.crowding)
                    need = self.pop_size - len(new_pop)
                    new_pop.extend(fr[:need])
                    break
            pop = new_pop

            if self.verbose:
                pareto = fast_non_dominated_sort(pop)[0]
                bestT = min(pareto, key=lambda ind: ind.f[0]).f[0]
                elapsed = time.perf_counter() - self._t0
                hit_rate = (self.evaluator.cache_hits / self.evaluator.calls) if self.evaluator.calls else 0.0
                print(f"[NSGA-II][Gen {g}/{self.generations}] pareto={len(pareto)} bestT={bestT:.2f} "
                      f"cache={len(self.evaluator.cache)} hit={hit_rate*100:.1f}% elapsed={_fmt_hms(elapsed)}")

        pareto = fast_non_dominated_sort(pop)[0]
        uniq2: Dict[Tuple[int, int], Individual] = {}
        for ind in pareto:
            uniq2[(ind.x.num_rockets_per_site_initial, ind.x.annual_increase)] = ind
        pareto = list(uniq2.values())
        pareto.sort(key=lambda ind: ind.f)

        if self.verbose:
            elapsed = time.perf_counter() - self._t0
            print(f"[NSGA-II] done | pareto={len(pareto)} cache={len(self.evaluator.cache)} elapsed={_fmt_hms(elapsed)}")

        return {"pareto": pareto, "cache_size": len(self.evaluator.cache)}


def pick_one_from_pareto(
    pareto: List[Individual],
    weights: Tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> Individual:
    if not pareto:
        raise ValueError("Empty pareto set")
    F = np.array([ind.f for ind in pareto], dtype=float)
    f_min = F.min(axis=0)
    f_max = F.max(axis=0)
    denom = np.maximum(f_max - f_min, 1e-12)
    Fn = (F - f_min) / denom
    score = Fn @ np.array(weights, dtype=float)
    return pareto[int(np.argmin(score))]


# ============================================================
#                          main
# ============================================================

if __name__ == "__main__":
    TOTAL_DEMAND = 1e6
    ELEV_CAP = 179000 / 365 * 3  # 你示例里的电梯装货能力

    evaluator = Scenario3Evaluator(
        total_demand=TOTAL_DEMAND,
        elevator_capacity=ELEV_CAP,
        base_seed=2026,
        replications=1,              # 想更稳可改 3/5
        use_median=False,
        sim_iteration_limit=2_000_000_000
    )

    opt = NSGA2Optimizer(
        evaluator=evaluator,
        pop_size=10,
        generations=2,
        seed=123,
        verbose=True,
        parallel=True,
        n_jobs=None,
        eval_progress_every=1,
        eval_progress_secs=2.0,
        eval_timing_window=10
    )

    result = opt.optimize()
    pareto = result["pareto"]

    print("\n========== Pareto 解集（前 10 个展示）==========")
    for i, ind in enumerate(pareto[:10]):
        print(f"{i:02d} | x=(n0={ind.x.num_rockets_per_site_initial}, ainc={ind.x.annual_increase}) "
              f"| f=(T={ind.f[0]:.2f}, Fuel={ind.f[1]:.3e}, Env={ind.f[2]:.3e})")

    best = pick_one_from_pareto(pareto, weights=(2.0, 1.0, 0.8))
    print("\n========== 推荐解（加权归一化）==========")
    print(f"x=(n0={best.x.num_rockets_per_site_initial}, ainc={best.x.annual_increase}) "
          f"| f=(T={best.f[0]:.2f}, Fuel={best.f[1]:.3e}, Env={best.f[2]:.3e})")
