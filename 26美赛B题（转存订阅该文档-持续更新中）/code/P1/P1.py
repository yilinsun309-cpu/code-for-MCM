import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple, Optional
from enum import Enum
import matplotlib.pyplot as plt
from collections import defaultdict
import heapq

# 设置中文字体支持
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


class Program(Enum):
    """程序枚举"""
    PROGRAM_1 = 1  # 太空电梯运输 → 银河港顶端锚
    PROGRAM_2 = 2  # 火箭满载：地面 → 地月转移轨道
    PROGRAM_3 = 3  # 火箭满载：地月转移轨道 → 月球殖民地
    PROGRAM_4 = 4  # 火箭空载：月球 → 银河港顶端锚
    PROGRAM_5 = 5  # 火箭空载：月球 → 地面发射场


class TransportScenario(Enum):
    """运输情景枚举"""
    SCENARIO_1 = 1  # 仅使用银河港太空电梯系统
    SCENARIO_2 = 2  # 仅使用传统地面火箭系统
    SCENARIO_3 = 3  # 太空电梯与传统火箭的组合方案


@dataclass
class Rocket:
    """火箭类"""
    launch_site_id: int  # 发射场ID
    rocket_id: int  # 火箭ID
    current_program: Program  # 当前程序
    completion_time: float  # 完成当前程序的时间
    total_cargo: float  # 累计运输物资量 M_{j,i_j}
    total_fuel_cost: float  # 累计燃料成本 F_{j,i_j}
    cargo_capacity: float  # 载荷上限 q_{j,i_j}
    scenario: TransportScenario  # 所属情景
    assigned_elevator: Optional[int] = None  # 分配的银河港ID
    
    def __repr__(self):
        return f"Rocket(site={self.launch_site_id}, id={self.rocket_id}, program={self.current_program.value}, t={self.completion_time:.2f})"


class SpaceElevatorLoadingQueue:
    """银河港装货队列管理器"""
    
    def __init__(self, elevator_id: int, loading_capacity: float):
        """
        初始化银河港装货队列
        
        Parameters:
        -----------
        elevator_id: int
            银河港ID
        loading_capacity: float
            每天装货吞吐能力 C̄^load_k (公吨/天)
        """
        self.elevator_id = elevator_id
        self.loading_capacity = loading_capacity
        
        # 记录每一天的装货量: {day: total_cargo_loaded}
        self.daily_loading = defaultdict(float)
        
        # 等待装货的火箭队列: [(arrival_time, rocket)]
        self.waiting_queue = []
        
    def get_available_loading_time(self, arrival_time: float, cargo_amount: float) -> float:
        """
        计算火箭实际可以开始装货的时间
        
        考虑银河港每日装货能力约束：
        Σ_{当日新增} q_{j,i_j} ≤ C̄^load_k
        
        Parameters:
        -----------
        arrival_time: float
            火箭到达银河港的时间
        cargo_amount: float
            需要装载的货物量
            
        Returns:
        --------
        float: 实际可以开始装货的时间
        """
        current_day = int(np.floor(arrival_time))
        
        # 从到达日开始，寻找第一个有足够装货能力的日期
        search_day = current_day
        max_search_days = 1000  # 防止无限循环
        
        for _ in range(max_search_days):
            # 检查这一天的剩余装货能力
            used_capacity = self.daily_loading[search_day]
            remaining_capacity = self.loading_capacity - used_capacity
            
            if remaining_capacity >= cargo_amount:
                # 这一天有足够的容量
                # 装货时间在这一天内，取 max(arrival_time, search_day)
                loading_start_time = max(arrival_time, float(search_day))
                
                # 记录这一天的装货量
                self.daily_loading[search_day] += cargo_amount
                
                return loading_start_time
            
            # 这一天容量不足，检查下一天
            search_day += 1
        
        # 理论上不应该到这里
        print(f"警告: 银河港 {self.elevator_id} 装货队列搜索超时")
        return arrival_time
    
    def release_loading_capacity(self, loading_time: float, cargo_amount: float):
        """
        释放装货容量（用于回滚等操作）
        """
        day = int(np.floor(loading_time))
        self.daily_loading[day] -= cargo_amount
        if self.daily_loading[day] < 1e-9:
            del self.daily_loading[day]


