# 扰动模拟脚本说明

脚本: `perturbation_sim.py`

用途
- 将缆索摆动、火箭故障、电梯损坏转为有效运力扰动
- 进行蒙特卡洛模拟，输出工期与成本统计

快速使用
- `python perturbation_sim.py --trials 5000 --seed 42`
- `python perturbation_sim.py --dump-config > config.json`
- `python perturbation_sim.py --config config.json --se-share 0.6 --output ../output/perturbation_trials.csv`

关键参数
- `--trials`: 模拟次数
- `--seed`: 随机种子
- `--se-share`: M_goal 中分配给电梯的比例
- `--m-se`: 直接指定电梯质量(优先于 se-share)
- `--output`: 输出逐次样本 CSV

配置字段概览
- `base`: 基础参数(单位与论文一致)
- `uncertainty.oscillation`: 摆动折减
- `uncertainty.rocket`: 故障概率与停飞
- `uncertainty.elevator`: 机械可用度与损坏
