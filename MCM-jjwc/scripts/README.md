# 扰动模拟脚本说明

脚本: `perturbation_sim.py`

用途
- 将缆索摆动、火箭故障、电梯损坏转为有效运力扰动
- 进行蒙特卡洛模拟，输出工期与成本统计

快速使用
- `python perturbation_sim.py --trials 5000 --seed 42`
- `python perturbation_sim.py --no-fault --trials 1`
- `python perturbation_sim.py --dump-config > config.json`
- `python perturbation_sim.py --config config.json --se-share 0.6 --output ../output/perturbation_trials.csv`

关键参数
- `--trials`: 模拟次数
- `--seed`: 随机种子
- `--se-share`: M_goal 中分配给电梯的比例
- `--m-se`: 直接指定电梯质量(优先于 se-share)
- `--output`: 输出逐次样本 CSV
- `--no-fault`: 无故障模式(摆动/故障/损坏均视为 0)

配置字段概览
- `base`: 基础参数(单位与论文一致)
- `uncertainty.oscillation`: 摆动折减
- `uncertainty.rocket`: 故障概率与停飞
- `uncertainty.elevator`: 机械可用度与损坏

输出说明
- 控制台 JSON
  - `trials`: 模拟次数
  - `infeasible`: 不可行次数(有效运力为 0 或节奏为 0 造成工期无穷)
  - `T_mean`/`T_p50`/`T_p90`: 总工期的均值/中位数/90 分位(年)
  - `cost_mean`/`cost_p50`/`cost_p90`: 总成本的均值/中位数/90 分位(USD)
  - `N_rock_mean`/`N_rock_p50`/`N_rock_p90`: 发射次数的均值/中位数/90 分位(次)
- CSV 每行字段
  - `T`: 单次模拟总工期(年)
  - `cost`: 单次模拟总成本(USD)
  - `N_rock`: 单次模拟发射次数(次)
  - `f_osc`: 摆动折减因子
  - `f_dmg`: 损坏折减因子
  - `A_mech`: 电梯机械可用度
  - `A_rocket`: 火箭可用度(含停飞折减)
  - `M_rocket_target`: 分配给火箭的目标质量(吨)
