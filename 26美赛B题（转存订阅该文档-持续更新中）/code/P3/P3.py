import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Set, Optional
from enum import Enum
import matplotlib.pyplot as plt
from collections import defaultdict

# 设置中文字体支持
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


class Program(Enum):
    """程序枚举（扩展到含失效状态 6）"""
    PROGRAM_1 = 1
    PROGRAM_2 = 2
    PROGRAM_3 = 3  # 卸货点：计入M（方案A：按 cargo_onboard 计）
    PROGRAM_4 = 4
    PROGRAM_5 = 5
    FAILURE = 6    # 失效状态（吸收态）


class TransportScenario(Enum):
    """运输情景枚举"""
    SCENARIO_1 = 1
    SCENARIO_2 = 2
    SCENARIO_3 = 3


@dataclass
class Rocket:
    launch_site_id: int
    rocket_id: int
    current_program: Program
    completion_time: float
    total_cargo: float
    total_fuel_cost: float
    cargo_capacity: float
    scenario: TransportScenario
    assigned_elevator: Optional[int] = None
    cargo_onboard: float = 0.0  # 方案A：只有装货放行成功才>0

    def __repr__(self):
        return (f"Rocket(site={self.launch_site_id}, id={self.rocket_id}, "
                f"program={self.current_program.value}, t={self.completion_time:.2f}, "
                f"onboard={self.cargo_onboard:.1f})")


class SpaceElevatorLoadingQueue:
    """银河港装货队列管理器（每天装货能力约束）"""

    def __init__(self, elevator_id: int, loading_capacity: float):
        self.elevator_id = elevator_id
        self.loading_capacity = float(loading_capacity)
        self.daily_loading = defaultdict(float)

    def get_available_loading_time(self, arrival_time: float, cargo_amount: float) -> float:
        """
        考虑银河港每日装货能力约束：
        Σ_{当日新增} q_{j,i_j} ≤ C̄^load_k
        """
        current_day = int(np.floor(arrival_time))
        search_day = current_day
        max_search_days = 10000

        for _ in range(max_search_days):
            used_capacity = self.daily_loading[search_day]
            remaining_capacity = self.loading_capacity - used_capacity

            if remaining_capacity >= cargo_amount:
                loading_start_time = max(arrival_time, float(search_day))
                self.daily_loading[search_day] += cargo_amount
                return loading_start_time

            search_day += 1

        print(f"警告: 银河港 {self.elevator_id} 装货队列搜索超时")
        return arrival_time


class RocketAssemblyQueue:
    """
    火箭组装队列（仅用于情景1）——允许小数产能：
    用“组装速率 assembly_rate_per_day（枚/天）”建模。
    - 每枚火箭需要 assembly_time = 1 / assembly_rate_per_day 天
    - 单条组装线，顺序组装（FIFO 时间推进）
    例如：assembly_rate_per_day=0.5 => 每枚火箭耗时2天
    """

    def __init__(self, site_id: int, assembly_rate_per_day: float):
        self.site_id = site_id
        self.assembly_rate_per_day = float(assembly_rate_per_day)
        if self.assembly_rate_per_day <= 0:
            self.assembly_time = np.inf
        else:
            self.assembly_time = 1.0 / self.assembly_rate_per_day

        # 组装线的下一个空闲时刻
        self.next_free_time = 0.0

    def get_ready_time(self, request_time: float) -> float:
        """
        request_time：请求开始组装的时刻（比如年度扩编时刻）
        返回：该火箭组装完成时刻 ready_time
        """
        if not np.isfinite(self.assembly_time):
            return np.inf
        start = max(request_time, self.next_free_time)
        finish = start + self.assembly_time
        self.next_free_time = finish
        return finish


