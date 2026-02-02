# Task4 环境输入所需的 Task2/3 结果汇总

> 说明：先填入当前已跑出的场景 C（Q2 默认 scenario=3）结果，场景 A/B 需跑完 Task2/Task3 后再补。所有指标均为成本型（越小越好），单位以括号注明。

## 场景 C（Task2 DES，runs=1，max_time=250y）
- 来源：`代码/results/task2/summary.json` 与 `runs.csv`
- 主要指标：
  - 完工时间 T* (year): **189.2082**
  - 失效次数 mean_failures: **9931**
  - 替补发射 mean_launches: **9928**
  - 替换成本 mean_replace_cost (USD): **1.4892e11**
  - 最大缺口 max_deficit: **11**
  - 下行比 down_ratio: **0.0134**
- 说明：仅 1 条样本，std_T=0，需后续用 MC≥30 重新跑以获得稳健统计。

## 场景 B（待补）
- 需要：Task2 设 `--scenario 2 --n-mc 30+ --max-time 250`，导出 summary.json / runs.csv。
- 填表后指标项与场景 C 对齐。

## 场景 A（待补）
- 需要：Task2 设 `--scenario 1 --n-mc 30+ --max-time 250`，导出 summary.json / runs.csv。
- 填表后指标项与场景 C 对齐。

## 后续动作
1) 运行 Task3（供水年）生成各场景的 S_moon*、max_gap、arrivals、failures 等，存入 `代码/results/task3/`，便于 Q5 读取。
2) 将 A/B/C 三场景的 Task2/3 结果汇总成 JSON，作为 Q5 决策矩阵输入。
