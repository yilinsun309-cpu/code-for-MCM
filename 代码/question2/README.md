# Task 2 可靠性仿真说明

本目录的 `Q2.py` 实现了论文 Task 2 的非理想条件可靠性模型，包括：吸收态故障、事件驱动 DES、Apex 库存耦合、替换延迟与发射节拍约束、以及蒙特卡洛统计输出。

## 运行方式

```bash
python 代码/question2/Q2.py --n-mc 50
```

可选参数：

- `--scenario`：选择情景 1/2/3（默认 3）
- `--n-mc`：蒙特卡洛运行次数
- `--seed`：随机种子
- `--config`：可选 JSON 配置（如需覆盖默认参数）
- `--verbose`：开启事件级进度日志
- `--log-every`：事件级日志输出频率（默认 10000）
- `--mc-log-every`：蒙特卡洛运行级日志频率（默认每次输出）

## 参数配置位置

默认参数集中在 `Q2.py` 顶部全局常量区（Global Defaults）。你可直接修改这些常量：

- `DEFAULT_SCENARIO`：情景编号
- `DEFAULT_M_GOAL`：总需求质量（ton）
- `DEFAULT_CAP_SE`：电梯年运力（ton/yr）
- `DEFAULT_CAP_ROCK`：单次运载（ton）
- `DEFAULT_F_TOTAL`：年发射频次（launches/yr）
- `DEFAULT_TAU_DAYS`：程序 1~5 的名义持续时间（天）
- `DEFAULT_DELTA_TAU_DAYS`：鲁棒缓冲（天）
- `DEFAULT_P_FAIL`：程序 1~5 的吸收态失败概率
- `DEFAULT_FAIL_COST`：程序 1~5 的单次失败成本（单位自定）
- `DEFAULT_C_LAUNCH`：单次替换发射成本（单位自定）
- `DEFAULT_I_SAFE`：安全机队规模
- `DEFAULT_DELTA_REPLACEMENT_DAYS`：替换延迟（天）
- `DEFAULT_DOWN_RATIO`：电梯可用率折减区间（如 `(0.0, 0.1)`）
- `DEFAULT_INITIAL_ROCKETS`：初始火箭数（None 表示与 `I_safe` 一致）
- `DEFAULT_MAX_TIME_YEARS`：最大仿真时间（年）
- `DEFAULT_SEED`：随机种子

时间单位统一为“年”。若使用天为单位的输入，脚本会统一换算。

## 输出说明

程序输出为 JSON 摘要，包括：

- `mean_T`：完成时间均值
- `std_T`：标准差
- `ci95_T`：95% 置信区间
- `mean_failures`：平均失效次数
- `mean_launches`：平均替换发射次数
- `mean_fail_cost`：平均失败成本
- `mean_fail_loss_cost`：平均失败损失成本（按程序）
- `mean_replace_cost`：平均替换发射成本
- `max_deficit`：最大机队缺口

若全部样本未完成，会提示 `completed_runs = 0`。

## 模型实现要点

- 吸收态故障：任一程序发生失效即进入状态 6 且永久退出。
- DES 调度：事件队列驱动，交付完成时计入质量。
- Apex 库存：仅在 Scenario 1 与 Scenario 3 的 4→3 负载阶段消耗库存。
- 替换机制：不足 `I_safe` 则触发延迟替换，受 `f_total` 发射节拍约束。
