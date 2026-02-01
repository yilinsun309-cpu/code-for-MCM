import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple, Any
from enum import Enum
import matplotlib.pyplot as plt
from collections import defaultdict
import heapq

# 设置中文字体支持
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


class Program(Enum):
    """情景3只需要：2/3/4 + 失效(吸收态)"""
    PROGRAM_2 = 2
    PROGRAM_3 = 3  # 卸货点：按 cargo_onboard 计入M（方案A）
    PROGRAM_4 = 4
    FAILURE = 6    # 失效状态（吸收态）


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
    cargo_onboard: float = 0.0  # 方案A：只有装货放行成功才>0

    # NEW: 累计环境外部成本（与燃料等价成本同单位）
    total_env_cost: float = 0.0

    def __repr__(self):
        return (f"Rocket(site={self.launch_site_id}, id={self.rocket_id}, "
                f"program={self.current_program.value}, t={self.completion_time:.2f}, "
                f"onboard={self.cargo_onboard:.1f})")


class SpaceElevatorLoadingQueue:
    """银河港装货队列管理器（每天装货能力约束）"""

    def __init__(self, elevator_id: int, loading_capacity: float):
        self.elevator_id = elevator_id
        self.loading_capacity = float(loading_capacity)
        self.daily_loading = defaultdict(float)  # day -> used_capacity

    def get_available_loading_time(self, arrival_time: float, cargo_amount: float) -> float:
        """
        Σ_{当日新增} q_{j,i_j} ≤ C̄^load_k
        找到最早可装货的日子，并在该日占用 cargo_amount
        """
        current_day = int(np.floor(arrival_time))
        search_day = current_day
        max_search_days = 100000  # 给大一点，避免极端情况

        for _ in range(max_search_days):
            used = self.daily_loading[search_day]
            remaining = self.loading_capacity - used

            if remaining >= cargo_amount:
                loading_start_time = max(arrival_time, float(search_day))
                self.daily_loading[search_day] += cargo_amount
                return loading_start_time

            search_day += 1

        print(f"警告: 银河港 {self.elevator_id} 装货队列搜索超时")
        return arrival_time