class LunarTransportSimulation:
    """随机失效 + 方案A（装货绑定交付）+ 年度扩编 + 情景1组装速率约束"""

    def __init__(self,
                 scenario: TransportScenario,
                 total_demand: float = 1e8,
                 t0: float = 0.0,
                 seed: Optional[int] = 2026,
                 annual_rocket_increase: int = 100,
                 max_years: Optional[int] = None,
                 assembly_rate_per_day_s1: Optional[float] = None  # ✅ 情景1：组装速率(枚/天，可为0.5)
                 ):
        self.scenario = scenario
        self.total_demand = float(total_demand)
        self.t0 = float(t0)
        self.current_time = self.t0
        self.rng = np.random.default_rng(seed)

        self.annual_rocket_increase = int(annual_rocket_increase)
        self.max_years = max_years

        # ✅ 情景1组装约束：速率（枚/天，可小数）
        self.assembly_rate_per_day_s1 = assembly_rate_per_day_s1
        self.assembly_queues: Dict[int, RocketAssemblyQueue] = {}

        self.rockets: List[Rocket] = []
        self.space_elevators: Dict[int, dict] = {}
        self.elevator_queues: Dict[int, SpaceElevatorLoadingQueue] = {}
        self.launch_sites: Dict[int, dict] = {}

        self.program_time: Dict[Program, float] = {
            Program.PROGRAM_1: 14.0,
            Program.PROGRAM_2: 0.5,
            Program.PROGRAM_3: 3.0,
            Program.PROGRAM_4: 3.0,
            Program.PROGRAM_5: 4.0,
        }

        self.program_fuel_cost: Dict[Program, float] = {
            Program.PROGRAM_1: 60.0,
            Program.PROGRAM_2: 3000.0,
            Program.PROGRAM_3: 8.2,
            Program.PROGRAM_4: 2.353,
            Program.PROGRAM_5: 16.9,
            Program.FAILURE: 0.0,
        }

        # p_{l6}
        self.failure_prob: Dict[Program, float] = {
            Program.PROGRAM_1: 0.10,
            Program.PROGRAM_2: 0.02,
            Program.PROGRAM_3: 0.05,
            Program.PROGRAM_4: 0.03,
            Program.PROGRAM_5: 0.04,
        }

        # φ_h
        self.transition_functions = {
            TransportScenario.SCENARIO_1: {
                Program.PROGRAM_1: Program.PROGRAM_3,
                Program.PROGRAM_3: Program.PROGRAM_4,
                Program.PROGRAM_4: Program.PROGRAM_3,
            },
            TransportScenario.SCENARIO_2: {
                Program.PROGRAM_2: Program.PROGRAM_3,
                Program.PROGRAM_3: Program.PROGRAM_4,
                Program.PROGRAM_4: Program.PROGRAM_5,
                Program.PROGRAM_5: Program.PROGRAM_2,
            },
            TransportScenario.SCENARIO_3: {
                Program.PROGRAM_2: Program.PROGRAM_3,
                Program.PROGRAM_3: Program.PROGRAM_4,
                Program.PROGRAM_4: Program.PROGRAM_3,
            }
        }

        self.programs_need_elevator_loading = {Program.PROGRAM_1, Program.PROGRAM_4}

        self.history = {
            'time': [],
            'total_cargo': [],
            'total_fuel_cost': [],
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

    # ------------------- 基础配置 -------------------

    def add_space_elevator(self, elevator_id: int, loading_capacity: float,
                          parallel_capacity: int = np.inf, unit_fuel_cost: float = 0.5):
        self.space_elevators[elevator_id] = {
            'loading_capacity': float(loading_capacity),
            'parallel_capacity': parallel_capacity,
            'unit_fuel_cost': float(unit_fuel_cost)
        }
        self.elevator_queues[elevator_id] = SpaceElevatorLoadingQueue(
            elevator_id=elevator_id,
            loading_capacity=float(loading_capacity)
        )

    def add_launch_site(self, site_id: int, site_name: str,
                        launch_interval: float, initial_launch_time: float,
                        num_rockets_initial: int, rocket_capacity: float = 100.0):
        self.launch_sites[site_id] = {
            'name': site_name,
            'launch_interval': float(launch_interval),
            'initial_launch_time': float(initial_launch_time),
            'num_rockets_initial': int(num_rockets_initial),
            'rocket_capacity': float(rocket_capacity),
            'next_rocket_id': 0,
        }

        # ✅ 情景1：建立组装队列（允许0.5）
        if self.scenario == TransportScenario.SCENARIO_1 and self.assembly_rate_per_day_s1 is not None:
            self.assembly_queues[site_id] = RocketAssemblyQueue(
                site_id=site_id,
                assembly_rate_per_day=float(self.assembly_rate_per_day_s1)
            )

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

    # ------------------- 创建火箭（受组装约束） -------------------

    def _get_assembly_ready_time(self, site_id: int, request_time: float) -> float:
        if self.scenario != TransportScenario.SCENARIO_1:
            return request_time
        if self.assembly_rate_per_day_s1 is None:
            return request_time
        q = self.assembly_queues.get(site_id)
        if q is None:
            return request_time
        return q.get_ready_time(request_time)

    def _create_rocket(self, site_id: int, request_time: float) -> Rocket:
        site = self.launch_sites[site_id]
        rocket_id = site['next_rocket_id']
        site['next_rocket_id'] += 1

        initial_program = Program.PROGRAM_1 if self.scenario == TransportScenario.SCENARIO_1 else Program.PROGRAM_2

        # ✅ 情景1：先组装
        ready_time = self._get_assembly_ready_time(site_id, request_time)
        if not np.isfinite(ready_time):
            # 无法组装：视为无法投入（用FAILURE+inf让它不参与事件推进）
            self.stats['total_failures'] += 1
            self.stats['rockets_by_site'][site_id] += 1
            return Rocket(
                launch_site_id=site_id,
                rocket_id=rocket_id,
                current_program=Program.FAILURE,
                completion_time=np.inf,
                total_cargo=0.0,
                total_fuel_cost=0.0,
                cargo_capacity=site['rocket_capacity'],
                scenario=self.scenario,
                assigned_elevator=None,
                cargo_onboard=0.0
            )

        # 发射窗口从 ready_time 开始
        launch_times = self.get_launch_time_set(site_id)
        launch_time = self.get_next_launch_time(site_id, ready_time, launch_times)
        completion_time = launch_time + self.program_time[initial_program]

        assigned_elevator = None
        if self.scenario in [TransportScenario.SCENARIO_1, TransportScenario.SCENARIO_3] and self.space_elevators:
            assigned_elevator = list(self.space_elevators.keys())[0]

        self.stats['rockets_by_site'][site_id] += 1
        return Rocket(
            launch_site_id=site_id,
            rocket_id=rocket_id,
            current_program=initial_program,
            completion_time=completion_time,
            total_cargo=0.0,
            total_fuel_cost=self.program_fuel_cost[initial_program],
            cargo_capacity=site['rocket_capacity'],
            scenario=self.scenario,
            assigned_elevator=assigned_elevator,
            cargo_onboard=0.0
        )

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
        phi = self.transition_functions[self.scenario]
        if current_program not in phi:
            return current_program
        next_det = phi[current_program]
        p_fail = self.failure_prob.get(current_program, 0.0)
        return Program.FAILURE if (self.rng.random() < p_fail) else next_det

    # ------------------- 方案A：装货绑定交付 -------------------

    def ground_load_if_needed(self, rocket: Rocket, entering_program: Program):
        # 情景2/3：进入PROGRAM_2视为地面装满
        if entering_program == Program.PROGRAM_2 and rocket.scenario in [TransportScenario.SCENARIO_2, TransportScenario.SCENARIO_3]:
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
        rocket.cargo_onboard = q  # 装货放行成功
        return t_load

    # ------------------- 状态更新 -------------------

    def update_rocket_state(self, rocket: Rocket):
        cur = rocket.current_program
        if cur == Program.FAILURE:
            rocket.completion_time = np.inf
            return

        # PROGRAM_3 卸货：按 cargo_onboard 计入M
        if cur == Program.PROGRAM_3:
            delivered = rocket.cargo_onboard
            if delivered > 0:
                rocket.total_cargo += delivered
                self.stats['total_deliveries'] += 1
            rocket.cargo_onboard = 0.0

        # 成本累计
        rocket.total_fuel_cost += self.program_fuel_cost[cur]
        if cur == Program.PROGRAM_3 and rocket.assigned_elevator is not None:
            elevator_id = rocket.assigned_elevator
            rocket.total_fuel_cost += rocket.cargo_capacity * self.space_elevators[elevator_id]['unit_fuel_cost']

        # 随机转移
        nxt = self.get_next_program_stochastic(cur)
        if nxt == Program.FAILURE:
            rocket.current_program = Program.FAILURE
            rocket.completion_time = np.inf
            self.stats['total_failures'] += 1
            return

        base_t = rocket.completion_time
        entering = nxt

        self.ground_load_if_needed(rocket, entering)

        # 发射窗口（进入1或2）
        start_t = base_t
        if entering in [Program.PROGRAM_1, Program.PROGRAM_2]:
            launch_times = self.get_launch_time_set(rocket.launch_site_id)
            start_t = self.get_next_launch_time(rocket.launch_site_id, base_t, launch_times)

        finish_t = start_t + self.program_time[entering]
        rocket.current_program = entering
        rocket.completion_time = finish_t

        # 电梯装货放行（完成PROGRAM_1/4到达银河港后排队装货，再随机转移一次）
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

        active = sum(1 for r in self.rockets if np.isfinite(r.completion_time) and r.current_program != Program.FAILURE)
        failed = sum(1 for r in self.rockets if r.current_program == Program.FAILURE)
        self.history['active_rockets'].append(active)
        self.history['failed_rockets'].append(failed)
        self.history['completed_deliveries'].append(self.stats['total_deliveries'])
        self.history['total_rockets'].append(len(self.rockets))

        for elevator_id, queue in self.elevator_queues.items():
            day = int(np.floor(self.current_time))
            self.history['elevator_daily_loading'][elevator_id].append(queue.daily_loading.get(day, 0.0))

    def run(self, verbose: bool = True, record_interval: int = 1000):
        print(f"\n{'=' * 70}")
        print(f"开始仿真: 情景 {self.scenario.value}")
        print(f"总运输需求: {self.total_demand:.2e} 公吨")
        print(f"年度扩编: 每年每个发射场新增 {self.annual_rocket_increase} 枚火箭")
        if self.scenario == TransportScenario.SCENARIO_1 and self.assembly_rate_per_day_s1 is not None:
            print(f"情景1组装约束: 组装速率 = {self.assembly_rate_per_day_s1} 枚/天 （例如0.5表示每2天1枚）")
        print(f"{'=' * 70}\n")

        self.initialize_rockets()

        print(f"初始火箭总数: {len(self.rockets)}")
        if self.space_elevators:
            for elev_id, info in self.space_elevators.items():
                print(f"银河港 {elev_id} 装货能力: {info['loading_capacity']:.0f} 公吨/天")
        print(f"{'=' * 70}\n")

        iteration = 0
        termination_reason = "unknown"

        while True:
            if self.get_total_cargo() >= self.total_demand:
                termination_reason = "demand_met"
                break

            finite_times = [r.completion_time for r in self.rockets if np.isfinite(r.completion_time)]
            next_rocket_event = min(finite_times) if finite_times else np.inf
            next_expand = self._next_expansion_time

            if np.isinf(next_rocket_event) and np.isinf(next_expand):
                termination_reason = "all_failed_or_stalled"
                print("警告: 没有任何可推进的事件（通常全部失效/且不再扩编），终止仿真。")
                break

            self.current_time = min(next_rocket_event, next_expand)

            if abs(self.current_time - next_expand) < 1e-9:
                self.apply_annual_expansion(self.current_time)

            for r in self.rockets:
                if np.isfinite(r.completion_time) and abs(r.completion_time - self.current_time) < 1e-9:
                    self.update_rocket_state(r)

            if iteration % record_interval == 0:
                self.record_state()
                if verbose and iteration % (record_interval * 5) == 0:
                    cargo = self.get_total_cargo()
                    progress = cargo / self.total_demand * 100.0
                    avg_wait = float(np.mean(self.stats['elevator_waiting_time'])) if self.stats['elevator_waiting_time'] else 0.0
                    active = self.history['active_rockets'][-1]
                    failed = self.history['failed_rockets'][-1]
                    total_r = self.history['total_rockets'][-1]
                    print(f"迭代: {iteration:8d} | "
                          f"时间: {self.current_time:10.2f}天 | "
                          f"M: {cargo:.3e}公吨 | "
                          f"完成度: {progress:6.2f}% | "
                          f"交付: {self.stats['total_deliveries']:7d} | "
                          f"失效: {self.stats['total_failures']:7d} | "
                          f"在役: {active:6d} | "
                          f"总火箭: {total_r:7d} | "
                          f"电梯等待: {avg_wait:.2f}天 | "
                          f"扩编年数: {self._expansion_count:3d}")

            iteration += 1
            if iteration > 1e8:
                termination_reason = "iteration_limit"
                print("警告: 迭代次数过多, 终止仿真!")
                break

        self.record_state()

        final_cargo = self.get_total_cargo()
        final_cost = self.get_total_fuel_cost()
        avg_wait = float(np.mean(self.stats['elevator_waiting_time'])) if self.stats['elevator_waiting_time'] else 0.0
        max_wait = float(np.max(self.stats['elevator_waiting_time'])) if self.stats['elevator_waiting_time'] else 0.0

        print(f"\n{'=' * 70}")
        print("仿真完成!")
        print(f"{'=' * 70}")
        print(f"结束原因: {termination_reason}")
        print(f"完成时间 (T*): {self.current_time:.2f} 天")
        print(f"累计送达物资 M(T*): {final_cargo:.3e} 公吨")
        print(f"总燃料成本: {final_cost:.3e} 吨")
        print(f"总交付次数: {self.stats['total_deliveries']}")
        print(f"总失效次数: {self.stats['total_failures']}")
        print(f"累计扩编次数(年): {self._expansion_count}")
        print(f"最终火箭总数: {len(self.rockets)}")
        if self.stats['total_deliveries'] > 0:
            print(f"平均单次运输成本: {final_cost / self.stats['total_deliveries']:.2f} 吨燃料")
        if self.stats['elevator_waiting_time']:
            print(f"银河港平均等待时间: {avg_wait:.2f} 天")
            print(f"银河港最大等待时间: {max_wait:.2f} 天")
            print(f"发生等待的次数: {len(self.stats['elevator_waiting_time'])}")
        print(f"{'=' * 70}\n")

        return {
            'completion_time': self.current_time,
            'delivered_cargo': final_cargo,
            'total_cargo': final_cargo,
            'total_fuel_cost': final_cost,
            'total_deliveries': self.stats['total_deliveries'],
            'total_failures': self.stats['total_failures'],
            'avg_elevator_wait': avg_wait,
            'max_elevator_wait': max_wait,
            'termination_reason': termination_reason,
            'final_rockets': len(self.rockets),
            'expansion_years': self._expansion_count,
            'history': self.history
        }

    def plot_results(self, save_path: Optional[str] = None):
        has_elevator = len(self.space_elevators) > 0
        num_plots = 6 if has_elevator else 5

        fig, axes = plt.subplots(num_plots, 1, figsize=(14, 4 * num_plots))
        times = np.array(self.history['time'])

        axes[0].plot(times, self.history['total_cargo'], linewidth=2, label='累计送达M')
        axes[0].axhline(y=self.total_demand, linestyle='--', linewidth=2,
                        label=f'目标需求 ({self.total_demand:.2e}公吨)')
        axes[0].set_xlabel('时间 (天)')
        axes[0].set_ylabel('累计送达物资 (公吨)')
        axes[0].set_title(f'情景 {self.scenario.value}: 累计送达物资 M(t)', fontweight='bold')
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)
        axes[0].ticklabel_format(style='scientific', axis='y', scilimits=(0, 0))

        axes[1].plot(times, self.history['total_fuel_cost'], linewidth=2)
        axes[1].set_xlabel('时间 (天)')
        axes[1].set_ylabel('累计燃料成本 (吨)')
        axes[1].set_title(f'情景 {self.scenario.value}: 累计燃料成本', fontweight='bold')
        axes[1].grid(True, alpha=0.3)
        axes[1].ticklabel_format(style='scientific', axis='y', scilimits=(0, 0))

        axes[2].plot(times, self.history['completed_deliveries'], linewidth=2)
        axes[2].set_xlabel('时间 (天)')
        axes[2].set_ylabel('累计交付次数')
        axes[2].set_title(f'情景 {self.scenario.value}: 累计交付次数', fontweight='bold')
        axes[2].grid(True, alpha=0.3)

        axes[3].plot(times, self.history['failed_rockets'], linewidth=2)
        axes[3].set_xlabel('时间 (天)')
        axes[3].set_ylabel('失效火箭数')
        axes[3].set_title(f'情景 {self.scenario.value}: 失效火箭数', fontweight='bold')
        axes[3].grid(True, alpha=0.3)

        axes[4].plot(times, self.history['total_rockets'], linewidth=2)
        axes[4].set_xlabel('时间 (天)')
        axes[4].set_ylabel('火箭总数')
        axes[4].set_title(f'情景 {self.scenario.value}: 火箭数量（含年度扩编）', fontweight='bold')
        axes[4].grid(True, alpha=0.3)

        if has_elevator:
            for elevator_id in self.elevator_queues.keys():
                loading_data = self.history['elevator_daily_loading'].get(elevator_id, [])
                if loading_data:
                    axes[5].plot(times[:len(loading_data)], loading_data, linewidth=2, label=f'银河港 {elevator_id}')
            for elevator_id, info in self.space_elevators.items():
                axes[5].axhline(y=info['loading_capacity'], linestyle='--', linewidth=2,
                                label=f'装货能力上限 ({info["loading_capacity"]:.0f}公吨/天)')
            axes[5].set_xlabel('时间 (天)')
            axes[5].set_ylabel('每日装货量 (公吨/天)')
            axes[5].set_title(f'情景 {self.scenario.value}: 银河港每日装货量', fontweight='bold')
            axes[5].legend()
            axes[5].grid(True, alpha=0.3)

        plt.tight_layout()
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"图表已保存至: {save_path}")
        plt.show()


