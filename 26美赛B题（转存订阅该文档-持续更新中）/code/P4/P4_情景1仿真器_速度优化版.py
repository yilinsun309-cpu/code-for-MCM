import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import matplotlib.pyplot as plt
from collections import defaultdict
import heapq

# 设置中文字体支持
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


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

    # 累计环境外部成本（与燃料等价成本同单位）
    total_env_cost: float = 0.0


class SpaceElevatorLoadingQueue:
    """银河港装货队列（每日装货能力约束）"""

    def __init__(self, elevator_id: int, loading_capacity: float):
        self.elevator_id = elevator_id
        self.loading_capacity = float(loading_capacity)
        self.daily_loading = defaultdict(float)  # day -> used capacity

    def get_available_loading_time(self, arrival_time: float, cargo_amount: float) -> float:
        day = int(np.floor(arrival_time))
        for _ in range(100000):  # 拉高一点，避免极端情况下搜索不够
            used = self.daily_loading[day]
            if self.loading_capacity - used >= cargo_amount:
                start_time = max(arrival_time, float(day))
                self.daily_loading[day] += cargo_amount
                return start_time
            day += 1
        print(f"警告: 银河港 {self.elevator_id} 装货队列搜索超时")
        return arrival_time


class RocketAssemblyLine:
    """
    单条组装线：按 assembly_rate_per_day 匀速输出火箭（枚/天）
    assembly_time = 1 / rate
    next_free_time 表示下一次开始组装的时间（顺序组装）
    """

    def __init__(self, assembly_rate_per_day: float, t0: float = 0.0):
        self.rate = float(assembly_rate_per_day)
        self.assembly_time = np.inf if self.rate <= 0 else 1.0 / self.rate
        self.next_free_time = float(t0)

    def schedule_next_ready(self) -> float:
        """安排并返回下一枚火箭组装完成时间"""
        if not np.isfinite(self.assembly_time):
            return np.inf
        start = self.next_free_time
        finish = start + self.assembly_time
        self.next_free_time = finish
        return finish