class LunarTransportSimulationScenario3:
    """
    情景3仿真器：
    - 状态: 2 -> 3 -> 4 -> 3 -> ...
    - 随机失效吸收态
    - 方案A：只有“装货放行成功”才会让 cargo_onboard = capacity；到 PROGRAM_3 时卸货计入M
    - 银河港每日装货能力约束（PROGRAM_4 到港后排队装货）
    - 年度扩编：每年每个发射场新增 annual_rocket_increase 枚火箭

    ✅ 事件堆版（heapq）：
    事件类型：
    - ('rocket', rocket_index)
    - ('expand', None)
    """

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
        self.current_time = float(self.t0)
        self.rng = np.random.default_rng(seed)

        self.annual_rocket_increase = int(annual_rocket_increase)
        self.max_years = max_years

        self.rockets: List[Rocket] = []
        self.space_elevators: Dict[int, dict] = {}
        self.elevator_queues: Dict[int, SpaceElevatorLoadingQueue] = {}
        self.launch_sites: Dict[int, dict] = {}

        # 各程序耗时（天）
        self.program_time: Dict[Program, float] = {
            Program.PROGRAM_2: 0.5,
            Program.PROGRAM_3: 3.0,
            Program.PROGRAM_4: 3.0,
        }

        # 各程序燃料成本（吨）
        self.program_fuel_cost: Dict[Program, float] = {
            Program.PROGRAM_2: 3000.0,
            Program.PROGRAM_3: 8.2,
            Program.PROGRAM_4: 2.353,
            Program.FAILURE: 0.0,
        }

        # NEW: 环境影响系数 λ（按你给的论文段落）
        # 程序二：地面发射进入地月转移轨道 -> λ2 = 3.0
        # 程序三：地月转移至月球并着陆 -> λ3 = 0.1
        # 程序四：月球起飞回收到顶端锚处 -> λ4 = 1.3
        # （情景3无程序五）
        self.program_env_lambda: Dict[Program, float] = {
            Program.PROGRAM_2: 3.0,
            Program.PROGRAM_3: 0.1,
            Program.PROGRAM_4: 1.3,
            Program.FAILURE: 0.0,
        }

        # NEW: 电梯装货（按货量计的那笔）对应论文程序一：λ1 = 0.4
        self.elevator_env_lambda: float = 0.4

        # 失效概率 p_{l6}
        self.failure_prob: Dict[Program, float] = {
            Program.PROGRAM_2: 0.02,
            Program.PROGRAM_3: 0.05,
            Program.PROGRAM_4: 0.03,
        }

        # 情景3确定性转移 φ：2->3, 3->4, 4->3
        self.transition_det = {
            Program.PROGRAM_2: Program.PROGRAM_3,
            Program.PROGRAM_3: Program.PROGRAM_4,
            Program.PROGRAM_4: Program.PROGRAM_3,
        }

        # 情景3：只有 PROGRAM_4 需要电梯装货放行
        self.programs_need_elevator_loading = {Program.PROGRAM_4}

        # 记录
        self.history = {
            'time': [],
            'total_cargo': [],
            'total_fuel_cost': [],
            'total_env_cost': [],  # NEW
            'active_rockets': [],
            'failed_rockets': [],
            'completed_deliveries': [],
            'elevator_daily_loading': defaultdict(list),
            'total_rockets': [],
        }

        self.stats = {
            'total_deliveries': 0,
            'total_failures': 0,
            'rockets_by_site': defaultdict(int),
            'elevator_waiting_time': [],
            'total_expansions': 0,
        }

        # 年度扩编事件
        self._next_expansion_time = self.t0 + 365.0
        self._expansion_count = 0

        # 事件堆序号（确保同一时刻稳定排序）
        self._event_seq = 0

    # ------------------- 配置 -------------------

    def add_space_elevator(self, elevator_id: int, loading_capacity: float,
                           unit_fuel_cost: float = 0.5):
        self.space_elevators[elevator_id] = {
            'loading_capacity': float(loading_capacity),
            'unit_fuel_cost': float(unit_fuel_cost)
        }
        self.elevator_queues[elevator_id] = SpaceElevatorLoadingQueue(
            elevator_id=elevator_id,
            loading_capacity=float(loading_capacity)
        )

    def add_launch_site(self, site_id: int, site_name: str,
                        launch_interval: float, initial_launch_time: float,
                        num_rockets_initial: int, rocket_capacity: float = 150.0):
        self.launch_sites[site_id] = {
            'name': site_name,
            'launch_interval': float(launch_interval),
            'initial_launch_time': float(initial_launch_time),
            'num_rockets_initial': int(num_rockets_initial),
            'rocket_capacity': float(rocket_capacity),
            'next_rocket_id': 0,
        }

    def get_launch_time_set(self, site_id: int, max_time: float = 100000.0) -> Set[float]:
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

    def get_next_launch_time(self, site_id: int, current_time: float,
                             launch_times: Optional[Set[float]] = None) -> float:
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

    # ------------------- NEW: 成本与环境影响累计 -------------------

    def _add_cost(self, rocket: Rocket, fuel_delta: float, env_lambda: float):
        """统一入口：燃料等价成本 + 环境外部成本 E = λ * f"""
        fuel_delta = float(fuel_delta)
        env_lambda = float(env_lambda)
        rocket.total_fuel_cost += fuel_delta
        rocket.total_env_cost += env_lambda * fuel_delta

    def get_total_env_cost(self) -> float:
        return sum(r.total_env_cost for r in self.rockets)

    # ------------------- 创建火箭 -------------------

    def _create_rocket(self, site_id: int, request_time: float) -> Rocket:
        site = self.launch_sites[site_id]
        rocket_id = site['next_rocket_id']
        site['next_rocket_id'] += 1

        initial_program = Program.PROGRAM_2

        # 发射窗口从 request_time 开始
        launch_times = self.get_launch_time_set(site_id)
        launch_time = self.get_next_launch_time(site_id, request_time, launch_times)
        completion_time = launch_time + self.program_time[initial_program]

        # 情景3：默认绑定第一个电梯（若存在）
        assigned_elevator = list(self.space_elevators.keys())[0] if self.space_elevators else None

        self.stats['rockets_by_site'][site_id] += 1

        rocket = Rocket(
            launch_site_id=site_id,
            rocket_id=rocket_id,
            current_program=initial_program,
            completion_time=completion_time,
            total_cargo=0.0,
            total_fuel_cost=0.0,  # 统一走 _add_cost，避免漏 env
            cargo_capacity=site['rocket_capacity'],
            assigned_elevator=assigned_elevator,
            cargo_onboard=0.0,
            total_env_cost=0.0
        )

        # 与你原逻辑一致：创建即视为进入 PROGRAM_2，因此先加一次 PROGRAM_2 成本（含 env）
        self._add_cost(
            rocket,
            fuel_delta=self.program_fuel_cost[initial_program],
            env_lambda=self.program_env_lambda.get(initial_program, 0.0)
        )

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

    # ------------------- 随机转移（含失效） -------------------

    def get_next_program_stochastic(self, current_program: Program) -> Program:
        if current_program == Program.FAILURE:
            return Program.FAILURE

        nxt_det = self.transition_det.get(current_program, current_program)
        p_fail = self.failure_prob.get(current_program, 0.0)
        return Program.FAILURE if (self.rng.random() < p_fail) else nxt_det

    # ------------------- 方案A：装货绑定交付 -------------------

    def ground_load_if_needed(self, rocket: Rocket, entering_program: Program):
        # 情景3：进入 PROGRAM_2 视为地面装满（但方案A里你实际是“只有放行成功才>0”）
        # 你原代码写的是进入2就装满，这里保持一致。
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

        # 装货放行成功
        rocket.cargo_onboard = q
        return t_load

    # ------------------- 状态更新 -------------------

    def update_rocket_state(self, rocket: Rocket):
        cur = rocket.current_program
        if cur == Program.FAILURE:
            rocket.completion_time = np.inf
            return

        # PROGRAM_3：卸货（按 cargo_onboard 计入M）
        if cur == Program.PROGRAM_3:
            delivered = rocket.cargo_onboard
            if delivered > 0:
                rocket.total_cargo += delivered
                self.stats['total_deliveries'] += 1
            rocket.cargo_onboard = 0.0

        # 成本累计（每次事件到达时加一次当前程序成本，保持你原写法）
        self._add_cost(
            rocket,
            fuel_delta=self.program_fuel_cost[cur],
            env_lambda=self.program_env_lambda.get(cur, 0.0)
        )

        # PROGRAM_3：如果有电梯，额外计入电梯单位成本（与你原代码一致）
        # 同时加入对应环境影响（论文程序一 λ1=0.4）
        if cur == Program.PROGRAM_3 and rocket.assigned_elevator is not None:
            elevator_id = rocket.assigned_elevator
            elevator_fuel = rocket.cargo_capacity * self.space_elevators[elevator_id]['unit_fuel_cost']
            self._add_cost(
                rocket,
                fuel_delta=elevator_fuel,
                env_lambda=self.elevator_env_lambda
            )

        # 随机转移（含失效）
        nxt = self.get_next_program_stochastic(cur)
        if nxt == Program.FAILURE:
            rocket.current_program = Program.FAILURE
            rocket.completion_time = np.inf
            self.stats['total_failures'] += 1
            return

        base_t = rocket.completion_time
        entering = nxt

        # 地面装载（进入2）
        self.ground_load_if_needed(rocket, entering)

        # 发射窗口：进入 PROGRAM_2 时需要卡窗口
        start_t = base_t
        if entering == Program.PROGRAM_2:
            launch_times = self.get_launch_time_set(rocket.launch_site_id)
            start_t = self.get_next_launch_time(rocket.launch_site_id, base_t, launch_times)

        finish_t = start_t + self.program_time[entering]
        rocket.current_program = entering
        rocket.completion_time = finish_t

        # 电梯装货放行：完成 PROGRAM_4 到港后排队装货，然后立刻再转移一次
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

    # ------------------- 统计/记录 -------------------

    def get_total_cargo(self) -> float:
        return sum(r.total_cargo for r in self.rockets)

    def get_total_fuel_cost(self) -> float:
        return sum(r.total_fuel_cost for r in self.rockets)

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

        for elevator_id, queue in self.elevator_queues.items():
            day = int(np.floor(self.current_time))
            self.history['elevator_daily_loading'][elevator_id].append(queue.daily_loading.get(day, 0.0))

    # ------------------- 事件堆工具 -------------------

    def _push_event(self, heap: List[Tuple[float, int, str, Any]], t: float, etype: str, payload: Any):
        if not np.isfinite(t):
            return
        self._event_seq += 1
        heapq.heappush(heap, (float(t), self._event_seq, etype, payload))

    # ------------------- 运行（事件堆版） -------------------

    def run(self, verbose: bool = True, record_interval: int = 1000, print_every: Optional[int] = None):
        print(f"\n{'=' * 70}")
        print("开始仿真: 情景 3（事件堆版 heapq + 环境影响）")
        print(f"总运输需求: {self.total_demand:.2e} 公吨")
        print(f"年度扩编: 每年每个发射场新增 {self.annual_rocket_increase} 枚火箭")
        if self.space_elevators:
            for elev_id, info in self.space_elevators.items():
                print(f"银河港 {elev_id} 装货能力: {info['loading_capacity']:.0f} 公吨/天 | λ_elev={self.elevator_env_lambda}")
        print("环境影响系数 λ：")
        for p, lam in self.program_env_lambda.items():
            print(f"  - {p.name}: {lam}")
        print(f"{'=' * 70}\n")

        if print_every is None:
            print_every = record_interval * 5

        self.initialize_rockets()

        print(f"初始火箭总数: {len(self.rockets)}")
        print(f"{'=' * 70}\n")

        heap: List[Tuple[float, int, str, Any]] = []

        # 年度扩编事件
        self._push_event(heap, self._next_expansion_time, 'expand', None)

        # 初始火箭事件
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
                print("警告: 事件堆为空，无可推进事件（通常全部失效/且不再扩编），终止仿真。")
                break

            # 最早事件时刻
            t = heap[0][0]
            self.current_time = t

            # 收集同一时刻事件
            events_at_t = []
            while heap and abs(heap[0][0] - t) < 1e-12:
                events_at_t.append(heapq.heappop(heap))

            # 处理同一时刻事件
            for _, _, etype, payload in events_at_t:
                if etype == 'expand':
                    # 过滤过期扩编事件
                    if abs(self._next_expansion_time - t) > 1e-9:
                        continue

                    old_len = len(self.rockets)
                    self.apply_annual_expansion(t)
                    new_len = len(self.rockets)

                    # 推入新火箭事件
                    for idx in range(old_len, new_len):
                        self._push_event(heap, self.rockets[idx].completion_time, 'rocket', idx)

                    # 推入下一次扩编事件
                    self._push_event(heap, self._next_expansion_time, 'expand', None)

                    iteration += 1

                elif etype == 'rocket':
                    idx = int(payload)
                    if idx < 0 or idx >= len(self.rockets):
                        continue
                    r = self.rockets[idx]

                    # 过滤过期火箭事件
                    if not np.isfinite(r.completion_time):
                        continue
                    if abs(r.completion_time - t) > 1e-9:
                        continue

                    self.update_rocket_state(r)

                    if np.isfinite(r.completion_time) and r.current_program != Program.FAILURE:
                        self._push_event(heap, r.completion_time, 'rocket', idx)

                    iteration += 1

                else:
                    raise RuntimeError(f"未知事件类型: {etype}")

                # 记录/打印（按事件处理次数）
                if iteration % record_interval == 0:
                    self.record_state()

                if verbose and (iteration % print_every == 0):
                    cargo = self.get_total_cargo()
                    progress = cargo / self.total_demand * 100.0
                    avg_wait = float(np.mean(self.stats['elevator_waiting_time'])) if self.stats['elevator_waiting_time'] else 0.0
                    active = sum(1 for rr in self.rockets if np.isfinite(rr.completion_time) and rr.current_program != Program.FAILURE)
                    failed = sum(1 for rr in self.rockets if rr.current_program == Program.FAILURE)
                    total_r = len(self.rockets)
                    env = self.get_total_env_cost()

                    print(f"迭代: {iteration:10d} | "
                          f"时间: {self.current_time:10.2f}天 | "
                          f"M: {cargo:.3e}公吨 | "
                          f"完成度: {progress:6.2f}% | "
                          f"交付: {self.stats['total_deliveries']:9d} | "
                          f"失效: {self.stats['total_failures']:9d} | "
                          f"在役: {active:7d} | "
                          f"失效在库: {failed:7d} | "
                          f"总火箭: {total_r:9d} | "
                          f"等待均值: {avg_wait:.2f}天 | "
                          f"扩编年数: {self._expansion_count:3d} | "
                          f"Env: {env:.3e}")

                if iteration > 2_000_000_000:
                    termination_reason = "iteration_limit"
                    print("警告: 事件次数过多, 终止仿真!")
                    break

            if termination_reason == "iteration_limit":
                break

        self.record_state()

        final_cargo = self.get_total_cargo()
        final_cost = self.get_total_fuel_cost()
        final_env = self.get_total_env_cost()
        avg_wait = float(np.mean(self.stats['elevator_waiting_time'])) if self.stats['elevator_waiting_time'] else 0.0
        max_wait = float(np.max(self.stats['elevator_waiting_time'])) if self.stats['elevator_waiting_time'] else 0.0

        print(f"\n{'=' * 70}")
        print("仿真完成!")
        print(f"{'=' * 70}")
        print(f"结束原因: {termination_reason}")
        print(f"完成时间 (T*): {self.current_time:.2f} 天")
        print(f"累计送达物资 M(T*): {final_cargo:.3e} 公吨")
        print(f"总燃料成本: {final_cost:.3e} 吨")
        print(f"总环境外部成本(等价燃料): {final_env:.3e}")
        print(f"总交付次数: {self.stats['total_deliveries']}")
        print(f"总失效次数: {self.stats['total_failures']}")
        print(f"累计扩编次数(年): {self._expansion_count}")
        print(f"最终火箭总数: {len(self.rockets)}")
        if self.stats['total_deliveries'] > 0:
            print(f"平均单次运输成本: {final_cost / self.stats['total_deliveries']:.2f} 吨燃料")
            print(f"平均单次环境外部成本: {final_env / self.stats['total_deliveries']:.2f}")
        if self.stats['elevator_waiting_time']:
            print(f"银河港平均等待时间: {avg_wait:.2f} 天")
            print(f"银河港最大等待时间: {max_wait:.2f} 天")
            print(f"发生等待的次数: {len(self.stats['elevator_waiting_time'])}")
        print(f"{'=' * 70}\n")

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
            'expansion_years': self._expansion_count,
            'history': self.history
        }


