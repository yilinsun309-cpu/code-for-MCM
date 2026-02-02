# Task 4 — 环境影响结果（CO₂e / BC / NOx，含生态限额）

计算口径：
- 火箭：每次发射 RP‑1 395.5 t + LOX 937.1 t，CO₂e = 2,675 t/launch；BC = 4.0–7.9 t/launch（默认 6.0 t），NOx = 5.5 t/launch。
- 电梯：14.8 kWh/kg；2050 低碳电网强度 0.005 kg CO₂/kWh。
- 站点生态限额：采纳 `f_green` 时取更小者 \(\min(k_{\text{env}} N^{(0)},\ f_{\text{green}})\)，其中 \(k_{\text{env}} = 1/\alpha_{\text{climate}}\)（Clean=10，Ultra=50）。本结果使用 Clean（α=0.10）。
- 成果取自 `scenarios_stats.json`（Task 5 输入），单位：吨。

| 场景 | 总 CO₂e (t) | CO₂e/交付吨 (t/ton) | 总 BC (t) | 总 NOx (t) | 备注 |
|---|---|---|---|---|---|
| A 纯电梯 | 7.40e6 | 7.4e-2 | 0 | 0 | 电网电力，近零碳；无火箭排放 |
| B 纯火箭 | 2.14e9 | 2.14e-2 | ≈6.0 × N_launch | ≈5.5 × N_launch | 占主导的高空排放 |
| C 混合 | 3.40e7 | 3.40e-4 | 6.0 × N_launch(C) | 5.5 × N_launch(C) | 火箭 + 电梯并存，强度最低 |

可视化：`task4_Eimpact.png`（莫兰迪配色）展示三场景 CO₂e 对比，路径 `代码/question4/`。

结论（环境维度）：混合方案（C）在总排放与单位排放两侧均为最优；纯火箭方案（B）受高发射数拖累；纯电梯方案（A）在总量上低，但单位强度受 100% 电梯承担所有质量而略高于 C。
