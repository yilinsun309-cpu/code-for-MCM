import time
import heapq
import numpy as np
import matplotlib.pyplot as plt
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict

# 设置中文字体支持
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


# =========================
#  0) 打印辅助函数
# =========================

def _fmt_float(x: float, nd: int = 3) -> str:
    try:
        return f"{float(x):.{nd}f}"
    except Exception:
        return str(x)

def _fmt_sci(x: float, nd: int = 3) -> str:
    try:
        return f"{float(x):.{nd}e}"
    except Exception:
        return str(x)

def _fmt_int(x: Any) -> str:
    try:
        return f"{int(x)}"
    except Exception:
        return str(x)

def _fmt_pct(x: float, nd: int = 2) -> str:
    try:
        return f"{float(x):.{nd}f}%"
    except Exception:
        return str(x)

def _hline(n: int = 78) -> str:
    return "=" * n

def _sline(n: int = 78) -> str:
    return "-" * n


# =========================
#  1) 情景1仿真器
# =========================

class Program(Enum):
    """情景1：1->3->4->3... + FAILURE"""
    PROGRAM_1 = 1   # 地月运行段A（需要装货放行）
    PROGRAM_3 = 3   # 卸货点：按 cargo_onboard 计入M
    PROGRAM_4 = 4   # 地月运行段B（需要装货放行）
    FAILURE = 6     # 失效（吸收态）


@dataclass
class Rocket:
    rocket_id: int
    current_program: Program
    completion_time: float          # 下一次事件发生时间
    cargo_capacity: float
    assigned_elevator: int          # 组装/运营所属银河港
    cargo_onboard: float = 0.0      # 装货放行成功才>0
    total_cargo: float = 0.0
    total_fuel_cost: float = 0.0
    total_env_cost: float = 0.0     # 累计环境外部成本（与燃料等价成本同单位）


class SpaceElevatorLoadingQueue:
    """银河港装货队列（每日装货能力约束）"""

    def __init__(self, elevator_id: int, loading_capacity: float):
        self.elevator_id = elevator_id
        self.loading_capacity = float(loading_capacity)
        self.daily_loading = defaultdict(float)  # day -> used capacity

    def get_available_loading_time(self, arrival_time: float, cargo_amount: float) -> float:
        day = int(np.floor(arrival_time))
        for _ in range(100000):
            used = self.daily_loading[day]
            if self.loading_capacity - used >= cargo_amount:
                start_time = max(arrival_time, float(day))
                self.daily_loading[day] += cargo_amount
                return start_time
            day += 1
        print(f"[WARN] 银河港 {self.elevator_id} 装货队列搜索超时")
        return arrival_time


class RocketAssemblyLine:
    """
    单条组装线：按 assembly_rate_per_day 匀速输出火箭（枚/天）
    assembly_time = 1 / rate
    """

    def __init__(self, assembly_rate_per_day: float, t0: float = 0.0):
        self.rate = float(assembly_rate_per_day)
        self.assembly_time = np.inf if self.rate <= 0 else 1.0 / self.rate
        self.next_free_time = float(t0)

    def schedule_next_ready(self) -> float:
        if not np.isfinite(self.assembly_time):
            return np.inf
        start = self.next_free_time
        finish = start + self.assembly_time
        self.next_free_time = finish
        return finish


