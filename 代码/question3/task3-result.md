


## Task 3 Monte Carlo 结果（当前 n_mc=1，需后续增大样本）

### 场景 A（scenario=1）
- runs: 1；feasible_runs: 0；stockout_runs: 1
- 关键输出：
  - max_gap_quantile_days: 17.08
  - S_moon_star_ton: 128,778.07
  - S_moon_min_ton: 189,104.47
  - mean_failures: 49；mean_launches: 47
  - mean_cost_usd: 7.9968e10
  - max_inventory_queue: 68；max_inventory_wait_days: 11.08；max_launch_wait_days: 6.65

### 场景 B（scenario=2）
- runs: 1；feasible_runs: 0；stockout_runs: 1
- 关键输出：
  - max_gap_quantile_days: 14.63
  - S_moon_star_ton: 110,293.03
  - S_moon_min_ton: 212,439.09
  - mean_direct_arrivals: 1298；mean_failures: 32；mean_launches: 30
  - mean_cost_usd: 1.947e10
  - max_inventory_queue: 0；max_launch_wait_days: 14.17

### 场景 C（scenario=3）
- runs: 1；feasible_runs: 0；stockout_runs: 1
- 关键输出：
  - max_gap_quantile_days: 6.0
  - S_moon_star_ton: 45,244.80
  - S_moon_min_ton: 155,692.80
  - mean_direct_arrivals: 117；mean_failures: 56；mean_launches: 54
  - mean_cost_usd: 8.0624e10
  - max_inventory_queue: 52；max_inventory_wait_days: 5.08；max_launch_wait_days: 6.65

> 备注：当前每个场景仅 1 条轨迹，std/分位不可得。请使用 `--n-mc ≥ 30` 重新仿真以获得稳健统计，并将均值/分位写回此文件和决策矩阵。
