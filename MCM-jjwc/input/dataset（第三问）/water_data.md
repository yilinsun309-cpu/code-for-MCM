# Problem B：用水需求侧（Demand Side）参数（平衡：空间站 vs 地球）

> 你要求的“折中法”：把**空间站航天员用水量**与**地球居民用水量**取算术平均；回收率（recovery rate）也同样取平均。下面给出可直接进模型的数值与公式，并在末尾给出处。

---

## 1. 需求侧总框架（从“人均”到“总量”）

1.（1）人口与时间口径

* ① 常住人口：**100,000 人**（题面设定）
* ② 时间：**满负荷运行 1 年 = 365 天**（题面设定）
* ③ 水密度近似：**1 kg 水 ≈ 1 L ≈ 10^{-3} 吨**（工程近似，便于换算）

1.（2）关键定义（模型里建议显式区分）

* ① **总用水（Gross Demand）**：居民/系统每天“使用与周转”的水流量
* ② **回收率（Recovery Rate）**：用水回收系统把废水/冷凝水等重新变成可用水的比例
* ③ **净补给水（Net Make-up）**：外部必须补上的那部分水

  * (i) 基本近似：W_net ≈ W_gross × (1 − r)

---

## 2. 人均日总用水（Gross）——按“空间站 vs 地球”取平均

2.（1）两端基准值（权威来源）

* ① 空间站（ISS/ECLSS 口径）：

  * 每名航天员每日需要约 **1 gallon/day**（饮用、食物准备、基础卫生如刷牙等）
  * 换算：1 gallon ≈ **3.785 L/day**
* ② 地球（家庭/居民用水口径）：

  * 美国居民在家平均用水约 **82 gallons/person/day**
  * 换算：82 gallons ≈ **310.4 L/person/day**

2.（2）按你的要求取算术平均得到“折中人均日总用水”

* ① 定义：w_ISS = 1 gal/day，w_Earth = 82 gal/day
* ② 折中用水：

  * w_avg = (w_ISS + w_Earth)/2 = (1 + 82)/2 = **41.5 gal/day**
  * 换算：w_avg ≈ 41.5 × 3.785 ≈ **157.1 L/person/day**

> 说明：这一步只是在“总量层面”做折中；若你还想要分项（饮用/洗浴/洗衣…）以便写得更像工程模型，下面用 NASA BVAD 的**分项比例**来把 157.1 L/day 拆开。

---

## 3. 用水分项（End-Use Breakdown）——用 NASA BVAD 的分项结构做“比例拆分”

3.（1）做法（比例缩放）

* ① NASA BVAD 给出“成熟行星基地（Mature Planetary Base）”的人均日总用水：

  * w_BVAD_total = **9.12 kg/(人·天) ≈ 9.12 L/(人·天)**
* ② 为保持分项结构，但让总量满足你的折中值 w_avg：

  * 缩放系数 k = w_avg / w_BVAD_total = 157.1 / 9.12 ≈ **17.225**
  * 每个分项：w_i(avg) = k × w_i(BVAD)

3.（2）拆分后的折中分项（单位：L/(人·天)）

* ① 饮用水（Drinking）：2.00 × k ≈ **34.45**
* ② 食物复水（Food rehydration）：0.50 × k ≈ **8.61**
* ③ 尿冲（Urinal flush）：0.50 × k ≈ **8.61**
* ④ 个人清洁（Personal hygiene）：0.40 × k ≈ **6.89**
* ⑤ 淋浴（Shower）：1.08 × k ≈ **18.60**
* ⑥ 洗衣（Laundry）：1.10 × k ≈ **18.95**
* ⑦ 洗碗（Dish wash）：3.54 × k ≈ **60.98**
* ⑧ 合计：≈ **157.10 L/(人·天)**（与 w_avg 对齐）

> 注：(i) 这里“分项结构”来自 BVAD 的成熟基地假设；你用它只是为了给论文一个合理的工程拆分。总量仍然由“空间站 vs 地球”折中定义。

---

## 4. 回收率（Recovery Rate）——同样按“空间站 vs 地球”取平均