class LunarTransportSimulationScenario1:
    """
    情景1（银河港顺序组装→直接地月运行，无发射场）
    事件堆版 heapq
    """

    def __init__(self, total_demand: float = 1e6, t0: float = 0.0, seed: Optional[int] = 2026,
                 rocket_capacity: float = 100.0):
        self.total_demand = float(total_demand)
        self.t0 = float(t0)
        self.current_time = float(t0)
        self.rng = np.random.default_rng(seed)

        self.rocket_capacity = float(rocket_capacity)

        self.space_elevators: Dict[int, dict] = {}
        self.elevator_queues: Dict[int, SpaceElevatorLoadingQueue] = {}

        self.assembly_lines: Dict[int, RocketAssemblyLine] = {}
        self.next_assembly_ready: Dict[int, float] = {}

        self.rockets: List[Rocket] = []
        self._global_rocket_id = 0

        self.program_time = {
            Program.PROGRAM_1: 14.0,
            Program.PROGRAM_3: 3.0,
            Program.PROGRAM_4: 3.0,
        }
        self.program_fuel_cost = {
            Program.PROGRAM_1: 60.0,
            Program.PROGRAM_3: 8.2,
            Program.PROGRAM_4: 2.353,
            Program.FAILURE: 0.0,
        }

        self.program_env_lambda = {
            Program.PROGRAM_1: 0.1,
            Program.PROGRAM_3: 0.1,
            Program.PROGRAM_4: 1.3,
            Program.FAILURE: 0.0,
        }
        self.elevator_env_lambda = 0.4

        self.failure_prob = {
            Program.PROGRAM_1: 0.10,
            Program.PROGRAM_3: 0.05,
            Program.PROGRAM_4: 0.03,
        }

        self.transition = {
            Program.PROGRAM_1: Program.PROGRAM_3,
            Program.PROGRAM_3: Program.PROGRAM_4,
            Program.PROGRAM_4: Program.PROGRAM_3,
        }

        self.programs_need_elevator_loading = {Program.PROGRAM_1, Program.PROGRAM_4}

        self.stats = {
            'total_deliveries': 0,
            'total_failures': 0,
            'elevator_waiting_time': [],
        }

        self.history = {
            'time': [],
            'total_cargo': [],
            'total_fuel_cost': [],
            'total_env_cost': [],
            'active_rockets': [],
            'failed_rockets': [],
            'completed_deliveries': [],
            'total_rockets': [],
            'elevator_daily_loading': defaultdict(list),
        }

        self._event_seq = 0

    def _add_cost(self, rocket: Rocket, fuel_delta: float, env_lambda: float):
        fuel_delta = float(fuel_delta)
        env_lambda = float(env_lambda)
        rocket.total_fuel_cost += fuel_delta
        rocket.total_env_cost += env_lambda * fuel_delta

    def get_total_cargo(self) -> float:
        return sum(r.total_cargo for r in self.rockets)

    def get_total_fuel_cost(self) -> float:
        return sum(r.total_fuel_cost for r in self.rockets)

    def get_total_env_cost(self) -> float:
        return sum(r.total_env_cost for r in self.rockets)

    def add_space_elevator(self, elevator_id: int, loading_capacity: float, unit_fuel_cost: float = 0.5):
        self.space_elevators[elevator_id] = {
            'loading_capacity': float(loading_capacity),
            'unit_fuel_cost': float(unit_fuel_cost),
        }
        self.elevator_queues[elevator_id] = SpaceElevatorLoadingQueue(elevator_id, loading_capacity)

    def add_elevator_assembly(self, elevator_id: int, assembly_rate_per_day: float):
        line = RocketAssemblyLine(assembly_rate_per_day=assembly_rate_per_day, t0=self.t0)
        self.assembly_lines[elevator_id] = line
        self.next_assembly_ready[elevator_id] = line.schedule_next_ready()

    def _push_event(self, heap: List[Tuple[float, int, str, Any]], t: float, etype: str, payload: Any):
        if not np.isfinite(t):
            return
        self._event_seq += 1
        heapq.heappush(heap, (float(t), self._event_seq, etype, payload))

    def _create_rocket_from_elevator_ready(self, elevator_id: int, ready_time: float) -> Rocket:
        rocket_id = self._global_rocket_id
        self._global_rocket_id += 1

        completion_time = ready_time + self.program_time[Program.PROGRAM_1]

        rocket = Rocket(
            rocket_id=rocket_id,
            current_program=Program.PROGRAM_1,
            completion_time=completion_time,
            cargo_capacity=self.rocket_capacity,
            assigned_elevator=elevator_id,
            cargo_onboard=0.0,
        )

        self._add_cost(
            rocket,
            fuel_delta=self.program_fuel_cost[Program.PROGRAM_1],
            env_lambda=self.program_env_lambda.get(Program.PROGRAM_1, 0.0)
        )

        self.rockets.append(rocket)
        return rocket

    def _next_program(self, cur: Program) -> Program:
        if cur == Program.FAILURE:
            return Program.FAILURE
        nxt = self.transition.get(cur, cur)
        p_fail = self.failure_prob.get(cur, 0.0)
        return Program.FAILURE if (self.rng.random() < p_fail) else nxt

    def _elevator_load_and_get_time(self, rocket: Rocket, arrival_time: float) -> float:
        q = rocket.cargo_capacity
        queue = self.elevator_queues[rocket.assigned_elevator]
        t_load = queue.get_available_loading_time(arrival_time, q)

        wait = t_load - arrival_time
        if wait > 0:
            self.stats['elevator_waiting_time'].append(wait)

        rocket.cargo_onboard = q
        return t_load

    def update_rocket_state(self, rocket: Rocket):
        cur = rocket.current_program
        if cur == Program.FAILURE:
            rocket.completion_time = np.inf
            return

        if cur == Program.PROGRAM_3:
            delivered = rocket.cargo_onboard
            if delivered > 0:
                rocket.total_cargo += delivered
                self.stats['total_deliveries'] += 1
            rocket.cargo_onboard = 0.0

        self._add_cost(
            rocket,
            fuel_delta=self.program_fuel_cost[cur],
            env_lambda=self.program_env_lambda.get(cur, 0.0)
        )

        if cur == Program.PROGRAM_3:
            eid = rocket.assigned_elevator
            elevator_fuel = rocket.cargo_capacity * self.space_elevators[eid]['unit_fuel_cost']
            self._add_cost(
                rocket,
                fuel_delta=elevator_fuel,
                env_lambda=self.elevator_env_lambda
            )

        entering = self._next_program(cur)
        if entering == Program.FAILURE:
            rocket.current_program = Program.FAILURE
            rocket.completion_time = np.inf
            self.stats['total_failures'] += 1
            return

        base_t = rocket.completion_time
        finish_t = base_t + self.program_time[entering]
        rocket.current_program = entering
        rocket.completion_time = finish_t

        if entering in self.programs_need_elevator_loading:
            arrival = finish_t
            load_time = self._elevator_load_and_get_time(rocket, arrival)

            after_load = self._next_program(entering)
            if after_load == Program.FAILURE:
                rocket.current_program = Program.FAILURE
                rocket.completion_time = np.inf
                self.stats['total_failures'] += 1
                return

            rocket.current_program = after_load
            rocket.completion_time = load_time + self.program_time[after_load]

    def record_state(self):
        self.history['time'].append(self.current_time)
        self.history['total_cargo'].append(self.get_total_cargo())
        self.history['total_fuel_cost'].append(self.get_total_fuel_cost())
        self.history['total_env_cost'].append(self.get_total_env_cost())

        active = sum(1 for r in self.rockets if np.isfinite(r.completion_time) and r.current_program != Program.FAILURE)
        failed = sum(1 for r in self.rockets if r.current_program == Program.FAILURE)

        self.history['active_rockets'].append(active)
        self.history['failed_rockets'].append(failed)
        self.history['completed_deliveries'].append(self.stats['total_deliveries'])
        self.history['total_rockets'].append(len(self.rockets))

        for eid, q in self.elevator_queues.items():
            day = int(np.floor(self.current_time))
            self.history['elevator_daily_loading'][eid].append(q.daily_loading.get(day, 0.0))

    def run(self, verbose: bool = True, record_interval: int = 2000, print_every: Optional[int] = None):
        """
        record_interval: 每隔多少“事件处理次数”记录一次 history
        print_every:     每隔多少“事件处理次数”打印一次
        """
        if not self.space_elevators:
            raise RuntimeError("请先 add_space_elevator() 添加银河港。")
        if not self.assembly_lines:
            raise RuntimeError("请先 add_elevator_assembly() 为银河港配置组装速率。")

        if print_every is None:
            print_every = record_interval * 5

        t_wall0 = time.perf_counter()

        if verbose:
            print("\n" + _hline())
            print("情景1仿真开始（heapq 事件堆）")
            print(_sline())
            print(f"需求 M*: {self.total_demand:.3e} 吨 | 单箭运力: {self.rocket_capacity:.1f} 吨")
            rates = ", ".join([f"{eid}:{_fmt_float(line.rate, 3)}" for eid, line in self.assembly_lines.items()])
            caps = ", ".join([f"{eid}:{_fmt_float(info['loading_capacity'], 1)}" for eid, info in self.space_elevators.items()])
            print(f"银河港组装速率(枚/天): {rates}")
            print(f"银河港装货能力(吨/天):   {caps}")
            print(_sline())
            print("进度输出列说明：iter | t(day) | progress | deliveries | failures | rockets | avg_wait | fuel | env")
            print(_sline())

        heap: List[Tuple[float, int, str, Any]] = []
        for eid, t_ready in self.next_assembly_ready.items():
            self._push_event(heap, t_ready, 'assembly', eid)

        iteration = 0
        termination_reason = "unknown"

        while True:
            if self.get_total_cargo() >= self.total_demand:
                termination_reason = "demand_met"
                break

            if not heap:
                termination_reason = "stalled"
                if verbose:
                    print("[WARN] 事件堆为空，无可推进事件，终止。")
                break

            t = heap[0][0]
            self.current_time = t

            while heap and abs(heap[0][0] - t) < 1e-12:
                _, _, etype, payload = heapq.heappop(heap)

                if etype == 'assembly':
                    eid = int(payload)
                    if not np.isfinite(self.next_assembly_ready.get(eid, np.inf)):
                        continue
                    if abs(self.next_assembly_ready[eid] - t) > 1e-12:
                        continue

                    rocket = self._create_rocket_from_elevator_ready(eid, ready_time=t)
                    self._push_event(heap, rocket.completion_time, 'rocket', rocket.rocket_id)

                    self.next_assembly_ready[eid] = self.assembly_lines[eid].schedule_next_ready()
                    self._push_event(heap, self.next_assembly_ready[eid], 'assembly', eid)

                elif etype == 'rocket':
                    rid = int(payload)
                    if rid < 0 or rid >= len(self.rockets):
                        continue
                    rocket = self.rockets[rid]

                    if not np.isfinite(rocket.completion_time):
                        continue
                    if abs(rocket.completion_time - t) > 1e-12:
                        continue

                    self.update_rocket_state(rocket)

                    if np.isfinite(rocket.completion_time) and rocket.current_program != Program.FAILURE:
                        self._push_event(heap, rocket.completion_time, 'rocket', rocket.rocket_id)

                else:
                    raise RuntimeError(f"未知事件类型: {etype}")

                iteration += 1

                if iteration % record_interval == 0:
                    self.record_state()

                if verbose and (iteration % print_every == 0):
                    cargo = self.get_total_cargo()
                    progress = cargo / self.total_demand * 100.0

                    waits = self.stats['elevator_waiting_time']
                    avg_wait = float(np.mean(waits)) if waits else 0.0

                    fuel = self.get_total_fuel_cost()
                    env = self.get_total_env_cost()

                    t_wall = time.perf_counter() - t_wall0

                    # 一行关键指标：更短、更好扫
                    print(
                        f"{iteration:>10d} | "
                        f"{self.current_time:>9.2f} | "
                        f"{progress:>8.2f}% | "
                        f"{self.stats['total_deliveries']:>10d} | "
                        f"{self.stats['total_failures']:>8d} | "
                        f"{len(self.rockets):>7d} | "
                        f"{avg_wait:>8.3f} | "
                        f"{fuel:>9.2e} | "
                        f"{env:>9.2e} | "
                        f"{t_wall:>7.1f}s"
                    )

                if iteration > 2_000_000_000:
                    termination_reason = "iteration_limit"
                    if verbose:
                        print("[WARN] 事件次数过多，终止仿真!")
                    break

            if termination_reason == "iteration_limit":
                break

        self.record_state()

        final_cargo = self.get_total_cargo()
        final_cost = self.get_total_fuel_cost()
        final_env = self.get_total_env_cost()

        waits = self.stats['elevator_waiting_time']
        avg_wait = float(np.mean(waits)) if waits else 0.0
        max_wait = float(np.max(waits)) if waits else 0.0

        if verbose:
            t_wall = time.perf_counter() - t_wall0
            print(_sline())
            print("仿真结束")
            print(_sline())
            print(f"结束原因: {termination_reason}")
            print(f"完成时间 T*: {self.current_time:.2f} 天 | 壁钟耗时: {t_wall:.1f}s")
            print(f"累计送达 M(T*): {final_cargo:.3e} 吨 (目标 {self.total_demand:.3e})")
            print(f"总燃料成本: {final_cost:.3e} | 总环境外部成本: {final_env:.3e}")
            print(f"交付次数: {self.stats['total_deliveries']} | 失效次数: {self.stats['total_failures']} | 火箭总数: {len(self.rockets)}")
            if self.stats['total_deliveries'] > 0:
                print(f"平均单次燃料成本: {final_cost / self.stats['total_deliveries']:.2f}")
                print(f"平均单次环境外部成本: {final_env / self.stats['total_deliveries']:.2f}")
            print(f"银河港平均等待: {avg_wait:.6f} 天 | 最大等待: {max_wait:.6f} 天 | 等待事件数: {len(waits)}")
            print(_hline() + "\n")

        return {
            'completion_time': self.current_time,
            'delivered_cargo': final_cargo,
            'total_fuel_cost': final_cost,
            'total_env_cost': final_env,
            'total_deliveries': self.stats['total_deliveries'],
            'total_failures': self.stats['total_failures'],
            'avg_elevator_wait': avg_wait,
            'max_elevator_wait': max_wait,
            'termination_reason': termination_reason,
            'final_rockets': len(self.rockets),
            'history': self.history,
        }