class LunarTransportSimulation:
    """月球殖民地运输仿真模型"""
    
    def __init__(self, 
                 scenario: TransportScenario,
                 total_demand: float = 1e8,  # 总运输需求 D (公吨)
                 t0: float = 0.0):  # 仿真起始时刻
        """
        初始化仿真模型
        
        Parameters:
        -----------
        scenario: TransportScenario
            运输情景选择
        total_demand: float
            总运输需求(公吨)
        t0: float
            仿真起始时刻(天)
        """
        self.scenario = scenario
        self.total_demand = total_demand
        self.t0 = t0
        self.current_time = t0
        
        # 数据存储
        self.rockets: List[Rocket] = []
        self.space_elevators: Dict[int, dict] = {}  # 银河港信息
        self.elevator_queues: Dict[int, SpaceElevatorLoadingQueue] = {}  # 银河港队列管理器
        self.launch_sites: Dict[int, dict] = {}  # 发射场信息
        
        # 程序参数 (根据表格数据)
        self.program_time: Dict[Program, float] = {
            Program.PROGRAM_1: 14.0,    # 太空电梯运输，14天
            Program.PROGRAM_2: 0.5,     # 火箭满载发射，0.5天
            Program.PROGRAM_3: 3.0,     # 地月转移到月球，3天
            Program.PROGRAM_4: 3.0,     # 月球返回银河港，3天
            Program.PROGRAM_5: 4.0,     # 月球返回地面，4天
        }
        
        self.program_fuel_cost: Dict[Program, float] = {
            Program.PROGRAM_1: 60.0,      # 太空电梯燃料，50吨
            Program.PROGRAM_2: 3000.0,    # 满载发射，3000吨
            Program.PROGRAM_3: 8.2,       # 满载飞月球，8.2吨
            Program.PROGRAM_4: 2.353,     # 空载返回银河港，2.353吨
            Program.PROGRAM_5: 16.9,      # 空载返回地面，16.9吨
        }
        
        # 程序转移函数 φ_h
        self.transition_functions = {
            TransportScenario.SCENARIO_1: {
                Program.PROGRAM_1: Program.PROGRAM_3,
                Program.PROGRAM_3: Program.PROGRAM_4,
                Program.PROGRAM_4: Program.PROGRAM_3,
            },
            TransportScenario.SCENARIO_2: {
                Program.PROGRAM_2: Program.PROGRAM_3,
                Program.PROGRAM_3: Program.PROGRAM_5,
                Program.PROGRAM_5: Program.PROGRAM_2,
            },
            TransportScenario.SCENARIO_3: {
                Program.PROGRAM_2: Program.PROGRAM_3,
                Program.PROGRAM_3: Program.PROGRAM_4,
                Program.PROGRAM_4: Program.PROGRAM_3,
            }
        }
        
        # 需要在银河港装货的程序
        self.programs_need_elevator_loading = {
            Program.PROGRAM_1,  # 通过电梯到达银河港后需要装货
            Program.PROGRAM_4,  # 从月球返回银河港后需要装货
        }
        
        # 仿真历史记录
        self.history = {
            'time': [],
            'total_cargo': [],
            'total_fuel_cost': [],
            'active_rockets': [],
            'completed_deliveries': [],
            'elevator_queue_length': defaultdict(list),  # 各银河港的队列长度
            'elevator_daily_loading': defaultdict(list),  # 各银河港的每日装货量
        }
        
        # 统计信息
        self.stats = {
            'total_deliveries': 0,  # 总交付次数
            'rockets_by_site': defaultdict(int),  # 各发射场的火箭数
            'elevator_waiting_time': [],  # 银河港等待时间记录
            'elevator_congestion_days': 0,  # 银河港拥堵天数
        }
        
    def add_space_elevator(self, 
                          elevator_id: int, 
                          loading_capacity: float = 179000/365,  # 吞吐能力 C̄^load_k (公吨/天)
                          parallel_capacity: int = np.inf,  # 并行服务能力 m_k
                          unit_fuel_cost: float = 0.5):  # 单位质量运输燃料成本 g_k
        """添加银河港"""
        self.space_elevators[elevator_id] = {
            'loading_capacity': loading_capacity,
            'parallel_capacity': parallel_capacity,
            'unit_fuel_cost': unit_fuel_cost
        }
        
        # 创建装货队列管理器
        self.elevator_queues[elevator_id] = SpaceElevatorLoadingQueue(
            elevator_id=elevator_id,
            loading_capacity=loading_capacity
        )
        
    def add_launch_site(self, 
                       site_id: int,
                       site_name: str,
                       launch_interval: float,  # 发射间隔 p_j (天)
                       initial_launch_time: float,  # 起始发射时间 γ_j (天)
                       num_rockets: int,  # 可调度火箭数量
                       rocket_capacity: float = 100.0):  # 火箭载荷 q_{j,i_j} (公吨)
        """添加火箭发射场"""
        self.launch_sites[site_id] = {
            'name': site_name,
            'launch_interval': launch_interval,
            'initial_launch_time': initial_launch_time,
            'num_rockets': num_rockets,
            'rocket_capacity': rocket_capacity,
        }
        
    def get_launch_time_set(self, site_id: int, max_time: float = 100000.0) -> Set[float]:
        """
        生成发射场的可发射时间集合 T_j
        T_j = {γ_j + n*p_j | n = 0,1,2,...}
        """
        site_info = self.launch_sites[site_id]
        gamma_j = site_info['initial_launch_time']
        p_j = site_info['launch_interval']
        
        launch_times = set()
        n = 0
        while True:
            launch_time = gamma_j + n * p_j
            if launch_time > max_time:
                break
            if launch_time >= self.t0:
                launch_times.add(launch_time)
            n += 1
        
        return launch_times
            
    def initialize_rockets(self):
        """初始化所有火箭"""
        for site_id, site_info in self.launch_sites.items():
            launch_times = self.get_launch_time_set(site_id)
            
            for rocket_id in range(site_info['num_rockets']):
                # 根据情景确定初始程序
                if self.scenario == TransportScenario.SCENARIO_1:
                    initial_program = Program.PROGRAM_1
                else:  # SCENARIO_2 和 SCENARIO_3
                    initial_program = Program.PROGRAM_2
                
                # 计算初始完成时间(需要等待发射窗口)
                initial_time = self.get_next_launch_time(site_id, self.t0, launch_times)
                completion_time = initial_time + self.program_time[initial_program]
                
                # 为使用银河港的情景分配电梯
                assigned_elevator = None
                if self.scenario in [TransportScenario.SCENARIO_1, TransportScenario.SCENARIO_3]:
                    if len(self.space_elevators) > 0:
                        assigned_elevator = list(self.space_elevators.keys())[0]
                
                rocket = Rocket(
                    launch_site_id=site_id,
                    rocket_id=rocket_id,
                    current_program=initial_program,
                    completion_time=completion_time,
                    total_cargo=0.0,
                    total_fuel_cost=self.program_fuel_cost[initial_program],
                    cargo_capacity=site_info['rocket_capacity'],
                    scenario=self.scenario,
                    assigned_elevator=assigned_elevator
                )
                self.rockets.append(rocket)
                self.stats['rockets_by_site'][site_id] += 1
                
    def get_next_launch_time(self, site_id: int, current_time: float, 
                            launch_times: Optional[Set[float]] = None) -> float:
        """
        获取下一个可用发射时间
        t^launch_{j,i_j} = min{t' ∈ T_j | t' ≥ t}
        """
        if launch_times is None:
            launch_times = self.get_launch_time_set(site_id)
        
        valid_times = [t for t in launch_times if t >= current_time]
        if valid_times:
            return min(valid_times)
        else:
            # 如果没有预计算的时间，动态计算
            site_info = self.launch_sites[site_id]
            gamma_j = site_info['initial_launch_time']
            p_j = site_info['launch_interval']
            
            if current_time <= gamma_j:
                return gamma_j
            else:
                n = int(np.ceil((current_time - gamma_j) / p_j))
                return gamma_j + n * p_j
    
    def get_next_program(self, current_program: Program) -> Program:
        """
        根据程序转移函数获取下一个程序
        l' = φ_h(l)
        """
        return self.transition_functions[self.scenario][current_program]
    
    def apply_elevator_loading_constraint(self, rocket: Rocket, arrival_time: float) -> float:
        """
        应用银河港装货能力约束
        
        返回考虑装货能力约束后，火箭实际可以开始下一程序的时间
        
        Parameters:
        -----------
        rocket: Rocket
            需要装货的火箭
        arrival_time: float
            火箭到达银河港的时间
            
        Returns:
        --------
        float: 实际可以开始装货（继续下一程序）的时间
        """
        if rocket.assigned_elevator is None:
            return arrival_time
        
        elevator_queue = self.elevator_queues[rocket.assigned_elevator]
        
        # 获取考虑装货能力约束后的装货开始时间
        loading_start_time = elevator_queue.get_available_loading_time(
            arrival_time=arrival_time,
            cargo_amount=rocket.cargo_capacity
        )
        
        # 记录等待时间
        waiting_time = loading_start_time - arrival_time
        if waiting_time > 0:
            self.stats['elevator_waiting_time'].append(waiting_time)
        
        return loading_start_time
    
    def update_rocket_state(self, rocket: Rocket):
        """更新火箭状态"""
        current_program = rocket.current_program
        
        # 如果完成了程序3(卸货),更新运输量
        if current_program == Program.PROGRAM_3:
            rocket.total_cargo += rocket.cargo_capacity
            self.stats['total_deliveries'] += 1
        
        # 累计当前程序的燃料成本
        rocket.total_fuel_cost += self.program_fuel_cost[current_program]
        
        # 如果是程序3且使用银河港,还需要加上银河港的运输成本
        if current_program == Program.PROGRAM_3 and rocket.assigned_elevator is not None:
            elevator_id = rocket.assigned_elevator
            elevator_fuel = (rocket.cargo_capacity * 
                           self.space_elevators[elevator_id]['unit_fuel_cost'])
            rocket.total_fuel_cost += elevator_fuel
        
        # 转移到下一个程序: l' = φ_h(l)
        next_program = self.get_next_program(current_program)
        rocket.current_program = next_program
        
        # 计算完成时间: T_{j,i_j} ← T_{j,i_j} + τ_{l'}
        base_completion_time = rocket.completion_time
        next_time = base_completion_time + self.program_time[next_program]
        
        # 如果下一个程序需要地面发射(程序1或2),需要等待发射窗口
        if next_program in [Program.PROGRAM_1, Program.PROGRAM_2]:
            launch_times = self.get_launch_time_set(rocket.launch_site_id)
            launch_time = self.get_next_launch_time(
                rocket.launch_site_id, 
                base_completion_time, 
                launch_times
            )
            next_time = launch_time + self.program_time[next_program]
        
        # 关键：如果下一个程序需要在银河港装货，应用装货能力约束
        if next_program in self.programs_need_elevator_loading and rocket.assigned_elevator is not None:
            # 火箭到达银河港的时间
            arrival_time = next_time
            
            # 考虑装货能力约束，获取实际可以装货的时间
            loading_start_time = self.apply_elevator_loading_constraint(rocket, arrival_time)
            
            # 如果需要等待，则继续下一个程序的时间需要延后
            if loading_start_time > arrival_time:
                # 从装货开始时间继续执行后续程序
                next_program_after_loading = self.get_next_program(next_program)
                next_time = loading_start_time + self.program_time[next_program_after_loading]
                rocket.current_program = next_program_after_loading
        
        rocket.completion_time = next_time
        
    def get_total_cargo(self) -> float:
        """
        获取系统累计运输量
        M(t) = Σ_j Σ_{i_j} M_{j,i_j}(t)
        """
        return sum(rocket.total_cargo for rocket in self.rockets)
    
    def get_total_fuel_cost(self) -> float:
        """获取系统累计燃料成本"""
        return sum(rocket.total_fuel_cost for rocket in self.rockets)
    
    def record_state(self):
        """记录当前状态"""
        self.history['time'].append(self.current_time)
        self.history['total_cargo'].append(self.get_total_cargo())
        self.history['total_fuel_cost'].append(self.get_total_fuel_cost())
        self.history['active_rockets'].append(len(self.rockets))
        self.history['completed_deliveries'].append(self.stats['total_deliveries'])
        
        # 记录各银河港的每日装货量
        for elevator_id, queue in self.elevator_queues.items():
            current_day = int(np.floor(self.current_time))
            daily_loading = queue.daily_loading.get(current_day, 0.0)
            self.history['elevator_daily_loading'][elevator_id].append(daily_loading)
        
    def run(self, verbose: bool = True, record_interval: int = 1000):
        """
        运行仿真
        
        Parameters:
        -----------
        verbose: bool
            是否输出详细信息
        record_interval: int
            记录状态的间隔(事件数)
        """
        print(f"\n{'='*70}")
        print(f"开始仿真: 情景 {self.scenario.value}")
        print(f"总运输需求: {self.total_demand:.2e} 公吨")
        print(f"火箭总数: {len(self.rockets)}")
        if self.space_elevators:
            for elev_id, elev_info in self.space_elevators.items():
                print(f"银河港 {elev_id} 装货能力: {elev_info['loading_capacity']:.0f} 公吨/天")
        print(f"{'='*70}\n")
        
        self.initialize_rockets()
        
        iteration = 0
        last_cargo = 0
        
        while self.get_total_cargo() < self.total_demand:
            # 找到下一个要完成的事件: t ← min_{j,i_j} T_{j,i_j}
            min_time = min(rocket.completion_time for rocket in self.rockets)
            self.current_time = min_time
            
            # 处理所有在当前时间完成的火箭
            for rocket in self.rockets:
                if abs(rocket.completion_time - self.current_time) < 1e-9:
                    self.update_rocket_state(rocket)
            
            # 定期记录状态
            if iteration % record_interval == 0:
                self.record_state()
                if verbose and iteration % (record_interval * 5) == 0:
                    current_cargo = self.get_total_cargo()
                    progress = current_cargo / self.total_demand * 100
                    
                    # 计算平均等待时间
                    avg_wait = np.mean(self.stats['elevator_waiting_time']) if self.stats['elevator_waiting_time'] else 0
                    
                    print(f"迭代: {iteration:8d} | "
                          f"时间: {self.current_time:8.2f}天 | "
                          f"累计运输: {current_cargo:.3e}公吨 | "
                          f"完成度: {progress:6.2f}% | "
                          f"交付: {self.stats['total_deliveries']:6d} | "
                          f"电梯等待: {avg_wait:.2f}天")
                    
                    last_cargo = current_cargo
            
            iteration += 1
            
            # 安全检查:防止无限循环
            if iteration > 1e8:
                print("警告: 迭代次数过多,终止仿真!")
                break
        
        # 记录最终状态
        self.record_state()
        
        # 输出最终结果
        final_cargo = self.get_total_cargo()
        final_cost = self.get_total_fuel_cost()
        avg_wait = np.mean(self.stats['elevator_waiting_time']) if self.stats['elevator_waiting_time'] else 0
        max_wait = max(self.stats['elevator_waiting_time']) if self.stats['elevator_waiting_time'] else 0
        
        print(f"\n{'='*70}")
        print(f"仿真完成!")
        print(f"{'='*70}")
        print(f"完成时间 (T*): {self.current_time:.2f} 天")
        print(f"总运输量 M(T*): {final_cargo:.3e} 公吨")
        print(f"总燃料成本: {final_cost:.3e} 吨")
        print(f"总交付次数: {self.stats['total_deliveries']}")
        print(f"平均单次运输成本: {final_cost/self.stats['total_deliveries']:.2f} 吨燃料")
        if self.stats['elevator_waiting_time']:
            print(f"银河港平均等待时间: {avg_wait:.2f} 天")
            print(f"银河港最大等待时间: {max_wait:.2f} 天")
            print(f"发生等待的次数: {len(self.stats['elevator_waiting_time'])}")
        print(f"{'='*70}\n")
            
        return {
            'completion_time': self.current_time,
            'total_cargo': final_cargo,
            'total_fuel_cost': final_cost,
            'total_deliveries': self.stats['total_deliveries'],
            'avg_elevator_wait': avg_wait,
            'max_elevator_wait': max_wait,
            'history': self.history
        }
    
    def plot_results(self, save_path: Optional[str] = None):
        """绘制仿真结果"""
        has_elevator = len(self.space_elevators) > 0
        num_plots = 4 if has_elevator else 3
        
        fig, axes = plt.subplots(num_plots, 1, figsize=(14, 4*num_plots))
        
        times = np.array(self.history['time'])
        
        # 1. 累计运输量
        axes[0].plot(times, self.history['total_cargo'], 'b-', linewidth=2, label='累计运输量')
        axes[0].axhline(y=self.total_demand, color='r', linestyle='--', 
                       linewidth=2, label=f'目标需求 ({self.total_demand:.2e}公吨)')
        axes[0].set_xlabel('时间 (天)', fontsize=12)
        axes[0].set_ylabel('累计运输量 (公吨)', fontsize=12)
        axes[0].set_title(f'情景 {self.scenario.value}: 累计运输量 M(t) 随时间变化', 
                         fontsize=14, fontweight='bold')
        axes[0].legend(fontsize=10)
        axes[0].grid(True, alpha=0.3)
        axes[0].ticklabel_format(style='scientific', axis='y', scilimits=(0,0))
        
        # 2. 累计燃料成本
        axes[1].plot(times, self.history['total_fuel_cost'], 'g-', linewidth=2)
        axes[1].set_xlabel('时间 (天)', fontsize=12)
        axes[1].set_ylabel('累计燃料成本 (吨)', fontsize=12)
        axes[1].set_title(f'情景 {self.scenario.value}: 累计燃料成本随时间变化', 
                         fontsize=14, fontweight='bold')
        axes[1].grid(True, alpha=0.3)
        axes[1].ticklabel_format(style='scientific', axis='y', scilimits=(0,0))
        
        # 3. 累计交付次数
        axes[2].plot(times, self.history['completed_deliveries'], 'm-', linewidth=2)
        axes[2].set_xlabel('时间 (天)', fontsize=12)
        axes[2].set_ylabel('累计交付次数', fontsize=12)
        axes[2].set_title(f'情景 {self.scenario.value}: 累计交付次数随时间变化', 
                         fontsize=14, fontweight='bold')
        axes[2].grid(True, alpha=0.3)
        
        # 4. 银河港每日装货量（如果使用银河港）
        if has_elevator:
            for elevator_id in self.elevator_queues.keys():
                if elevator_id in self.history['elevator_daily_loading']:
                    loading_data = self.history['elevator_daily_loading'][elevator_id]
                    if loading_data:
                        axes[3].plot(times[:len(loading_data)], loading_data, 
                                   linewidth=2, label=f'银河港 {elevator_id}')
            
            # 添加装货能力上限线
            for elevator_id, elev_info in self.space_elevators.items():
                axes[3].axhline(y=elev_info['loading_capacity'], 
                              color='r', linestyle='--', linewidth=2,
                              label=f'装货能力上限 ({elev_info["loading_capacity"]:.0f}公吨/天)')
            
            axes[3].set_xlabel('时间 (天)', fontsize=12)
            axes[3].set_ylabel('每日装货量 (公吨/天)', fontsize=12)
            axes[3].set_title(f'情景 {self.scenario.value}: 银河港每日装货量', 
                            fontsize=14, fontweight='bold')
            axes[3].legend(fontsize=10)
            axes[3].grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"图表已保存至: {save_path}")
        
        plt.show()


