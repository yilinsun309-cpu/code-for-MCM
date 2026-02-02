# Task 4 环境影响脚本说明

本目录的 `Q4.py` 用于计算第四题的环境影响指标，参数默认取自论文中的 Task 4 表格与说明。

## 运行方式

```bash
python 代码/question4/Q4.py
```

默认情景为 C（混合），并使用论文默认参数。

## 常用参数

- `--scenario`：情景 A/B/C（或 1/2/3）
- `--total-mass`：总运量（ton）
- `--cap-rock`：单次发射有效载荷（ton）
- `--cap-se`：电梯年运力（ton/yr）
- `--elevator-towers`：电梯塔数量（默认 1）
- `--f-cycle`：轨道火箭年循环次数（cycles/yr）
- `--n-launch`：地面发射总次数（不填则按情景自动估算）
- `--project-years`：项目年限（用于把总发射数换成“年均”）
- `--alpha-climate`：`baseline` / `clean` / `ultra` 或数值
- `--grid-year`：`2020` / `2030` / `2050`
- `--grid-intensity`：手动覆盖电力碳强度（kg CO2/kWh）
- `--site-caps`：JSON 文件，覆盖各发射场基础上限
- `--launch-plan`：JSON 文件，指定各发射场年发射量

## 示例

1）纯电梯（情景 A）

```bash
python 代码/question4/Q4.py --scenario A --total-mass 1e8
```

2）纯火箭（情景 B），自动用 `ceil(M/Cap_rock)` 估算发射次数

```bash
python 代码/question4/Q4.py --scenario B --total-mass 1e8
```

3）混合方案（情景 C），手动给定发射次数

```bash
python 代码/question4/Q4.py --scenario C --total-mass 1e8 --n-launch 30000
```

4）使用自定义发射场上限与计划（JSON）

```bash
python 代码/question4/Q4.py --site-caps site_caps.json --launch-plan launch_plan.json
```

`site_caps.json` 示例：

```json
{
  "Florida": 2300,
  "California": 950,
  "Texas": 190
}
```

`launch_plan.json` 示例：

```json
{
  "Florida": 800,
  "California": 300,
  "Texas": 100
}
```

## 输出说明

脚本输出 JSON，包含：

- 火箭 CO2/CO2e、BC、NOx 等排放量
- 电梯能耗与 CO2
- 碳强度（CO2e/ton）
- 分发射场的年发射利用率与是否超出上限
- 分层指标：`strat_proxy_ton_fuel`（平流层强迫 proxy）

参数默认值都在 `Q4.py` 顶部的全局变量中，可直接修改。