def setup_scenario_1_elevator_only(
    total_demand: float = 1e6,
    seed: Optional[int] = 2026,
    rocket_capacity: float = 100.0,
    elevator_loading_capacity: float = 1000.0,
    assembly_rate_per_day_each_elevator: float = 0.05,
):
    sim = LunarTransportSimulationScenario1(
        total_demand=total_demand,
        t0=0.0,
        seed=seed,
        rocket_capacity=rocket_capacity
    )

    for eid in [1, 2, 3]:
        sim.add_space_elevator(eid, loading_capacity=elevator_loading_capacity, unit_fuel_cost=0.5)
        sim.add_elevator_assembly(eid, assembly_rate_per_day=assembly_rate_per_day_each_elevator)

    return sim


# =========================
#  2) 工具：Pareto / 约束
# =========================

def dominates(a: np.ndarray, b: np.ndarray) -> bool:
    return np.all(a <= b) and np.any(a < b)

def pareto_front_indices(objs: np.ndarray) -> np.ndarray:
    n = objs.shape[0]
    is_nd = np.ones(n, dtype=bool)
    for i in range(n):
        if not is_nd[i]:
            continue
        for j in range(n):
            if i == j or not is_nd[j]:
                continue
            if dominates(objs[j], objs[i]):
                is_nd[i] = False
                break
    return np.where(is_nd)[0]