# ------------------ 情景3配置函数 ------------------

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

    # 情景3需要银河港
    sim.add_space_elevator(elevator_id=1, loading_capacity=elevator_capacity, unit_fuel_cost=0.5)

    # 发射场参数说明（按顺序）：
    # (
    #   site_id,                    # 发射场唯一编号
    #   site_name,                  # 发射场名称（仅用于标识/可读性）
    #   launch_interval,            # 发射周期 Δt（天）：相邻两次允许发射的最小时间间隔
    #   initial_launch_time,        # 首次可用发射时间 γ（天）：该发射场开始具备发射能力的时间
    #   num_rockets_per_site_initial,# 初始可用火箭数量（枚，t=0 时库存/在役）
    #   rocket_capacity             # 单枚火箭最大运载货物量（公吨，即单次交付量）
    # )

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


# ------------------ main 示例 ------------------

if __name__ == "__main__":
    print("\n" + "=" * 80)
    print(" 月球殖民地运输仿真系统（仅情景3：事件堆版 + 环境影响）")
    print("=" * 80)

    sim = setup_scenario_3(
        total_demand=1e6,
        num_rockets_per_site_initial=100,
        elevator_capacity=179000 / 365 * 3,
        seed=2026,
        annual_increase=10
    )

    # 建议：print_every 不要太大，否则会又感觉“卡”
    res = sim.run(verbose=True, record_interval=1000, print_every=2000)
    print("\n仿真完成!（情景3）")
