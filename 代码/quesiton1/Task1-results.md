# Task 1 — Deterministic baseline（solve_model1.py 默认参数运行结果）

假设：无失效、无排队、站点总年发射频次 `f_total = 3834 /yr`，电梯满可用；成本使用常数发射单价。

全局参数（与脚本 `Params` 默认一致）：  
`M_goal = 1.0e8 ton`，`Cap_SE = 5.37e5 ton/yr`，`Cap_Rock = 125 ton`，`f_cycle = 60 /yr`，  
`C_launch = 1.5e8 USD/launch`（注意：150M），`C_elec_unit = 7156.8 USD/ton`，`C_maint = 1.2e8 USD/yr`，`C_TV_fixed = 3.0e8 USD/yr`。  
电梯能耗 14.8 kWh/kg，电价假设 0.484 USD/kWh → 7156.8 USD/ton（排放强度另用于 Task 4）。

## Scenario A — 纯电梯 + 轨道循环（闭式解）
- 工期 \(T_A = M_{goal}/Cap_{SE} = 186.22\ \text{yr}\)
- 在轨运输火箭需求 \(N_{A}^{*} = \lceil Cap_{SE}/(f_{cycle} \cdot Cap_{Rock}) \rceil = 72\)
- 成本组成：发射 \(72\times1.5e8\) + 电费 \(1e8\times7156.8\) + 年运维 \(\underbrace{(C_{maint}+C_{TV\_fixed})}_{=4.2e8}\times186.22\)  
  总成本 \(C_A \approx 8.05\times10^{11}\ \text{USD}\)

## Scenario B — 纯火箭直送（闭式解）
- 发射次数 \(N_{B}^{*} = \lceil M_{goal}/Cap_{Rock}\rceil = 800{,}000\)
- 工期 \(T_B = N_{B}^{*} / f_{total} = 208.659\ \text{yr}\)
- 成本 \(C_B = N_{B}^{*} \times 1.5e8 \approx 1.20025\times10^{14}\ \text{USD}\)

## Scenario C — 混合（平行流 + 穷举优化）
- 穷举 \(N_{Rock}\in[0,800{,}000]\) 并做加权/帕累托筛。  
- 推荐解（距理想点最短）：  
  \(N_{C}^{*}=188{,}655,\quad T_C=142.306\ \text{yr},\quad C_C=2.89049\times10^{13}\ \text{USD}\)  
  对应电梯分担 \(M_{SE}\) 与在轨运力 \(R\) 见 `results/model1/scenario_summary.json`。
- 可行解计数 800,000，帕累托前沿 377,166 个（详见导出的 CSV）。

文件位置：`代码/results/model1/`（pareto_all_feasible.csv, pareto_front.csv, weighted_sum_solutions.csv, scenario_summary.json, pareto.png）。

> 说明：本结果仅为理想吞吐基线，未计入失效、排队、生态限额；Task 2–4 将在此基础上修正。更新：2026‑02‑03 依据最新脚本运行日志。