def crowding_distance(objs: np.ndarray) -> np.ndarray:
    k, m = objs.shape
    if k == 0:
        return np.array([])
    if k <= 2:
        return np.full(k, np.inf)

    dist = np.zeros(k, dtype=float)
    for d in range(m):
        order = np.argsort(objs[:, d])
        dist[order[0]] = np.inf
        dist[order[-1]] = np.inf
        vmin = objs[order[0], d]
        vmax = objs[order[-1], d]
        if np.isclose(vmax, vmin):
            continue
        for i in range(1, k - 1):
            prev_v = objs[order[i - 1], d]
            next_v = objs[order[i + 1], d]
            dist[order[i]] += (next_v - prev_v) / (vmax - vmin)
    return dist

def choose_knee_point(objs: np.ndarray) -> int:
    eps = 1e-12
    mn = objs.min(axis=0)
    mx = objs.max(axis=0)
    norm = (objs - mn) / (mx - mn + eps)
    dist = np.linalg.norm(norm, axis=1)
    return int(np.argmin(dist))


# =========================
#  3) 评估器：多次仿真 + 统计
# =========================

@dataclass
class EvalConfig:
    total_demand: float = 1e6
    rocket_capacity: float = 150.0
    elevator_loading_capacity: float = 179000 / 365 * 3
    replications: int = 12
    base_seed: int = 2026
    wait_tol: float = 1e-12
    strict_wait: bool = True
    require_demand_met: bool = True


