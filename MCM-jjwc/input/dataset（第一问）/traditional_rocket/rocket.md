# 2026 MCM Problem B: Traditional Rocket Data Analysis (Scenario B)

**适用题目**：Problem 1 (Scenario B: Traditional Rocket Launches)  
**文件用途**：提供真实世界数据基准，用于构建 2026-2050 年的技术演进模型  
**核心冲突**：题目假设 (Assumption) 与物理现实 (Physics Reality) 的差异分析

---

## 1. 未来发射成本模型 (Projected Launch Cost)
*目标：建立从 2026 年到 2050 年的成本衰减函数 $C(t)$。*

### A. 当前基准数据 (2025-2026 Baseline)
* **SpaceX Falcon Heavy (现役)**:
    * **可回收模式 (Reusable)**: 约 **$9,700 万美元/次** (仅回收侧助推器，中心级消耗)。
    * **全消耗模式 (Expendable)**: 约 **$1.5 亿美元/次** (为获得最大载荷)。
    * **单位成本 (LEO)**: 约 **$1,500 - $3,000 / kg**。
* **Starship (未来参考)**:
    * *注：虽然题目说用 "Advanced Falcon Heavy"，但这显然是指 Starship 级别的经济性。*
    * **目标成本**: 完全复用下，每次发射 **$200万 - $1,000 万美元**。
    * **目标单位成本**: **$10 - $20 / kg**。

