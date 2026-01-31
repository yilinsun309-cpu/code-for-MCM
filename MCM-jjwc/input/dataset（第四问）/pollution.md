# Task 4 环境影响：需要搜集的数据条目（已尽量填入权威数值）

> 目标：在三种运输情景（电梯 alone / 火箭 alone / 混合）下，把“环境代价”量化进你的成本-工期模型，并能做“最小环境影响”的调整。

---

## 0. 统一的环境指标口径（你模型的输出）

* **0.1 温室气体（GHG, CO2e）**

  * 输出：(E_{CO2e})（t CO2e）
  * 需要：

    * 电力排放系数 (EF_{grid})（kg CO2/kWh）
    * 火箭发射的 CO2 / CO2e（t/launch）
    * （可选）制造阶段材料的“单位质量碳足迹”（kg CO2e/kg material）

* **0.2 大气污染物（局地空气质量）**

  * 输出：(E_{NOx}, E_{CO}, E_{PM/BC}, E_{VOC}) 等（kg 或 t）
  * 需要：污染物“排放因子”（emission index, g/kg fuel）或“每次发射排放量”（t/launch）

* **0.3 噪声 / 冲击波（Noise / Sonic boom）**

  * 输出：是否触及显著影响阈值（如 DNL 65 dB）及相关等值线范围

* **0.4 生态与地表影响（land/wildlife/水体）**

  * 输出：占地/敏感区重叠、废水/残留燃料、交通与船舶/直升机活动等（一般做定性+少量关键量化）

---

## 1. 情景 B：传统火箭（Rockets alone）——需要的数据与已填数值

* **1.1 推进剂类型（决定排放因子）**

  * 数据：Falcon 系列一子级采用 **液氧 LOX + 高度精炼煤油 RP-1（kerosene）**
  * 来源：FAA《SpaceX Falcon Program Final EA and FONSI》（对 Falcon 9 Block 1 说明其推进剂为 LOX 与 RP-1）

* **1.2 单次发射推进剂用量（决定“每次发射排放量”的上限）**

  * **Falcon Heavy（示例：用于“先进 Falcon Heavy”代表性假设）**

    * 一子级：LOX = 1,898,000 lb；RP-1 = 807,000 lb
    * 二子级：LOX = 168,000 lb；RP-1 = 64,950 lb
    * 换算（1 lb = 0.453592 kg）：

      * RP-1 总量 (\approx 395.51,t)
      * LOX 总量 (\approx 937.12,t)
  * 来源：FAA《SpaceX Falcon Program Final EA and FONSI》技术参数表（Falcon Heavy Propellant Quantity by stage）

* **1.3 RP-1 的 CO2 排放系数（Combustion CO2 factor）**

  * 数据：IPCC 默认系数：Jet kerosene 的

    * CO2 排放因子：71,500 kg CO2/TJ
    * 低位发热量（NCV）：44.1 TJ/Gg
  * 推得：(EF_{CO2,RP1}\approx 3.153,\text{kg CO2}/\text{kg fuel})
  * 来源：IPCC 2006 Guidelines（V2 Ch2 的默认 CO2 因子；V2 Ch1 的默认 NCV）

* **1.4 火箭排放因子：黑碳/氮氧化物（BC / NOx emission index）**

  * **黑碳（Black Carbon, BC）**

    * 数据：煤油火箭发动机的 BC 排放因子（EI）：**10–40 g BC / kg fuel**（文献给出范围）
    * 用途：(E_{BC}=EI_{BC}\times m_{fuel})
    * 若以 Falcon Heavy 的 RP-1 (\approx 395.5,t)：(E_{BC}\approx 4.0–15.8,t)（按 10–40 g/kg 估算）
    * 来源：Ross et al.（2014）关于火箭发动机排放与辐射强迫（给出煤油火箭 BC EI 范围）
  * **氮氧化物（NOx）**

    * 数据：煤油/固体混合类火箭排放因子：**NOx ≈ 14 g/kg fuel**（作为工程量级估计）
    * 用途：(E_{NOx}=EI_{NOx}\times m_{fuel})
    * 若以 Falcon Heavy 的 RP-1 (\approx 395.5,t)：(E_{NOx}\approx 5.54,t)（按 14 g/kg 估算）
    * 来源：Ryan et al.（2022）对火箭排放因子进行汇总的综述论文（表格给出 NOx / BC 等）