class LunarTransportSimulationScenario1:
    """
    情景1（银河港顺序组装→直接地月运行，无发射场）：
    - 银河港 1/2/3 各自按速率顺序组装火箭（枚/天，可小数）
    - 组装完成后立刻开始 PROGRAM_1（不需要对齐发射窗口）
    - 装货绑定交付（PROGRAM_3 仅按 cargo_onboard 计入M）
    - 银河港每日装货能力约束（装货发生在完成 PROGRAM_1/4 之后）
    - 随机失效（吸收态 FAILURE）

    事件堆版：用 heapq 管理两类事件
    - ('assembly', elevator_id)
    - ('rocket', rocket_id)
    """

    def __init__(self, total_demand: float = 1e6, t0: float = 0.0, seed: Optional[int] = 2026,
                 rocket_capacity: float = 100.0):
        self.total_demand = float(total_demand)
        self.t0 = float(t0)
        self.current_time = float(t0)
        self.rng = np.random.default_rng(seed)

        self.rocket_capacity = float(rocket_capacity)

        # 银河港（电梯）配置：装货能力 + 单位货物燃料成本
        self.space_elevators: Dict[int, dict] = {}
        self.elevator_queues: Dict[int, SpaceElevatorLoadingQueue] = {}

        # 组装线按银河港
        self.assembly_lines: Dict[int, RocketAssemblyLine] = {}
        self.next_assembly_ready: Dict[int, float] = {}  # elevator_id -> next ready time

        self.rockets: List[Rocket] = []
        self._global_rocket_id = 0

        # 程序耗时 / 成本 / 失效概率（情景1）
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

        # 环境影响系数 λ（可按论文/建模需要自行调整）
        self.program_env_lambda = {
            Program.PROGRAM_1: 0.1,
            Program.PROGRAM_3: 0.1,
            Program.PROGRAM_4: 1.3,
            Program.FAILURE: 0.0,
        }
        # 电梯装货（按货量计的那笔）对应论文程序一：λ1 = 0.4
        self.elevator_env_lambda = 0.4

        self.failure_prob = {
            Program.PROGRAM_1: 0.10,
            Program.PROGRAM_3: 0.05,
            Program.PROGRAM_4: 0.03,
        }

        # 确定性转移：1->3->4->3...
        self.transition = {
            Program.PROGRAM_1: Program.PROGRAM_3,
            Program.PROGRAM_3: Program.PROGRAM_4,
            Program.PROGRAM_4: Program.PROGRAM_3,
        }

        # 完成 PROGRAM_1/4 后到银河港：排队装货放行
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
            'elevator_daily_loading': defaultdict(list),  # eid -> list
        }

        # 事件堆需要的序号（保证同一时刻事件稳定排序）
        self._event_seq = 0

    # ------------------- 成本与环境影响累计 -------------------

    def _add_cost(self, rocket: Rocket, fuel_delta: float, env_lambda: float):
        """统一入口：燃料等价成本 + 环境外部成本 E = λ * f"""
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

    # ------------------- 配置 -------------------

    def add_space_elevator(self, elevator_id: int, loading_capacity: float, unit_fuel_cost: float = 0.5):
        self.space_elevators[elevator_id] = {
            'loading_capacity': float(loading_capacity),
            'unit_fuel_cost': float(unit_fuel_cost),
        }
        self.elevator_queues[elevator_id] = SpaceElevatorLoadingQueue(elevator_id, loading_capacity)

    def add_elevator_assembly(self, elevator_id: int, assembly_rate_per_day: float):
        """每个银河港每天可组装 assembly_rate_per_day 枚火箭（例如0.05）"""
        line = RocketAssemblyLine(assembly_rate_per_day=assembly_rate_per_day, t0=self.t0)
        self.assembly_lines[elevator_id] = line
        self.next_assembly_ready[elevator_id] = line.schedule_next_ready()

    # ------------------- 事件堆：push -------------------

    def _push_event(self, heap: List[Tuple[float, int, str, Any]], t: float, etype: str, payload: Any):
        if not np.isfinite(t):
            return
        self._event_seq += 1
        heapq.heappush(heap, (float(t), self._event_seq, etype, payload))

    # ------------------- 组装事件：银河港生成新火箭 -------------------

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

        # 初始进入 PROGRAM_1 的成本与环境影响（避免漏统计）
        self._add_cost(
            rocket,
            fuel_delta=self.program_fuel_cost[Program.PROGRAM_1],
            env_lambda=self.program_env_lambda.get(Program.PROGRAM_1, 0.0)
        )

        self.rockets.append(rocket)
        return rocket

    # ------------------- 随机转移 -------------------

    def _next_program(self, cur: Program) -> Program:
        if cur == Program.FAILURE:
            return Program.FAILURE
        nxt = self.transition.get(cur, cur)
        p_fail = self.failure_prob.get(cur, 0.0)
        return Program.FAILURE if (self.rng.random() < p_fail) else nxt

    # ------------------- 银河港装货（装货绑定交付） -------------------

    def _elevator_load_and_get_time(self, rocket: Rocket, arrival_time: float) -> float:
        q = rocket.cargo_capacity
        queue = self.elevator_queues[rocket.assigned_elevator]
        t_load = queue.get_available_loading_time(arrival_time, q)

        wait = t_load - arrival_time
        if wait > 0:
            self.stats['elevator_waiting_time'].append(wait)

        rocket.cargo_onboard = q
        return t_load

    # ------------------- 火箭事件：状态推进 -------------------

    def update_rocket_state(self, rocket: Rocket):
        cur = rocket.current_program
        if cur == Program.FAILURE:
            rocket.completion_time = np.inf
            return

        # PROGRAM_3 卸货：按 cargo_onboard 计入 M
        if cur == Program.PROGRAM_3:
            delivered = rocket.cargo_onboard
            if delivered > 0:
                rocket.total_cargo += delivered
                self.stats['total_deliveries'] += 1
            rocket.cargo_onboard = 0.0

        # 到达该程序就记一次该程序燃料成本，并同步计入环境外部成本
        self._add_cost(
            rocket,
            fuel_delta=self.program_fuel_cost[cur],
            env_lambda=self.program_env_lambda.get(cur, 0.0)
        )

        # 在 PROGRAM_3 处加“按货量计”的电梯燃料成本（对应论文程序一：λ1=0.4）
        if cur == Program.PROGRAM_3:
            eid = rocket.assigned_elevator
            elevator_fuel = rocket.cargo_capacity * self.space_elevators[eid]['unit_fuel_cost']
            self._add_cost(
                rocket,
                fuel_delta=elevator_fuel,
                env_lambda=self.elevator_env_lambda
            )

        # 随机转移
        entering = self._next_program(cur)
        if entering == Program.FAILURE:
            rocket.current_program = Program.FAILURE
            rocket.completion_time = np.inf
            self.stats['total_failures'] += 1
            return

        base_t = rocket.completion_time

        # 直接进入下一段（无发射窗口）
        finish_t = base_t + self.program_time[entering]
        rocket.current_program = entering
        rocket.completion_time = finish_t

        # 完成 PROGRAM_1/4 后到银河港：排队装货，再“立即随机转移一次”
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

    # ------------------- 统计/记录 -------------------

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

    # ------------------- 运行（事件堆版） -------------------

    def run(self, verbose: bool = True, record_interval: int = 2000, print_every: Optional[int] = None):
        """
        record_interval: 每隔多少“事件处理次数”记录一次 history
        print_every:     每隔多少“事件处理次数”打印一次（None 表示使用 record_interval*5 的旧策略）
        """
        if not self.space_elevators:
            raise RuntimeError("请先 add_space_elevator() 添加银河港。")
        if not self.assembly_lines:
            raise RuntimeError("请先 add_elevator_assembly() 为银河港配置组装速率。")

        if print_every is None:
            print_every = record_interval * 5  # 保持你原来“很稀疏”的打印频率

        print("\n" + "=" * 70)
        print("开始仿真：情景1（事件堆版 heapq）")
        print(f"总需求: {self.total_demand:.2e} 公吨 | 单箭运力: {self.rocket_capacity} 公吨")
        print("银河港组装速率（枚/天）：")
        for eid, line in self.assembly_lines.items():
            print(f"  - 银河港 {eid}: {line.rate}")
        print("银河港装货能力（公吨/天）：")
        for eid, info in self.space_elevators.items():
            print(f"  - 银河港 {eid}: {info['loading_capacity']:.0f}")
        print("环境影响系数 λ：")
        for p, lam in self.program_env_lambda.items():
            print(f"  - {p.name}: {lam}")
        print(f"  - ELEVATOR_LOADING: {self.elevator_env_lambda}")
        print("=" * 70 + "\n")

        # 初始化事件堆
        heap: List[Tuple[float, int, str, Any]] = []

        # 推入每个银河港的“下一次组装完成事件”
        for eid, t_ready in self.next_assembly_ready.items():
            self._push_event(heap, t_ready, 'assembly', eid)

        iteration = 0
        termination_reason = "unknown"

        # 主循环：每次弹出最早事件
        while True:
            # 若已满足需求：终止
            if self.get_total_cargo() >= self.total_demand:
                termination_reason = "demand_met"
                break

            if not heap:
                termination_reason = "stalled"
                print("警告: 事件堆为空，无可推进事件，终止。")
                break

            # 取出当前最早时刻
            t = heap[0][0]
            self.current_time = t

            # 处理同一时刻 t 的所有事件（注意：过程中可能推入同一时刻的新事件，也会被处理）
            while heap and abs(heap[0][0] - t) < 1e-12:
                _, _, etype, payload = heapq.heappop(heap)

                if etype == 'assembly':
                    eid = int(payload)

                    # 过滤“过期的组装事件”
                    if not np.isfinite(self.next_assembly_ready.get(eid, np.inf)):
                        continue
                    if abs(self.next_assembly_ready[eid] - t) > 1e-12:
                        continue

                    # 生成新火箭
                    rocket = self._create_rocket_from_elevator_ready(eid, ready_time=t)
                    # 推入火箭的下一次流程事件
                    self._push_event(heap, rocket.completion_time, 'rocket', rocket.rocket_id)

                    # 安排该银河港下一次组装完成，并推入事件堆
                    self.next_assembly_ready[eid] = self.assembly_lines[eid].schedule_next_ready()
                    self._push_event(heap, self.next_assembly_ready[eid], 'assembly', eid)

                elif etype == 'rocket':
                    rid = int(payload)

                    # rid 可能越界（极端情况），做保护
                    if rid < 0 or rid >= len(self.rockets):
                        continue
                    rocket = self.rockets[rid]

                    # 过滤“过期的火箭事件”（因为火箭 completion_time 会更新）
                    if not np.isfinite(rocket.completion_time):
                        continue
                    if abs(rocket.completion_time - t) > 1e-12:
                        continue

                    # 推进火箭状态
                    self.update_rocket_state(rocket)

                    # 若未失效，推入下一次火箭事件
                    if np.isfinite(rocket.completion_time) and rocket.current_program != Program.FAILURE:
                        self._push_event(heap, rocket.completion_time, 'rocket', rocket.rocket_id)

                else:
                    raise RuntimeError(f"未知事件类型: {etype}")

                # “事件处理次数”+1
                iteration += 1

                # 记录与打印（按事件次数）
                if iteration % record_interval == 0:
                    self.record_state()

                if verbose and (iteration % print_every == 0):
                    cargo = self.get_total_cargo()
                    progress = cargo / self.total_demand * 100.0
                    avg_wait = float(np.mean(self.stats['elevator_waiting_time'])) if self.stats['elevator_waiting_time'] else 0.0
                    env_cost = self.get_total_env_cost()
                    print(
                        f"迭代:{iteration:10d} | "
                        f"t={self.current_time:10.2f}天 | "
                        f"M={cargo:.3e} | "
                        f"{progress:6.2f}% | "
                        f"交付={self.stats['total_deliveries']:9d} | "
                        f"失效={self.stats['total_failures']:9d} | "
                        f"火箭数={len(self.rockets):9d} | "
                        f"平均等待={avg_wait:.2f}天 | "
                        f"Env={env_cost:.3e}"
                    )

                if iteration > 2_000_000_000:
                    termination_reason = "iteration_limit"
                    print("警告: 事件次数过多，终止仿真!")
                    break

            if termination_reason == "iteration_limit":
                break

        # 结束前再记录一次
        self.record_state()

        final_cargo = self.get_total_cargo()
        final_cost = self.get_total_fuel_cost()
        final_env = self.get_total_env_cost()
        avg_wait = float(np.mean(self.stats['elevator_waiting_time'])) if self.stats['elevator_waiting_time'] else 0.0
        max_wait = float(np.max(self.stats['elevator_waiting_time'])) if self.stats['elevator_waiting_time'] else 0.0

        print("\n" + "=" * 70)
        print("仿真完成!（事件堆版）")
        print("=" * 70)
        print(f"结束原因: {termination_reason}")
        print(f"完成时间 T*: {self.current_time:.2f} 天")
        print(f"累计送达 M(T*): {final_cargo:.3e} 公吨")
        print(f"总燃料成本: {final_cost:.3e} 吨")
        print(f"总环境外部成本(等价燃料): {final_env:.3e}")
        print(f"总交付次数: {self.stats['total_deliveries']}")
        print(f"总失效次数: {self.stats['total_failures']}")
        print(f"最终火箭总数: {len(self.rockets)}")
        if self.stats['total_deliveries'] > 0:
            print(f"平均单次运输成本: {final_cost / self.stats['total_deliveries']:.2f} 吨燃料")
            print(f"平均单次环境外部成本: {final_env / self.stats['total_deliveries']:.2f} 等价燃料")
        if self.stats['elevator_waiting_time']:
            print(f"银河港平均等待时间: {avg_wait:.2f} 天")
            print(f"银河港最大等待时间: {max_wait:.2f} 天")
            print(f"发生等待次数: {len(self.stats['elevator_waiting_time'])}")
        print("=" * 70 + "\n")

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


# ------------------ 示例：银河港 1/2/3 ------------------

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

    # 银河港 1/2/3
    for eid in [1, 2, 3]:
        sim.add_space_elevator(eid, loading_capacity=elevator_loading_capacity, unit_fuel_cost=0.5)
        sim.add_elevator_assembly(eid, assembly_rate_per_day=assembly_rate_per_day_each_elevator)

    return sim


if __name__ == "__main__":
    sim = setup_scenario_1_elevator_only(
        total_demand=1e6,
        seed=2026,
        rocket_capacity=150.0,
        elevator_loading_capacity=179000 / 365 * 3,
        assembly_rate_per_day_each_elevator=0.05,
    )

    # 建议：print_every 调小一点，否则你又会觉得“卡住了”
    result = sim.run(verbose=True, record_interval=2000, print_every=2000)
    print("Done.")