# ------------------ 三种情景配置 ------------------

def setup_scenario_1(total_demand: float = 1e6,
                     num_rockets_per_site_initial: int = 10,
                     elevator_capacity: float = 1000.0,
                     seed: Optional[int] = 2026,
                     annual_increase: int = 100,
                     assembly_rate_per_day_s1: float = 0.5   # ✅ 你要的：0.5 枚/天
                     ) -> LunarTransportSimulation:
    sim = LunarTransportSimulation(
        scenario=TransportScenario.SCENARIO_1,
        total_demand=total_demand,
        t0=0.0,
        seed=seed,
        annual_rocket_increase=annual_increase,
        assembly_rate_per_day_s1=assembly_rate_per_day_s1
    )
    sim.add_space_elevator(1, elevator_capacity, np.inf, 0.5)

    launch_sites_data = [
        (1, "加利福尼亚", 5.53, 9, num_rockets_per_site_initial, 100),
        (2, "德克萨斯", 73, 15, num_rockets_per_site_initial, 100),
        (3, "佛罗里达", 3.35, 3, num_rockets_per_site_initial, 100),
        (4, "弗吉尼亚", 365, 351, num_rockets_per_site_initial, 100),
        (5, "哈萨克斯坦", 60.83, 57, num_rockets_per_site_initial, 100),
        (6, "法属圭亚那", 52.14, 64, num_rockets_per_site_initial, 100),
        (7, "印度", 73, 28, num_rockets_per_site_initial, 100),
        (8, "中国", 30.42, 22, num_rockets_per_site_initial, 100),
        (9, "新西兰", 21.47, 38, num_rockets_per_site_initial, 100),
    ]
    for site_data in launch_sites_data:
        sim.add_launch_site(*site_data)
    return sim