4.（1）两端基准值（权威来源）

* ① 空间站（ISS/ECLSS 实测里程碑）：总水回收率 r_ISS ≈ **0.98**（98%）
* ② 地球（市政污水的“再生水回用/回收”现状，按 WEF 统计口径）：

  * 美国市政污水中，作为再生水被回用（Recovered）的比例约 **6%**
  * 记作 r_Earth ≈ **0.06**

4.（2）按你的要求取算术平均得到折中回收率

* ① r_avg = (r_ISS + r_Earth)/2 = (0.98 + 0.06)/2 = **0.52**

> 说明：(i) 这里的 r_Earth 是“再生水回用占比”的统计口径，确实会比空间站闭环系统低很多；所以 r_avg=0.52 会让净补给水偏大（更保守）。如果你后面觉得补给压力过大，可在敏感性分析里把 r 提升到 0.7~0.9 作为技术进步情景。

---

## 5. 农业/生物再生用水（若基地有植物舱/水培）

5.（1）权威基线（NASA BVAD）

* ① 生物质生产用水强度（Biomass production water consumption）：

  * **4.00 kg/(m²·天) ≈ 4.00 L/(m²·天)**

5.（2）接入模型

* ① 设植物舱面积 A（m²）
* ② 农业端年总用水（gross）：W_gross_agri = 4.00 × A × 365
* ③ 农业端年净补给（net）：W_net_agri ≈ W_gross_agri × (1 − r_avg)

---

## 6. 最终可直接用的计算式（含数值示例）

6.（1）变量

* ① N = 100,000
* ② d = 365
* ③ 人均日总用水（折中）：w_avg = **157.1 L/(人·天)**
* ④ 回收率（折中）：r_avg = **0.52**

6.（2）公式

* ① 年总用水（生活端，gross）：W_gross_life = N × w_avg × d
* ② 年净补给水（生活端，net）：W_net_life ≈ W_gross_life × (1 − r_avg)

6.（3）数值结果（生活端）

* ① 年总用水（gross）：

  * W_gross_life ≈ 100000 × 157.1 × 365 ≈ **5.73×10^9 L/年 ≈ 5,734,000 吨/年**
* ② 年净补给水（net）：

  * (1 − r_avg) = 0.48
  * W_net_life ≈ 5,734,000 × 0.48 ≈ **2,752,000 吨/年**

---

## 引用（References）

1. NASA. *NASA Achieves Water Recovery Milestone on International Space Station* (Jun 20, 2023). 文中给出：总回收率达 98%，并说明“each crew member needs about a gallon of water per day…”。[https://www.nasa.gov/missions/station/iss-research/nasa-achieves-water-recovery-milestone-on-international-space-station/](https://www.nasa.gov/missions/station/iss-research/nasa-achieves-water-recovery-milestone-on-international-space-station/)
2. US EPA WaterSense. *Statistics and Facts*（页面给出：Each American uses an average of 82 gallons of water a day at home，并引用 USGS 2015 估计）。[https://www.epa.gov/watersense/statistics-and-facts](https://www.epa.gov/watersense/statistics-and-facts)
3. Water Environment Federation (WEF). *Preparation of Baseline Data to Establish the Current Amount of Resource Recovery* (Oct 2018). 报告中给出美国市政再生水回用占比约 6%（Recovered 6% / Not Recovered 94%）。[https://watereuse.org/wp-content/uploads/2018/10/WRRFBaselineDataFinalReportWEF.pdf](https://watereuse.org/wp-content/uploads/2018/10/WRRFBaselineDataFinalReportWEF.pdf)
4. NASA. *Life Support Baseline Values and Assumptions Document (BVAD), NASA/TP-2015-218570, Rev 2 (Feb 2022).* 用于分项结构与植物舱用水强度（如 Table 4-20、Biomass production water consumption）。[https://ntrs.nasa.gov/api/citations/20210024855/downloads/BVAD_2.15.22-final.pdf](https://ntrs.nasa.gov/api/citations/20210024855/downloads/BVAD_2.15.22-final.pdf)