def setup_scenario_1(total_demand: float = 1e6, num_rockets_per_site: int = 10,
                     elevator_capacity: float = 1000.0) -> LunarTransportSimulation:
    """
    配置情景一: 仅使用银河港太空电梯系统
    """
    sim = LunarTransportSimulation(
        scenario=TransportScenario.SCENARIO_1,
        total_demand=total_demand,
        t0=0.0
    )
    
    # 添加银河港（带装货能力约束）
    sim.add_space_elevator(
        elevator_id=1,
        loading_capacity=elevator_capacity,  # 每天装货能力
        parallel_capacity=np.inf,
        unit_fuel_cost=0.5  # 约为火箭的1/50
    )
    
    # 添加主要发射场(基于2025年数据)
    launch_sites_data = [
        # (site_id, name, launch_interval, initial_time, num_rockets, capacity)
        (1, "加利福尼亚", 5.53, 9, num_rockets_per_site, 100),
        (2, "德克萨斯", 73, 15, num_rockets_per_site, 100),
        (3, "佛罗里达", 3.35, 3, num_rockets_per_site, 100),
        (4, "弗吉尼亚", 365, 351, num_rockets_per_site, 100),
        (5, "哈萨克斯坦", 60.83, 57, num_rockets_per_site, 100),
        (6, "法属圭亚那", 52.14, 64, num_rockets_per_site, 100),
        (7, "印度", 73, 28, num_rockets_per_site, 100),
        (8, "中国", 30.42, 22, num_rockets_per_site, 100),
        (9, "新西兰", 21.47, 38, num_rockets_per_site, 100),
    ]
    
    for site_data in launch_sites_data:
        sim.add_launch_site(*site_data)
    
    return sim