def setup_scenario_2(total_demand: float = 1e6,
                     num_rockets_per_site_initial: int = 10,
                     seed: Optional[int] = 2026,
                     annual_increase: int = 100) -> LunarTransportSimulation:
    sim = LunarTransportSimulation(
        scenario=TransportScenario.SCENARIO_2,
        total_demand=total_demand,
        t0=0.0,
        seed=seed,
        annual_rocket_increase=annual_increase,
        assembly_rate_per_day_s1=None
    )
    launch_sites_data = [
        (1, "加利福尼亚", 10.14, 9, num_rockets_per_site_initial, 100),
        (2, "德克萨斯", 73, 15, num_rockets_per_site_initial, 100),
        (3, "佛罗里达", 36.5, 3, num_rockets_per_site_initial, 100),
        (4, "弗吉尼亚", 365, 351, num_rockets_per_site_initial, 100),
        (5, "哈萨克斯坦", 60.83, 57, num_rockets_per_site_initial, 100),
        (6, "法属圭亚那", 52.14, 64, num_rockets_per_site_initial, 100),
        (7, "印度", 73, 28, num_rockets_per_site_initial, 100),
        (8, "中国", 30.42, 22, num_rockets_per_site_initial, 100),
        (9, "新西兰", 21.47, 38, num_rockets_per_site_initial, 100),
    ]
    for site_data in launch_sites_data:
        sim.add_launch_site(*site_data)
    return sim


