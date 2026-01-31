# 2026 MCM Problem B: Problem 1 数据集需求分析指南

**适用题目**：Problem 1 (三种运输情景的成本与时间表计算)  
**文件用途**：辅助建立数学模型所需的数据清单与检索策略  
**当前状态**：第一阶段 (基础模型构建 - 完美条件假设)

---

## 1. 核心约束数据 (Hard Constraints)
*以下数据直接来源于题目原文，作为模型的固定参数或边界条件，不可更改。*

### A. 总体目标 (Project Goal)
* [cite_start]**任务总量**：1 亿公吨 (100 million metric tons) [cite: 11]。
* [cite_start]**起始时间**：2050 年 [cite: 10]。
* [cite_start]**目标人口**：100,000 人 (用于辅助验证物资消耗速率) [cite: 10]。

### B. 太空电梯系统 (Space Elevator System)
* [cite_start]**系统架构**：3 个银河港 (Galactic Harbours)，沿赤道每隔 120 度分布 [cite: 8]。
* [cite_start]**单港配置**：每个银河港包含 1 个地球港口 + 2 条 100,000 km 长的缆绳 + 2 个顶点锚 [cite: 9]。
* [cite_start]**运载能力**：银河港每年可运输 **179,000 公吨** [cite: 14]。
    * *建模提示*：需在论文中明确假设这 179,000 吨是指“单个银河港”还是“整个系统”的运力。考虑到总需求 1 亿吨，若为系统总运力则需 500+ 年，故建议假设为单港运力或需进一步论证。
* [cite_start]**运输路径**：地球港 -> 顶点锚 (第一步) -> 月球殖民地 (第二步，需火箭/飞船) [cite: 13]。
* [cite_start]**环境影响**：无大气污染 (No atmospheric pollution) [cite: 14]。
* [cite_start]**运行条件**：完美条件 (Perfect conditions)，即不考虑缆绳晃动或设备故障 [cite: 20]。

### C. 传统火箭系统 (Traditional Rockets)
* [cite_start]**运载能力**：单次发射有效载荷 **100 - 150 公吨** (基于先进的 Falcon Heavy) [cite: 19]。
* [cite_start]**发射基地**：现有 10 个发射场 (美国 5 个, 哈萨克斯坦, 法属圭亚那, 印度, 中国, 新西兰) [cite: 16]。
* [cite_start]**运行条件**：完美条件 (Perfect conditions)，即不考虑发射失败或天气延误 [cite: 20]。
* [cite_start]**运输路径**：地球发射场 -> 月球殖民地 (单步直达) [cite: 18]。

---

## 2. 需补充的外部数据 (External Data Requirements)
*以下数据题目未给出，但对构建成本 (Cost) 和时间表 (Timeline) 模型至关重要。需通过文献检索或合理估算获得。*

### A. 太空电梯专属数据
1.  **建设成本 (CAPEX)**:
    * 建造 3 个银河港及配套设施的固定资产投资是多少？
    * *参考方向*：ISEC (International Space Elevator Consortium) 报告、石墨烯材料造价估算。
2.  **运营成本 (OPEX)**:
    * 每公斤物资通过电梯运输到 GEO/顶点锚的电力与维护成本 ($/kg)。
3.  **运行速度与周期 (Time Variable)**:
    * 爬升器 (Climber) 的垂直速度是多少 (km/h)？这将决定单次运输的在途时间 (Transit Time)。
4.  **第二阶段运输成本 (Apex to Moon)**:
    * [cite_start]题目指出从顶点锚到月球仍需“火箭”或“飞船” [cite: 13]。
    * *关键缺失*：从 GEO/顶点锚到月球转移轨道的燃料消耗与成本 (通常远低于地面发射)。

### B. 传统火箭专属数据
1.  **未来发射成本 (Projected Launch Cost)**:
    * 2050 年 Falcon Heavy 级别的发射报价。需建立一个“技术进步导致的成本衰减模型”。
    * *参考方向*：SpaceX Starship 预期成本、航天经济学预测。
2.  **最大发射频率 (Launch Cadence)**:
    * 全球 10 个基地在极限状态下，每年最多能发射多少次？
    * *瓶颈分析*：发射台周转时间 (Turnaround Time)、燃料生产与加注能力。这是限制 Scenario B 时间表的核心变量。
3.  **火箭制造与翻新 (Manufacturing & Refurbishment)**:
    * 火箭复用次数上限及翻新成本。

### C. 综合物流参数
1.  **资金时间价值 (Time Value of Money)**:
    * 项目跨度可能长达数十年，是否引入折现率 (Discount Rate) 来计算净现值 (NPV)？
2.  **物资优先级 (Material Priority)**:
    * 是否所有 1 亿吨物资都具有相同的运输紧迫性？(虽然题目未明说，但在 Scenario C 组合优化中可作为权重)。

---

## 3. 推荐检索关键词 (Search Strategy)

| 数据类别 | 推荐关键词 (English Keywords) | 预期用途 |
| :--- | :--- | :--- |
| **电梯造价** | "Space Elevator estimated construction cost ISEC report", "Cost of graphene tether per km" | 计算 Scenario A 的总成本 |
| **电梯速度** | "Space Elevator climber speed limits", "7 days to GEO space elevator" | 计算 Scenario A 的物资到达延迟 |
| **轨道转移** | "Delta-v budget LEO to Moon", "Orbital Transfer Vehicle (OTV) cost per ton" | 计算电梯第二程 (锚点->月球) 成本 |
| **火箭成本** | "Falcon Heavy launch cost projection 2050", "Cost per kg to Moon surface SpaceX" | 计算 Scenario B 的单次发射成本 |
| **发射能力** | "Kennedy Space Center maximum launch frequency", "Global orbital launch capacity annual" | 设定 Scenario B 的时间表上限约束 |

---

## 4. 讲师提示 (Instructor's Note)

* **关于“完美条件”**：在 Problem 1 中，**不要**引入天气、事故率、维修停工等随机变量。这些是 Problem 2 的考点。第一问应聚焦于系统的**理论极限产能**。
* **关于“组合情景 (Scenario C)”**：这是优化的核心。通常火箭快但贵，电梯慢但便宜（或初期投入大后期便宜）。你的模型应寻找一个“拐点”或“混合比例”，例如：前期用火箭快速建立前哨站，后期用电梯大规模运输重型物资。

---
*文件生成时间：2026 MCM 备赛期间*