def setup_scenario_2(total_demand: float = 1e6, num_rockets_per_site: int = 10) -> LunarTransportSimulation:
    """
    配置情景二: 仅使用传统地面火箭系统
    """
    sim = LunarTransportSimulation(
        scenario=TransportScenario.SCENARIO_2,
        total_demand=total_demand,
        t0=0.0
    )
    
    # 添加主要发射场
    launch_sites_data = [
        # (site_id, name, launch_interval, initial_time, num_rockets, capacity)
        (1, "加利福尼亚", 10.14, 9, num_rockets_per_site, 100),
        (2, "德克萨斯", 73, 15, num_rockets_per_site, 100),
        (3, "佛罗里达", 36.5, 3, num_rockets_per_site, 100),
        (4, "弗吉尼亚", 365, 351, num_rockets_per_site, 100),
        (5, "哈萨克斯坦", 60.83, 57, num_rockets_per_site, 100),
        (6, "法属圭亚那", 52.14, 64, num_rockets_per_site, 100),
        (7, "印度", 73, 28, num_rockets_per_site, 100),
        (8, "中国", 30.42, 22, num_rockets_per_site, 100),
        (9, "新西兰", 21.47, 38, num_rockets_per_site, 100),
    ]
    
    for site_data in launch_sites_data:
        sim.add_launch_site(*site_data)
    
    return sim