def setup_scenario_3(total_demand: float = 1e6,
                     num_rockets_per_site_initial: int = 10,
                     elevator_capacity: float = 1000.0,
                     seed: Optional[int] = 2026,
                     annual_increase: int = 100) -> LunarTransportSimulation:
    sim = LunarTransportSimulation(
        scenario=TransportScenario.SCENARIO_3,
        total_demand=total_demand,
        t0=0.0,
        seed=seed,
        annual_rocket_increase=annual_increase,
        assembly_rate_per_day_s1=None
    )
    sim.add_space_elevator(1, elevator_capacity, np.inf, 0.5)

    launch_sites_data = [
        (1, "加利福尼亚", 5.53, 9, num_rockets_per_site_initial, 66),
        (2, "德克萨斯", 73, 15, num_rockets_per_site_initial, 5),
        (3, "佛罗里达", 3.35, 3, num_rockets_per_site_initial, 100),
        (4, "弗吉尼亚", 365, 351, num_rockets_per_site_initial, 1),
        (5, "哈萨克斯坦", 60.83, 57, num_rockets_per_site_initial, 6),
        (6, "法属圭亚那", 52.14, 64, num_rockets_per_site_initial, 7),
        (7, "印度", 73, 28, num_rockets_per_site_initial, 5),
        (8, "中国", 30.42, 22, num_rockets_per_site_initial, 12),
        (9, "新西兰", 21.47, 38, num_rockets_per_site_initial, 17),
    ]
    for site_data in launch_sites_data:
        sim.add_launch_site(*site_data)
    return sim