@dataclass
class EvalResult:
    rate: float
    feasible: bool
    violation: float
    mean_time: float
    mean_fuel: float
    mean_env: float
    mean_avg_wait: float
    mean_max_wait: float
    mean_wait_events: float
    bad_runs: int


class Scenario1Evaluator:
    def __init__(self, cfg: EvalConfig):
        self.cfg = cfg
        self.seeds = [cfg.base_seed + i for i in range(cfg.replications)]
        self.total_run_calls = 0     # 统计 sim.run() 调用次数
        self.total_good_runs = 0
        self.total_bad_runs = 0

    def _check_feasible(self, avg_wait: float, max_wait: float, wait_events: int) -> Tuple[bool, float]:
        tol = self.cfg.wait_tol
        if self.cfg.strict_wait:
            feasible = (avg_wait <= tol) and (max_wait <= tol) and (wait_events == 0)
            violation = max(avg_wait - tol, 0.0) + max(max_wait - tol, 0.0) + (1.0 if wait_events > 0 else 0.0)
        else:
            feasible = (avg_wait <= tol)
            violation = max(avg_wait - tol, 0.0)
        return feasible, float(violation)

    def evaluate(self, rate: float, verbose: bool = False) -> EvalResult:
        rate = float(rate)
        times, fuels, envs = [], [], []
        avg_waits, max_waits, wait_events = [], [], []
        bad_runs = 0

        for s in self.seeds:
            sim = setup_scenario_1_elevator_only(
                total_demand=self.cfg.total_demand,
                seed=s,
                rocket_capacity=self.cfg.rocket_capacity,
                elevator_loading_capacity=self.cfg.elevator_loading_capacity,
                assembly_rate_per_day_each_elevator=rate,
            )

            self.total_run_calls += 1
            try:
                out = sim.run(verbose=False, record_interval=5_000_000, print_every=5_000_000)
            except Exception:
                bad_runs += 1
                continue

            if self.cfg.require_demand_met and out.get("termination_reason") != "demand_met":
                bad_runs += 1
                continue

            times.append(out["completion_time"])
            fuels.append(out["total_fuel_cost"])
            envs.append(out["total_env_cost"])
            avg_waits.append(out["avg_elevator_wait"])
            max_waits.append(out["max_elevator_wait"])
            we = len(sim.stats["elevator_waiting_time"]) if hasattr(sim, "stats") else 0
            wait_events.append(we)

        good = len(times)
        self.total_good_runs += good
        self.total_bad_runs += bad_runs

        if good == 0:
            res = EvalResult(
                rate=rate,
                feasible=False,
                violation=1e30,
                mean_time=1e30,
                mean_fuel=1e30,
                mean_env=1e30,
                mean_avg_wait=1e30,
                mean_max_wait=1e30,
                mean_wait_events=1e30,
                bad_runs=bad_runs
            )
            if verbose:
                print(f"[EVAL] rate={rate:.3f} | ALL BAD (bad_runs={bad_runs}/{self.cfg.replications})")
            return res

        mean_time = float(np.mean(times))
        mean_fuel = float(np.mean(fuels))
        mean_env = float(np.mean(envs))
        mean_avg_wait = float(np.mean(avg_waits))
        mean_max_wait = float(np.mean(max_waits))
        mean_wait_events = float(np.mean(wait_events))

        feasible, violation = self._check_feasible(mean_avg_wait, mean_max_wait, int(round(mean_wait_events)))

        if verbose:
            tag = "OK" if feasible else "VIOL"
            print(
                f"[EVAL] rate={rate:.3f} | {tag} | "
                f"T={mean_time:.2f} | fuel={_fmt_sci(mean_fuel, 3)} | env={_fmt_sci(mean_env, 3)} | "
                f"wait(avg/max/events)={mean_avg_wait:.3e}/{mean_max_wait:.3e}/{mean_wait_events:.2f} | "
                f"bad={bad_runs}/{self.cfg.replications}"
            )

        return EvalResult(
            rate=rate,
            feasible=feasible,
            violation=violation,
            mean_time=mean_time,
            mean_fuel=mean_fuel,
            mean_env=mean_env,
            mean_avg_wait=mean_avg_wait,
            mean_max_wait=mean_max_wait,
            mean_wait_events=mean_wait_events,
            bad_runs=bad_runs
        )