def setup_scenario_3(total_demand: float = 1e6, num_rockets_per_site: int = 10,
                     elevator_capacity: float = 1000.0) -> LunarTransportSimulation:
    """
    配置情景三: 太空电梯与传统火箭的组合方案
    """
    sim = LunarTransportSimulation(
        scenario=TransportScenario.SCENARIO_3,
        total_demand=total_demand,
        t0=0.0
    )
    
    # 添加银河港（带装货能力约束）
    sim.add_space_elevator(
        elevator_id=1,
        loading_capacity=elevator_capacity,
        parallel_capacity=np.inf,
        unit_fuel_cost=0.5
    )
    
    # 添加主要发射场
    launch_sites_data = [
        # (site_id, name, launch_interval, initial_time, num_rockets, capacity)
        (1, "加利福尼亚", 5.53, 9, num_rockets_per_site, 66),
        (2, "德克萨斯", 73, 15, num_rockets_per_site, 5),
        (3, "佛罗里达", 3.35, 3, num_rockets_per_site, 100),
        (4, "弗吉尼亚", 365, 351, num_rockets_per_site, 1),
        (5, "哈萨克斯坦", 60.83, 57, num_rockets_per_site, 6),
        (6, "法属圭亚那", 52.14, 64, num_rockets_per_site, 7),
        (7, "印度", 73, 28, num_rockets_per_site, 5),
        (8, "中国", 30.42, 22, num_rockets_per_site, 12),
        (9, "新西兰", 21.47, 38, num_rockets_per_site, 17),
    ]
    
    for site_data in launch_sites_data:
        sim.add_launch_site(*site_data)
    
    return sim