### B. 2050 年预测模型 (Modeling for 2050)
* **建议设定**: 不要直接使用 Starship 的最低值，保留一定冗余。
* **推荐单次发射成本**: **$1,000 万 - $3,000 万美元** (基于 2026 年币值)。
* **成本衰减公式 (Wright's Law)**:
    * 航空航天领域的经验法则：产量每翻一番，单位成本下降约 15%-20%。
    * 推荐模型：
      $$Cost(t) = C_{2026} \times e^{-k(t-2026)}$$
      *(建议 $k$ 取值 0.05 - 0.10)*
模型出处
Wright, T. P. (1936). Factors Affecting the Cost of Airplanes. Journal of the Aeronautical Sciences, 3, 122–128. https://doi.org/10.2514/8.155
---

## 2. 最大发射频率与基础设施瓶颈 (Launch Cadence & Constraints)
*目标：确定 Scenario B 的时间表上限 (Timeline Cap)。*

### A. 单发射台极限 (Pad Turnaround)
* **现实瓶颈**:
    * **Falcon 9**: 最快周转记录 **9 天**。
    * **Kennedy Space Center (LC-39A)**: 目前唯一能发射 Falcon Heavy 的发射台，年极限约 **60 次**。
    * **Falcon Heavy 复杂性**: 需要 3 个核心并联，整备时间远长于单核火箭。
* **2050 年假设**: 需假设实现了类似航空业的“快速周转”，单台发射间隔缩短至 **3-5 天**。

### B. 全球基地真实能力 (Global Reality Check)
题目给出的 10 个基地中，绝大多数在现实中**无法支持重型火箭**：
* **Mahia, New Zealand**: 仅能发射小型电子号 (Electron, ~300kg)，无法承受重型火箭声学冲击。
* **Taiyuan, China**: 内陆基地，落区为人口稠密区，通常仅发射中型火箭，年均 10-15 次。
* **Wallops, USA**: 主要发射 Antares，年容量约 12 次。

> **建模关键点**: 必须在模型中计算**基础设施升级成本 (Infrastructure CAPEX)**。若要这 10 个基地全部达到 KSC 的标准，需投入数千亿美元进行扩建。

---

## 3. 制造与翻新 (Manufacturing & Refurbishment)
*目标：计算长期运营的可持续性与供应链压力。*

### A. 复用次数 (Reusability Limit)
* **现实数据**:
    * Falcon 9 助推器: 单枚最高复用 **20+ 次**。
    * Falcon Heavy 中心核: 承受应力极大，历史上从未高频复用。
* **2050 年设定**: 假设材料学突破，寿命可达 **100 次** 以上 (类似 Starship 设计目标)。

### B. 翻新成本 (Refurbishment Cost)
* **现实数据**: 助推器翻新约 $25 万美元；整流罩制造约 $600 万美元 (回收可节省)。
* **不可回收部分**: 现役 Falcon Heavy 的**第二级 (Second Stage)** 是 100% 消耗品。
* **建模建议**: 必须假设 2050 年的 "Advanced Falcon Heavy" 变成了**完全可回收 (Fully Reusable)**，否则第二级的制造成本将导致总预算破产。

---

## 4. 关键物理陷阱 (The Physics Trap)
*这是本题最大的“坑”，需要在论文中显式讨论。*

| 参数 | 题目假设 (Problem Statement) | 物理现实 (Physics Reality) | 处理策略 |
| :--- | :--- | :--- | :--- |
| **单次运载量 (Payload to Moon)** | **100 - 150 公吨** | **~15 - 20 公吨** (TLI Limit) | **必须使用题目假设 (150t)**。<br>但在 "模型评价" 中指出：这相当于假设该火箭性能达到了 SpaceX Starship V3 的水平，而非现役 Falcon Heavy。 |
| **环境影响** | "Advanced Falcon Heavy" | 煤油 (RP-1) 燃烧产生黑碳 (Soot) | 需在 Problem 4 中讨论黑碳对平流层的累积影响。 |

---

## 5. 总结：您的模型输入数据表 (Data Input Table)

| 参数 (Parameter) | 2026 现实值 (Real World) | 2050 模型推荐设定 (Model Input) | 备注 |
| :--- | :--- | :--- | :--- |
| **单次发射成本** | ~$1.5 亿 (Expendable) | **$1,500万 (平均)** | 假设技术完全成熟 |
| **单次运载量** | ~20 吨 (TLI) | **125 吨 (取平均)** | **严格遵循题目** |
| **发射台周转** | 60+ 天 (FH) | **3 天** | 假设极高效率 |
| **复用寿命** | <20 次 | **100 次** | 材料学进步 |
| **可用基地数** | 1 (仅 KSC) | **10 (全部升级)** | 需计算升级成本 |
| **燃料类型** | RP-1 (Kerosene) | **Methalox (甲烷)** | 建议假设改为甲烷机以减少积碳和复用成本 |

---

### 讲师建议 (Instructor's Note)
在撰写论文时，不要只是列出数据。要用一段话描述**“从 2026 年的现实到 2050 年的题目假设之间发生了什么”**。
例如：“我们要实现题目所说的 150 吨月球运载量和 10 个基地的发射频率，意味着全球航天工业必须经历一场类似从‘螺旋桨飞机’到‘喷气式客机’的技术革命。” 这样的定性分析会增加论文的深度。


# 从离地 10 万公里处到月球：大概需要多久？

## 结论（可直接引用）
从“地球地面上方 100,000 km（10 万公里）”出发到月球附近（按到月球表面粗算），通常仍需要 **约 2 天左右**；常见范围大约 **1.5–3 天**（取决于轨道设计与能量/速度方案，如 Trans-Lunar Injection, TLI）。

> 与 NASA 的说法一致：到月球一般是“几天（several days）”。

---

## 估算过程（便于核算）
**1）剩余路程（按到月球表面粗算）**
- 地月平均距离（地心到月心）：约 384,400 km
- 地球半径：约 6,371 km
- 出发点离地心距离：6,371 + 100,000 = 106,371 km
- 若刚好朝月球方向：到月心剩余距离 ≈ 384,400 − 106,371 = 278,029 km
- 月球半径：约 1,737 km  
→ 到月球表面剩余距离 ≈ 278,029 − 1,737 ≈ **276,000 km**

**2）飞行时间（用“典型平均速度”粗算）**
去月球通常是一次主要加速后长时间滑行（coast），所以可用一个“平均速度”做数量级估算：
- 若平均速度取 **1.5 km/s**（常见“几天到月球”的量级）  
  时间 ≈ 276,000 / 1.5 = 184,000 s ≈ 51.1 小时 ≈ **2.1 天**
- 若平均速度在 **1.0–2.0 km/s**（更慢更省 / 更快更激进）  
  时间范围 ≈ 276,000/2.0 到 276,000/1.0  
  ≈ 38.3–76.7 小时 ≈ **1.6–3.2 天**

---

## 出处（权威）
- NASA（2025-02-19）：*How Long Does it Take to Get to the Moon… Mars… Jupiter? We Asked a NASA Expert: Episode 51*  
  链接：https://www.nasa.gov/directorates/smd/how-long-does-it-take-to-get-to-the-moon-mars-jupiter-we-asked-a-nasa-expert-episode-51/  
  其中给出的结论：“To get to the Moon takes several days.”