* **1.5 “每次发射”的 GHG（CO2 / CO2e）直接数据（优先用于报告）**

  * 数据（FAA 评估给出的年度总量，可折算到每次发射）：

    * 60 次 Falcon 9：CO2 = 23,226 t/年  → **≈ 387 t CO2/launch**
    * 10 次 Falcon Heavy：CO2 = 11,613 t/年 → **≈ 1,161 t CO2/launch**
    * 10 次 Falcon Heavy：CO2e = 26,747 t/年 → **≈ 2,675 t CO2e/launch**
  * 用途：直接形成你模型中火箭方案的 (E_{CO2}) 或 (E_{CO2e}) 约束/目标
  * 来源：FAA《Final EA》温室气体排放汇总表（CO2 与 CO2e）

* **1.6 噪声与冲击波阈值（用于“局地环境影响”对比）**

  * 数据（显著影响阈值）：若噪声敏感区 **DNL ≥ 65 dB** 且增量 **≥ 1.5 dB**，可判为显著影响
  * 数据（对比结论）：Falcon Heavy 在 LC-39A 的噪声暴露一般比 Falcon 9 **高 4–5 dB**；LAmax 70–110 dB 等值线用于表征单次事件最大声级
  * 来源：FAA《Final EA》噪声章节（DNL 65 dB 规则、LAmax/SEL 等值线描述）

---

## 2. 情景 A：太空电梯（Space Elevator alone）——需要的数据与已填数值

* **2.1 运行阶段：单位质量提升能耗（核心）**

  * 数据：把 1 kg 质量提升到 GEO 所需能量约 **14.8 kWh/kg**（给出量级参考）
  * 用途：(E_{elec}=m_{lift}\times e_{kWh/kg}/\eta)

    * (\eta)：系统总效率（激光/微波→电能→驱动→机械），建议作为敏感性参数（例如 0.3–0.8）
  * 来源：NASA/CP-2000-210429《Space Elevators: An Advanced Earth-Space Infrastructure for the New Millennium》（文中给出 14.8 kWh/kg 到 GEO 的量级）

* **2.2 电力排放系数（grid carbon intensity）**

  * 数据（IEA “Net Zero by 2050” 路线图：CO2 intensity of electricity generation）：

    * 2020：0.468 kg CO2/kWh
    * 2030：0.138 kg CO2/kWh
    * 2050：-0.005 kg CO2/kWh（≈ 接近 0；代表净零/净负排）
  * 用途：(E_{CO2,elec}=E_{elec}\times EF_{grid})
  * 来源：IEA《Net Zero by 2050》附录表（CO2 intensity of electricity generation）

* **2.3 建造阶段：关键材料“单位碳足迹”（用于把建造影响摊到 2050 起的运输期）**

  * **2.3.1 石墨烯/类石墨烯材料（Graphene materials）**

    * 数据（文献示例，差异极大，建议做区间敏感性）：

      * Hummers 法：**4841 kg CO2e / kg graphene**
      * 生物质废弃物（PWW）路线：**115.86 kg CO2e / kg graphene**
    * 用途：(E_{CO2e,mat}=m_{graphene}\times EF_{graphene})
    * 来源：Bahmei et al.（2025, Journal of Cleaner Production）摘要给出 GWP 数值
  * **2.3.2 碳纤维（Carbon fiber, 作为“碳基高强材料”对照）**

    * 数据（生产规模 3000 TPY）：

      * 常规工艺：24.83 kg CO2e/kg
      * 改进工艺：19.29 kg CO2e/kg
    * 用途：当你在报告里需要“对照材料”或“替代材料情景”时，用于量级比较
    * 来源：Kawajiri et al.（2022, Materials Today Sustainability）摘要给出数值