def compare_scenarios(total_demand: float = 1e6,
                      num_rockets_initial: int = 10,
                      elevator_capacity: float = 1000.0,
                      seed: Optional[int] = 2026,
                      annual_increase: int = 100,
                      assembly_rate_per_day_s1: float = 0.5):
    results = {}

    setups = [
        (TransportScenario.SCENARIO_1,
         lambda: setup_scenario_1(total_demand, num_rockets_initial, elevator_capacity, seed,
                                  annual_increase, assembly_rate_per_day_s1)),
        (TransportScenario.SCENARIO_2,
         lambda: setup_scenario_2(total_demand, num_rockets_initial, seed, annual_increase)),
        (TransportScenario.SCENARIO_3,
         lambda: setup_scenario_3(total_demand, num_rockets_initial, elevator_capacity, seed, annual_increase)),
    ]

    for sc, fn in setups:
        print(f"\n{'#' * 70}")
        print(f"# 运行情景 {sc.value}")
        print(f"{'#' * 70}")
        sim = fn()
        res = sim.run(verbose=True, record_interval=1000)
        results[sc] = res
        # sim.plot_results(save_path=f"scenario_{sc.value}_results.png")

    print("=" * 140)
    print(f"{'情景':<6} {'结束原因':<14} {'完成时间':<12} {'送达质量M(公吨)':<18} "
          f"{'燃料成本':<15} {'交付次数':<10} {'失效次数':<10} {'最终火箭数':<10} {'扩编年数':<10} {'电梯等待':<12}")
    print("-" * 140)

    def reason_cn(r: str) -> str:
        if r == "demand_met":
            return "送达完成"
        if r == "all_failed_or_stalled":
            return "全体失效/停滞"
        if r == "iteration_limit":
            return "迭代上限"
        return r

    for sc in [TransportScenario.SCENARIO_1, TransportScenario.SCENARIO_2, TransportScenario.SCENARIO_3]:
        r = results[sc]
        avg_wait = r.get('avg_elevator_wait', 0.0)
        print(f"{sc.value:<6} "
              f"{reason_cn(r.get('termination_reason', 'unknown')):<14} "
              f"{r['completion_time']:<12.2f} "
              f"{r['delivered_cargo']:<18.3e} "
              f"{r['total_fuel_cost']:<15.3e} "
              f"{r['total_deliveries']:<10} "
              f"{r['total_failures']:<10} "
              f"{r['final_rockets']:<10} "
              f"{r['expansion_years']:<10} "
              f"{avg_wait:<12.2f}")

    print("=" * 140)
    return results


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print(" 月球殖民地运输仿真系统")
    print("=" * 80)

    results = compare_scenarios(
        total_demand=1.1 * 1e5,
        num_rockets_initial=100,
        elevator_capacity=179000 / 365 * 3,
        seed=2025,
        annual_increase=50,
        assembly_rate_per_day_s1=0.05
    )

    print("\n仿真完成! 结果已保存。")
