# 2026 MCM B：太空电梯年度维护/运维成本（O&M）估算（结论版）

## 结论（可直接写进 Summary/Cost Assumptions）
- 题面最终系统：**3 个 Galactic Harbours**，每个 Harbour 有 **2 条 100,000 km tethers** ⇒ 总计 **6 条 tethers**。  
- 采用 **NIAC（NASA Institute for Advanced Concepts）公开材料**给出的空间电梯年度运维成本量级：**Operations cost < $100M/yr** 作为“单条 tether 对应一套电梯系统的年度 O&M（含维护 maintenance）”锚点。  
- 则题面系统年度 O&M（含维护）估算为：  
  - **基础区间（2002$ 量级）**：约 **$0.30–$0.60 B/yr**（对应每条 tether 50–100M/yr）  
  - **基准值（2002$ 量级）**：约 **$0.45 B/yr**（每条 tether 75M/yr）  
  - **考虑“不完美工况/故障”风险倍数** \(k_r\in[1.3,1.7]\)：约 **$0.585–$0.765 B/yr**（基准 × \(k_r\)）

## 数值表（单位：B$/yr，2002$ 量级）
| 假设 | 单条 tether 年O&M (M$/yr) | 风险倍数 \(k_r\) | 系统年O&M (B$/yr) |
|---|---:|---:|---:|
| 偏乐观 | 50 | 1.0 | 0.30 |
| **基准** | **75** | **1.0** | **0.45** |
| 保守上界 | 100 | 1.0 | 0.60 |
| 基准 + 轻度风险 | 75 | 1.3 | 0.585 |
| 基准 + 较差工况 | 75 | 1.7 | 0.765 |

## 可选：通胀换算到 2025 年 12 月美元（2025-12 $）
- BLS CPI-U：**2002 annual avg = 179.9**；**2025-12 = 324.054** ⇒ 通胀系数 \(\approx 324.054/179.9 \approx 1.80\)  
- 因此：
  - 基础区间：**$0.54–$1.08 B/yr（2025-12$）**
  - 基准值：**$0.81 B/yr（2025-12$）**
  - 基准 + 风险：**$1.05–$1.38 B/yr（2025-12$）**

## 引用与链接（权威出处）
- COMAP 2026 MCM Problem B（系统结构、tether 长度、年运力）：见题目 PDF。  
- NIAC（Edwards, “The Space Elevator”, Jun 2002）：给出 **Operations cost < $100M/yr**  
  - https://www.niac.usra.edu/files/library/meetings/annual/jun02/521Edwards.pdf
- BLS（U.S. Bureau of Labor Statistics）CPI-U：
  - 2002 annual average（历史表，含 2002=179.9）：https://www.bls.gov/cpi/tables/historical-cpi-u-201710.pdf  
  - Dec 2025 CPI 新闻稿（含 CPI-U=324.054）：https://www.bls.gov/news.release/pdf/cpi.pdf