def compare_scenarios(total_demand: float = 1e6, num_rockets: int = 10,
                     elevator_capacity: float = 1000.0):
    """比较三种情景"""
    results = {}
    
    scenarios_setup = [
        (TransportScenario.SCENARIO_1, lambda: setup_scenario_1(total_demand, num_rockets, elevator_capacity)),
        (TransportScenario.SCENARIO_3, lambda: setup_scenario_3(total_demand, num_rockets, elevator_capacity)),
        (TransportScenario.SCENARIO_2, lambda: setup_scenario_2(total_demand, num_rockets)),
    ]
    
    for scenario, setup_func in scenarios_setup:
        print(f"\n{'#'*70}")
        print(f"# 运行情景 {scenario.value}")
        print(f"{'#'*70}")
        
        sim = setup_func()
        result = sim.run(verbose=True, record_interval=1000)
        results[scenario] = result
        
        # 绘制结果
        sim.plot_results(save_path=f"scenario_{scenario.value}_results.png")
    
    # 比较汇总
    print("\n" + "="*90)
    print("三种情景对比汇总")
    print("="*90)
    print(f"{'情景':<8} {'完成时间':<12} {'燃料成本':<15} {'交付次数':<10} "
          f"{'平均成本':<12} {'电梯等待':<12}")
    print("-"*90)
    
    for scenario in [TransportScenario.SCENARIO_1, TransportScenario.SCENARIO_2, TransportScenario.SCENARIO_3]:
        res = results[scenario]
        avg_cost = res['total_fuel_cost'] / res['total_deliveries']
        avg_wait = res.get('avg_elevator_wait', 0)
        
        print(f"{scenario.value:<8} "
              f"{res['completion_time']:<12.2f} "
              f"{res['total_fuel_cost']:<15.3e} "
              f"{res['total_deliveries']:<10} "
              f"{avg_cost:<12.2f} "
              f"{avg_wait:<12.2f}")
    
    print("="*90)
    
    # 绘制对比图
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    
    scenario_names = ['情景1\n(仅电梯)', '情景2\n(仅火箭)', '情景3\n(组合)']
    colors = ['#3498db', '#e74c3c', '#2ecc71']
    
    # 完成时间对比
    times = [results[s]['completion_time'] for s in [TransportScenario.SCENARIO_1, 
             TransportScenario.SCENARIO_2, TransportScenario.SCENARIO_3]]
    axes[0, 0].bar(scenario_names, times, color=colors)
    axes[0, 0].set_ylabel('完成时间 (天)', fontsize=12)
    axes[0, 0].set_title('完成时间对比', fontsize=14, fontweight='bold')
    axes[0, 0].grid(True, alpha=0.3, axis='y')
    
    # 燃料成本对比
    costs = [results[s]['total_fuel_cost'] for s in [TransportScenario.SCENARIO_1, 
             TransportScenario.SCENARIO_2, TransportScenario.SCENARIO_3]]
    axes[0, 1].bar(scenario_names, costs, color=colors)
    axes[0, 1].set_ylabel('总燃料成本 (吨)', fontsize=12)
    axes[0, 1].set_title('燃料成本对比', fontsize=14, fontweight='bold')
    axes[0, 1].ticklabel_format(style='scientific', axis='y', scilimits=(0,0))
    axes[0, 1].grid(True, alpha=0.3, axis='y')
    
    # 平均单次成本对比
    avg_costs = [results[s]['total_fuel_cost']/results[s]['total_deliveries'] 
                 for s in [TransportScenario.SCENARIO_1, TransportScenario.SCENARIO_2, 
                          TransportScenario.SCENARIO_3]]
    axes[1, 0].bar(scenario_names, avg_costs, color=colors)
    axes[1, 0].set_ylabel('平均单次运输成本 (吨燃料)', fontsize=12)
    axes[1, 0].set_title('单次运输成本对比', fontsize=14, fontweight='bold')
    axes[1, 0].grid(True, alpha=0.3, axis='y')
    
    # 银河港等待时间对比
    wait_times = [results[s].get('avg_elevator_wait', 0) 
                  for s in [TransportScenario.SCENARIO_1, TransportScenario.SCENARIO_2, 
                           TransportScenario.SCENARIO_3]]
    axes[1, 1].bar(scenario_names, wait_times, color=colors)
    axes[1, 1].set_ylabel('平均银河港等待时间 (天)', fontsize=12)
    axes[1, 1].set_title('银河港等待时间对比', fontsize=14, fontweight='bold')
    axes[1, 1].grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig('scenarios_comparison.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    return results


if __name__ == "__main__":
    print("\n" + "="*80)
    print(" "*20 + "月球殖民地运输仿真系统")
    print(" "*15 + "(含银河港装货能力约束)")
    print("="*80)
    
    # 运行三种情景对比
    # 注意: 这里使用较小的需求量用于快速测试
    # elevator_capacity 参数控制银河港每日装货能力
    
    results = compare_scenarios(
        total_demand=1e8,        
        num_rockets=100,          
        elevator_capacity=179000/365*3
    )
    
    print("\n仿真完成! 结果已保存。")
    print("\n提示: 可以调整 elevator_capacity 参数来观察银河港装货能力对系统的影响")