* **2.4 地面港口（Earth Port）与能量传输的生态安全参数（通常做约束/定性）**

  * 需要搜集的数据条目（建议先列为参数，缺数据可在附录说明）：

    * 激光/微波束功率密度阈值、禁飞区半径、对鸟类/航线影响
    * 地面站与储能系统占地（km²）与选址敏感区重叠（保护区/居民区）

---

## 3. 情景 C：混合（你的“情景三”）——需要的数据条目（用于“减少重复地面发射”带来的环境收益）

* **3.1 减少的地面发射次数 (\Delta N_{launch})**

  * 数据：由你的优化结果产生（不需要外部资料）
  * 用途：火箭相关排放（CO2/CO2e、NOx、BC、噪声）几乎都可按 (\Delta N_{launch}) 线性缩放

* **3.2 顶端锚处（apex anchor）到月球往返的推进剂消耗/排放**

  * 需要搜集的数据条目（目前你方案里用了“6 天往返”）：

    * 顶端锚到月球的典型转移时间（days）与对应 (\Delta v)（km/s）
    * 运输飞行器发动机 Isp（s）与推进剂类型（决定排放因子）
  * 备注：这部分决定“留在顶端循环的 70 枚火箭”到底还要烧多少推进剂，从而决定混合方案的真实环境优势

---

## 4. 你可以直接写进论文的“最小环境影响”调整方向（对应数据依赖）

* **4.1 目标函数加入环境项（建议的最简形式）**

  * (\min ; C + \lambda_1,T + \lambda_2,E_{CO2e} + \lambda_3,E_{BC} + \lambda_4,E_{NOx})
  * 其中 (\lambda) 可用“碳价（$/tCO2）”“健康损失（$/t NOx）”“政策权重”等做情景分析

* **4.2 电梯优先用低碳电（关键靠 (EF_{grid})）**

  * 若 2050 接近净零电力（IEA NZE），电梯运行阶段 CO2 近乎为 0，优势会非常明显

* **4.3 尽量用电梯替代地面发射（关键靠 (CO2e/launch)）**

  * 把“每次发射 CO2e”当作强惩罚项，优化会自然倾向减少地面发射次数

---

## 参考文献（用于你论文 References）

1. FAA. *SpaceX Falcon Program Final Environmental Assessment and Finding of No Significant Impact (Final EA and FONSI).* （包含：推进剂类型、Falcon Heavy 分级推进剂用量、CO2/CO2e 汇总、噪声阈值与对比结论等）
2. IPCC. *2006 IPCC Guidelines for National Greenhouse Gas Inventories, Volume 2: Energy.* （Jet kerosene 默认 CO2 排放因子与 NCV）
3. Smitherman Jr., D. V. (NASA). *Space Elevators: An Advanced Earth-Space Infrastructure for the New Millennium* (NASA/CP-2000-210429). （到 GEO 的能量量级：14.8 kWh/kg）
4. IEA. *Net Zero by 2050: A Roadmap for the Global Energy Sector.* （电力碳强度：kg CO2/kWh，含 2030/2050 指标）
5. Ross, M. T., & Sheaffer, P. M. (2014). *Radiative forcing caused by rocket engine emissions.* Earth’s Future. （煤油火箭黑碳排放因子范围与气候效应讨论）
6. Ryan, R. G., et al. (2022). *Impact of Rocket Launch and Space Debris Air Pollutant Emissions on Stratospheric Ozone and Climate.* （火箭排放因子综述表：NOx/BC 等）
7. Bahmei, F., et al. (2025). *Comparison of environmental impacts in the production of graphene from biomass waste and the Hummers' method.* Journal of Cleaner Production. （Graphene 生产 GWP：4841 vs 115.86 kg CO2e/kg 示例）
8. Kawajiri, K., et al. (2022). *Environmental impact of carbon fibers fabricated by an innovative manufacturing process on life cycle greenhouse gas emissions.* Materials Today Sustainability. （Carbon fiber 单位碳足迹：24.83 vs 19.29 kg CO2e/kg）