# =========================
#  4) 优化器：全局采样 + Pareto + 局部加密
# =========================

@dataclass
class OptConfig:
    rate_min: float = 0.05
    rate_max: float = 1.0
    n_initial: int = 8
    refine_rounds: int = 0
    refine_per_round: int = 0
    refine_sigma_frac: float = 0.12
    dedup_eps: float = 5e-4
    auto_relax_wait_if_no_feasible: bool = True


class Scenario1MultiObjectiveOptimizer:
    def __init__(self, evaluator: Scenario1Evaluator, cfg: OptConfig):
        self.ev = evaluator
        self.cfg = cfg
        self._cache: Dict[float, EvalResult] = {}

    def _clip_rate(self, r: float) -> float:
        return float(np.clip(r, self.cfg.rate_min, self.cfg.rate_max))

    def _dedup_rate(self, r: float) -> Optional[float]:
        for k in self._cache.keys():
            if abs(k - r) <= self.cfg.dedup_eps:
                return None
        return r

    def _evaluate_rate(self, r: float, verbose: bool = False) -> EvalResult:
        r = self._clip_rate(r)
        for k, v in self._cache.items():
            if abs(k - r) <= self.cfg.dedup_eps:
                return v
        res = self.ev.evaluate(r, verbose=verbose)
        self._cache[r] = res
        return res

    def _collect_arrays(self):
        items = list(self._cache.values())
        rates = np.array([x.rate for x in items], dtype=float)
        objs = np.array([[x.mean_time, x.mean_fuel, x.mean_env] for x in items], dtype=float)
        feas = np.array([x.feasible for x in items], dtype=bool)
        viol = np.array([x.violation for x in items], dtype=float)
        return rates, objs, feas, viol, items

    def _get_feasible_pareto(self) -> List[EvalResult]:
        _, objs, feas, _, items = self._collect_arrays()
        feas_idx = np.where(feas)[0]
        if len(feas_idx) == 0:
            return []
        feas_objs = objs[feas_idx]
        nd_local = pareto_front_indices(feas_objs)
        nd_idx = feas_idx[nd_local]
        return [items[i] for i in nd_idx]

    def _get_best_infeasible(self) -> Optional[EvalResult]:
        items = list(self._cache.values())
        if len(items) == 0:
            return None
        return sorted(items, key=lambda x: (x.violation, x.mean_time, x.mean_fuel, x.mean_env))[0]

    def optimize(self, verbose: bool = True) -> Dict[str, Any]:
        t0 = time.perf_counter()

        if verbose:
            print("\n" + _hline())
            print("仿真优化开始（情景1）")
            print(_sline())
            print(f"rate 范围: [{self.cfg.rate_min}, {self.cfg.rate_max}] | 初始采样点数: {self.cfg.n_initial}")
            print(f"replications: {self.ev.cfg.replications} | strict_wait: {self.ev.cfg.strict_wait}")
            print(_hline())

        # Stage-1
        if verbose:
            print("\n[OPT] Stage-1 Global sampling")
            print(_sline())

        init_rates = np.linspace(self.cfg.rate_min, self.cfg.rate_max, self.cfg.n_initial)
        for r in init_rates:
            rr = self._dedup_rate(float(r))
            if rr is not None:
                # 你如果希望每个点都打印，把 verbose=True
                self._evaluate_rate(rr, verbose=False)

        feasible_pareto = self._get_feasible_pareto()
        if (len(feasible_pareto) == 0) and self.cfg.auto_relax_wait_if_no_feasible and self.ev.cfg.strict_wait:
            if verbose:
                print("[OPT] No feasible under strict_wait -> relax to avg_wait==0 only and re-evaluate.")
            self.ev.cfg.strict_wait = False
            old_cache = list(self._cache.keys())
            self._cache.clear()
            for r in old_cache:
                self._evaluate_rate(r, verbose=False)

        # Stage-2
        if verbose:
            print("\n[OPT] Stage-2 Local refinement")
            print(_sline())
            if self.cfg.refine_rounds <= 0 or self.cfg.refine_per_round <= 0:
                print("跳过（refine_rounds==0 或 refine_per_round==0）")

        span = self.cfg.rate_max - self.cfg.rate_min
        sigma = self.cfg.refine_sigma_frac * span

        for k in range(self.cfg.refine_rounds):
            feasible_pareto = self._get_feasible_pareto()
            if len(feasible_pareto) == 0:
                center = self._get_best_infeasible()
                if center is None:
                    break
                c = center.rate
                if verbose:
                    print(f"[OPT] Round {k+1}: no feasible, explore around best infeasible rate={c:.3f}, viol={center.violation:.3e}")
                cand = c + np.random.default_rng(1234 + k).normal(0.0, sigma, size=self.cfg.refine_per_round)
            else:
                po = np.array([[x.mean_time, x.mean_fuel, x.mean_env] for x in feasible_pareto], dtype=float)
                cd = crowding_distance(po)
                centers = np.argsort(-cd)[: min(3, len(feasible_pareto))]
                centers_rates = [feasible_pareto[i].rate for i in centers]
                if verbose:
                    print(f"[OPT] Round {k+1}: centers = {[f'{x:.3f}' for x in centers_rates]}")
                rng = np.random.default_rng(2026 + k)
                cand = []
                for _ in range(self.cfg.refine_per_round):
                    c = rng.choice(centers_rates)
                    cand.append(c + rng.normal(0.0, sigma))
                cand = np.array(cand, dtype=float)

            for r in cand:
                rr = self._dedup_rate(self._clip_rate(float(r)))
                if rr is not None:
                    self._evaluate_rate(rr, verbose=False)

            sigma *= 0.6

        # 汇总
        items = list(self._cache.values())
        feasible = [x for x in items if x.feasible]
        infeasible = [x for x in items if not x.feasible]
        feasible_pareto = self._get_feasible_pareto()
        feasible_pareto_sorted = sorted(feasible_pareto, key=lambda x: x.rate)

        recommended = None
        if len(feasible_pareto) > 0:
            objs = np.array([[x.mean_time, x.mean_fuel, x.mean_env] for x in feasible_pareto], dtype=float)
            idx = choose_knee_point(objs)
            recommended = feasible_pareto[idx]
        else:
            recommended = self._get_best_infeasible()

        # 打印总结
        if verbose:
            dt = time.perf_counter() - t0
            print("\n" + _hline())
            print("[OPT] Summary")
            print(_sline())
            print(f"评估点数: {len(items)} | 可行点: {len(feasible)} | 不可行点: {len(infeasible)} | 可行 Pareto: {len(feasible_pareto_sorted)}")
            print(f"耗时: {dt:.1f}s")
            print(_sline())

            if recommended is not None:
                tag = "OK" if recommended.feasible else "VIOL"
                print(f"推荐解 [{tag}]  rate={recommended.rate:.3f}")
                print(f"  T={recommended.mean_time:.2f} | fuel={_fmt_sci(recommended.mean_fuel,3)} | env={_fmt_sci(recommended.mean_env,3)}")
                print(f"  wait(avg/max/events)={recommended.mean_avg_wait:.3e}/{recommended.mean_max_wait:.3e}/{recommended.mean_wait_events:.2f}")
                print(f"  violation={recommended.violation:.3e} | bad_runs={recommended.bad_runs}/{self.ev.cfg.replications}")
                print(_sline())

            # Pareto 前几条（避免刷屏）
            if len(feasible_pareto_sorted) > 0:
                print("可行 Pareto（前 10 条，按 rate 排序）")
                print("  rate  |    T    |    fuel    |    env     | avg_wait | max_wait | wait_events")
                print(_sline())
                for x in feasible_pareto_sorted[:10]:
                    print(
                        f" {x.rate:>5.3f} | "
                        f"{x.mean_time:>7.2f} | "
                        f"{x.mean_fuel:>9.2e} | "
                        f"{x.mean_env:>9.2e} | "
                        f"{x.mean_avg_wait:>8.2e} | "
                        f"{x.mean_max_wait:>8.2e} | "
                        f"{x.mean_wait_events:>10.2f}"
                    )
                print(_sline())

            # 运行次数统计（更真实：包含 bad_runs）
            print("[RUN COUNT]")
            print(f"  sim.run() 调用总次数 : {self.ev.total_run_calls}")
            print(f"  成功 runs             : {self.ev.total_good_runs}")
            print(f"  bad runs              : {self.ev.total_bad_runs}")
            print(_hline() + "\n")

        return {
            "recommended": recommended,
            "feasible_pareto": feasible_pareto_sorted,
            "all_results": sorted(items, key=lambda x: x.rate),
        }


# =========================
#  5) 一键运行示例
# =========================

def run_optimizer_example():
    eval_cfg = EvalConfig(
        total_demand=5*1e6,
        rocket_capacity=150.0,
        elevator_loading_capacity=179000 / 365 * 3,
        replications=1,      # 你要快就设 1~3
        base_seed=2026,
        wait_tol=1e-12,
        strict_wait=True,
        require_demand_met=True,
    )

    opt_cfg = OptConfig(
        rate_min=0.05,
        rate_max=1.0,
        n_initial=12,        # 粗一些就 6~12
        refine_rounds=1,     # 粗搜：0
        refine_per_round=5,
        refine_sigma_frac=0.02,
        dedup_eps=5e-4,
        auto_relax_wait_if_no_feasible=True,
    )

    evaluator = Scenario1Evaluator(eval_cfg)
    optimizer = Scenario1MultiObjectiveOptimizer(evaluator, opt_cfg)
    return optimizer.optimize(verbose=True)


if __name__ == "__main__":
    # 只运行优化（避免你原来脚本里“先跑一次仿真又跑一次优化”的双 main）
    result = run_optimizer_example()
