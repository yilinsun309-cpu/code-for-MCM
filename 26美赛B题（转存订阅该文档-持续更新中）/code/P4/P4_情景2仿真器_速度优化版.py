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
    """情景2所需程序枚举（含失效吸收态）"""
    PROGRAM_2 = 2
    PROGRAM_3 = 3  # 卸货点：计入M（按 cargo_onboard 计）
    PROGRAM_4 = 4
    PROGRAM_5 = 5
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
    cargo_onboard: float = 0.0  # 情景2：进入PROGRAM_2即装满

    # NEW: 累计环境外部成本（与燃料等价成本同单位）
    total_env_cost: float = 0.0

    def __repr__(self):
        return (f"Rocket(site={self.launch_site_id}, id={self.rocket_id}, "
                f"program={self.current_program.value}, t={self.completion_time:.2f}, "
                f"onboard={self.cargo_onboard:.1f})")


class LunarTransportSimulationScenario2:
    """
    情景2仿真器（随机失效 + 装货绑定交付（地面装满） + 年度扩编）
    循环：2 -> 3 -> 4 -> 5 -> 2
    - 进入 PROGRAM_2：地面装满 cargo_onboard = cargo_capacity
    - PROGRAM_3：卸货，按 cargo_onboard 计入 M，并清零 cargo_onboard
    - 每个程序结束后可能以 p_fail 进入 FAILURE（吸收态）

    ✅ 事件堆版（heapq）：
    事件类型：
    - ('rocket', rocket_index)
    - ('expand', None)  年度扩编
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
        self.current_time = float(t0)
        self.rng = np.random.default_rng(seed)

        self.annual_rocket_increase = int(annual_rocket_increase)
        self.max_years = max_years

        self.rockets: List[Rocket] = []
        self.launch_sites: Dict[int, dict] = {}

        # 情景2各程序耗时（天）
        self.program_time: Dict[Program, float] = {
            Program.PROGRAM_2: 0.5,
            Program.PROGRAM_3: 3.0,
            Program.PROGRAM_4: 3.0,
            Program.PROGRAM_5: 4.0,
        }

        # 情景2各程序燃料成本（吨）
        self.program_fuel_cost: Dict[Program, float] = {
            Program.PROGRAM_2: 3000.0,
            Program.PROGRAM_3: 8.2,
            Program.PROGRAM_4: 2.353,
            Program.PROGRAM_5: 16.9,
            Program.FAILURE: 0.0,
        }

        # NEW: 环境影响系数 λ（按你给的论文段落）
        # 程序二：地面发射进入地月转移轨道 -> λ2 = 3.0
        # 程序三：地月转移至月球并着陆 -> λ3 = 0.1
        # 程序四：月球起飞回收到顶端锚处 -> λ4 = 1.3
        # 程序五：再入并回收至发射场 -> λ5 = 1.6
        self.program_env_lambda: Dict[Program, float] = {
            Program.PROGRAM_2: 3.0,
            Program.PROGRAM_3: 0.1,
            Program.PROGRAM_4: 1.3,
            Program.PROGRAM_5: 1.6,
            Program.FAILURE: 0.0,
        }

        # 每个程序结束时失效概率 p_fail（进入 FAILURE）
        self.failure_prob: Dict[Program, float] = {
            Program.PROGRAM_2: 0.02,
            Program.PROGRAM_3: 0.05,
            Program.PROGRAM_4: 0.03,
            Program.PROGRAM_5: 0.04,
        }

        # 情景2确定性转移
        self.transition_det: Dict[Program, Program] = {
            Program.PROGRAM_2: Program.PROGRAM_3,
            Program.PROGRAM_3: Program.PROGRAM_4,
            Program.PROGRAM_4: Program.PROGRAM_5,
            Program.PROGRAM_5: Program.PROGRAM_2,
        }

        self.history = {
            'time': [],
            'total_cargo': [],
            'total_fuel_cost': [],
            'total_env_cost': [],      # NEW
            'active_rockets': [],
            'failed_rockets': [],
            'completed_deliveries': [],
            'total_rockets': [],
        }

        self.stats = {
            'total_deliveries': 0,
            'total_failures': 0,
            'rockets_by_site': defaultdict(int),
            'total_expansions': 0,
        }

        # 年度扩编事件
        self._next_expansion_time = self.t0 + 365.0
        self._expansion_count = 0

        # 事件堆序号（确保同一时刻稳定排序）
        self._event_seq = 0

    # ------------------- 发射场配置 -------------------

    def add_launch_site(
        self,
        site_id: int,
        site_name: str,
        launch_interval: float,
        initial_launch_time: float,
        num_rockets_initial: int,
        rocket_capacity: float = 150
    ):
        self.launch_sites[site_id] = {
            'name': site_name,
            'launch_interval': float(launch_interval),
            'initial_launch_time': float(initial_launch_time),
            'num_rockets_initial': int(num_rockets_initial),
            'rocket_capacity': float(rocket_capacity),
            'next_rocket_id': 0,
        }

    def get_launch_time_set(self, site_id: int, max_time: float = 200000.0):
        """生成该发射场未来发射窗口集合（用于离散窗口约束）"""
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
        """返回 >= current_time 的最早发射窗口"""
        if launch_times is None:
            launch_times = self.get_launch_time_set(site_id)
        valid = [t for t in launch_times if t >= current_time]
        if valid:
            return min(valid)

        # 兜底（避免 max_time 不够导致集合里没有）
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

    # ------------------- 创建火箭/初始化/扩编 -------------------

    def _create_rocket(self, site_id: int, request_time: float) -> Rocket:
        site = self.launch_sites[site_id]
        rocket_id = site['next_rocket_id']
        site['next_rocket_id'] += 1

        initial_program = Program.PROGRAM_2

        # 发射窗口从 request_time 开始匹配
        launch_times = self.get_launch_time_set(site_id)
        launch_time = self.get_next_launch_time(site_id, request_time, launch_times)

        completion_time = launch_time + self.program_time[initial_program]

        # 进入 PROGRAM_2 视为地面装满
        cargo_onboard = site['rocket_capacity']

        self.stats['rockets_by_site'][site_id] += 1

        rocket = Rocket(
            launch_site_id=site_id,
            rocket_id=rocket_id,
            current_program=initial_program,
            completion_time=completion_time,
            total_cargo=0.0,
            total_fuel_cost=0.0,  # 改为0，统一走 _add_cost，避免漏加 env
            cargo_capacity=site['rocket_capacity'],
            cargo_onboard=cargo_onboard,
            total_env_cost=0.0
        )

        # 注意：你原始代码里这里就已经加了 PROGRAM_2 的燃料成本；
        # 我们保持一致：火箭一创建就视为“已进入 PROGRAM_2”，因此先加一次 PROGRAM_2 成本（含环境）
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
        """年度扩编：每个发射场增加 annual_rocket_increase 枚火箭"""
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
        """先按确定性转移，再按当前程序失效概率决定是否吸收至 FAILURE"""
        if current_program == Program.FAILURE:
            return Program.FAILURE
        nxt = self.transition_det.get(current_program, current_program)
        p_fail = self.failure_prob.get(current_program, 0.0)
        if self.rng.random() < p_fail:
            return Program.FAILURE
        return nxt

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

        # 成本累计（保持你原始写法：每次事件到达时再加一次“当前程序成本”）
        self._add_cost(
            rocket,
            fuel_delta=self.program_fuel_cost[cur],
            env_lambda=self.program_env_lambda.get(cur, 0.0)
        )

        # 随机转移
        nxt = self.get_next_program_stochastic(cur)
        if nxt == Program.FAILURE:
            rocket.current_program = Program.FAILURE
            rocket.completion_time = np.inf
            self.stats['total_failures'] += 1
            return

        base_t = rocket.completion_time

        # 进入 PROGRAM_2：地面装满
        if nxt == Program.PROGRAM_2:
            rocket.cargo_onboard = rocket.cargo_capacity

        # 进入 PROGRAM_2 需要对齐发射窗口
        start_t = base_t
        if nxt == Program.PROGRAM_2:
            launch_times = self.get_launch_time_set(rocket.launch_site_id)
            start_t = self.get_next_launch_time(rocket.launch_site_id, base_t, launch_times)

        finish_t = start_t + self.program_time[nxt]
        rocket.current_program = nxt
        rocket.completion_time = finish_t

    # ------------------- 统计/记录 -------------------

    def get_total_cargo(self) -> float:
        return sum(r.total_cargo for r in self.rockets)

    def get_total_fuel_cost(self) -> float:
        return sum(r.total_fuel_cost for r in self.rockets)

    def get_total_env_cost(self) -> float:
        return sum(r.total_env_cost for r in self.rockets)

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

    # ------------------- 事件堆工具 -------------------

    def _push_event(self, heap: List[Tuple[float, int, str, Any]], t: float, etype: str, payload: Any):
        if not np.isfinite(t):
            return
        self._event_seq += 1
        heapq.heappush(heap, (float(t), self._event_seq, etype, payload))

    # ------------------- 主循环（事件堆版） -------------------

    def run(self, verbose: bool = True, record_interval: int = 1000, print_every: Optional[int] = None):
        print(f"\n{'=' * 70}")
        print("开始仿真: 情景 2（事件堆版 heapq + 环境影响）")
        print(f"总运输需求: {self.total_demand:.2e} 公吨")
        print(f"年度扩编: 每年每个发射场新增 {self.annual_rocket_increase} 枚火箭")
        print("环境影响系数 λ：")
        for p, lam in self.program_env_lambda.items():
            print(f"  - {p.name}: {lam}")
        print(f"{'=' * 70}\n")

        if print_every is None:
            print_every = record_interval * 5  # 默认稀疏打印（和你原来一致）

        self.initialize_rockets()
        print(f"初始火箭总数: {len(self.rockets)}")
        print(f"{'=' * 70}\n")

        # 初始化事件堆
        heap: List[Tuple[float, int, str, Any]] = []

        # 推入年度扩编事件
        self._push_event(heap, self._next_expansion_time, 'expand', None)

        # 推入所有初始火箭事件
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

            # 取最早事件时刻
            t = heap[0][0]
            self.current_time = t

            # 处理同一时刻 t 的所有事件（包含处理过程中 push 的同一时刻事件）
            while heap and abs(heap[0][0] - t) < 1e-12:
                _, _, etype, payload = heapq.heappop(heap)

                if etype == 'expand':
                    # 过滤过期扩编事件
                    if abs(self._next_expansion_time - t) > 1e-9:
                        continue

                    self.apply_annual_expansion(t)

                    # 将新火箭的事件推入堆
                    # 新火箭都追加在 self.rockets 末尾，索引为 old_len .. new_len-1
                    # 为了不丢事件，这里用“本次扩编前后的长度差”来推入
                    # （apply_annual_expansion 内部会 append rockets）
                    # ——我们通过统计 rockets_by_site 增量会复杂，这里直接用长度差。
                    # 但 apply_annual_expansion 里没返回 old_len，所以我们在此处做：
                    # 方案：扩编前先记 old_len。
                else:
                    pass

                # 注意：上面 expand 需要知道 old_len/new_len，为了写得更清晰，
                # 我们把 expand 的逻辑搬到一个小块里重写一次：
                if etype == 'expand':
                    # 重新执行：用 old_len/new_len 推入新火箭事件
                    old_len = len(self.rockets)
                    # (上面已经 apply_annual_expansion 过了会错)
                    # 为避免重复，我们在这里用一个标记：如果我们刚才执行过 apply_annual_expansion，就跳过。
                    # ——所以把 expand 逻辑重写：只在这里做一次，删除上面那段。
                    pass

                # 为避免混乱，我们把 expand / rocket 分支在下面重新写一遍（正确版本）
                break  # 跳出当前 while，进入“修正版同一时刻处理”

            # -------- 修正版：同一时刻处理（清晰、不重复） --------
            # 重新把同一时刻 t 的事件收集出来一次性处理，避免上面重复逻辑
            # （为了保持“完整代码可直接跑”，我们采用这段修正实现）
            same_time_events = []
            while heap and abs(heap[0][0] - t) < 1e-12:
                same_time_events.append(heapq.heappop(heap))

            # 把刚才 pop 的第一个事件也补进去（因为 heap[0] 已经变了）
            # 但我们在进入修正版之前已经把一个事件 pop 了且丢了，这不行。
            # 所以最简单：不用上面的结构，直接在最初就用“修正版”。
            # ——因此，我们将 run() 在此处直接 raise，让你用下面提供的“最终正确 run()”。

            raise RuntimeError(
                "你看到这个错误说明你运行到了中间修补段。请使用下方提供的【最终正确版本】run()。"
            )

        # （理论上不会到这里）
        self.record_state()
        return {}


# ------------------ 情景2快捷配置 ------------------

def setup_scenario_2(
    total_demand: float = 1e6,
    num_rockets_per_site_initial: int = 10,
    seed: Optional[int] = 2026,
    annual_increase: int = 100
) -> LunarTransportSimulationScenario2:
    sim = LunarTransportSimulationScenario2(
        total_demand=total_demand,
        t0=0.0,
        seed=seed,
        annual_rocket_increase=annual_increase,
        max_years=None
    )

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


# =============================================================================
# ✅ 最终正确版本：把上面类里的 run() 用下面这个替换（完整、可直接跑）
# =============================================================================

def _scenario2_run_heapq(self: LunarTransportSimulationScenario2,
                         verbose: bool = True,
                         record_interval: int = 1000,
                         print_every: Optional[int] = None):
    print(f"\n{'=' * 70}")
    print("开始仿真: 情景 2（事件堆版 heapq + 环境影响）")
    print(f"总运输需求: {self.total_demand:.2e} 公吨")
    print(f"年度扩编: 每年每个发射场新增 {self.annual_rocket_increase} 枚火箭")
    print("环境影响系数 λ：")
    for p, lam in self.program_env_lambda.items():
        print(f"  - {p.name}: {lam}")
    print(f"{'=' * 70}\n")

    if print_every is None:
        print_every = record_interval * 5

    # 初始化火箭
    self.initialize_rockets()
    print(f"初始火箭总数: {len(self.rockets)}")
    print(f"{'=' * 70}\n")

    heap: List[Tuple[float, int, str, Any]] = []

    # 推入年度扩编事件
    self._push_event(heap, self._next_expansion_time, 'expand', None)

    # 推入所有初始火箭事件（payload 用 rocket 的“索引”）
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

        # 当前最早事件时刻
        t = heap[0][0]
        self.current_time = t

        # 收集并处理所有同一时刻 t 的事件
        events_at_t = []
        while heap and abs(heap[0][0] - t) < 1e-12:
            events_at_t.append(heapq.heappop(heap))

        # 逐个处理
        for _, _, etype, payload in events_at_t:
            if etype == 'expand':
                # 过滤过期扩编事件
                if abs(self._next_expansion_time - t) > 1e-9:
                    continue

                old_len = len(self.rockets)
                self.apply_annual_expansion(t)
                new_len = len(self.rockets)

                # 推入新火箭的事件
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

                # 过滤过期火箭事件（completion_time 被更新后旧事件失效）
                if not np.isfinite(r.completion_time):
                    continue
                if abs(r.completion_time - t) > 1e-9:
                    continue

                self.update_rocket_state(r)

                # 若未失效，推入下一次火箭事件
                if np.isfinite(r.completion_time) and r.current_program != Program.FAILURE:
                    self._push_event(heap, r.completion_time, 'rocket', idx)

                iteration += 1

            else:
                raise RuntimeError(f"未知事件类型: {etype}")

            # record / print（按“事件处理次数”）
            if iteration % record_interval == 0:
                self.record_state()

            if verbose and (iteration % print_every == 0):
                cargo = self.get_total_cargo()
                progress = cargo / self.total_demand * 100.0
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

    print(f"\n{'=' * 70}")
    print("情景2仿真完成!")
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
        print(f"平均单次运输成本: {final_cost / self.stats['total_deliveries']:.2f}")
        print(f"平均单次环境外部成本: {final_env / self.stats['total_deliveries']:.2f}")
    print(f"{'=' * 70}\n")

    return {
        'completion_time': self.current_time,
        'delivered_cargo': final_cargo,
        'total_fuel_cost': final_cost,
        'total_env_cost': final_env,
        'total_deliveries': self.stats['total_deliveries'],
        'total_failures': self.stats['total_failures'],
        'termination_reason': termination_reason,
        'final_rockets': len(self.rockets),
        'expansion_years': self._expansion_count,
        'history': self.history
    }


# 把正确 run() 挂回类（不改你原来调用方式）
LunarTransportSimulationScenario2.run = _scenario2_run_heapq


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print(" 月球殖民地运输仿真系统（仅情景2：事件堆版 + 环境影响）")
    print("=" * 80)

    sim = setup_scenario_2(
        total_demand=1e6,
        seed=2026,
        num_rockets_per_site_initial=100,
        annual_increase=10
    )

    # 建议：print_every 不要太大，否则会又感觉“卡”
    res = sim.run(verbose=True, record_interval=1000, print_every=2000)
    print("\n仿真完成! 结果已输出。")
