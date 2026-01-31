# Problem B：用水需求侧（Demand Side）参数（已填入权威机构数据）

> 目标：把“居民总用水（gross demand）→ 回收（recovery）→ 需要补给的净水量（net make‑up）”这条链条的数据填齐，供第 3 题直接建模。

---

## 1. 需求侧总框架（从“人均”到“总量”）

1.（1）人口与时间口径

* ① 常住人口：**100,000 人**（题面设定）
* ② 时间：**满负荷运行 1 年 = 365 天**（题面设定）
* ③ 水密度近似：**1 kg 水 ≈ 1 L**（工程近似，常用）

1.（2）把“用水”拆成三条主支路

* ① 生活用水（Crew/Resident Use）：饮用、食物复水、个人清洁、冲厕等
* ② 运营/科研/工程用水（Payload / Ops Use）：实验、设备清洗、维护等（架构相关，需做参数化）
* ③ 农业/生物再生用水（Biomass / Plant Growth Use）：若基地部分食物自给，则需要营养液/灌溉用水

1.（3）关键定义（模型里建议显式区分）

* ① **总用水（Gross Demand）**：居民“用掉/周转”的水流量（不等于要从地球补给）
* ② **回收率（Recovery Rate）**：回收系统把废水/冷凝水等重新变成可用水的比例
* ③ **净补给水（Net Make‑up）**：外部必须补上的那部分水（= 总用水 × (1 − 回收率) + 其它不可回收损失）

---

## 2. 人均日用水（权威来源给出“基线/标准值”）

2.（1）NASA BVAD 给出的“成熟行星基地（Mature Planetary Base）”稳态用水分解（单位：kg/(人·天)）

> 来源：NASA/TP《Life Support Baseline Values and Assumptions Document (BVAD)》Rev2 (Feb 2022)，Table 4‑20。这里“成熟行星基地”明确假设 **具备完整卫生用水能力，并有生物质生产舱**。

* ① 饮用水（Drinking water）：**2.00**
* ② 食物复水（Food rehydration water）：**0.50**
* ③ 人体消耗合计（Total human consumption）：**2.50**
* ④ 冲厕/尿冲（Urinal flush）：**0.50**
* ⑤ 个人清洁（Personal hygiene，含口腔等）：**0.40**
* ⑥ 淋浴（Shower）：**1.08**

  * (i) BVAD 注释：ISS 本身没有淋浴；该值来自地面类比研究的估计
* ⑦ 洗衣（Laundry）：**1.10**
* ⑧ 洗碗/餐具清洗（Dish wash）：**3.54**
* ⑨ 卫生用水合计（Total hygiene）：**6.62**
* ⑩ 总用水（Total water consumption，不含农业与医疗应急）：**9.12**
* ⑪ 医疗/应急用水（Medical water）：**0.5 kg/(人·天) + 每次事件 5 kg**（见 BVAD 表 4‑20 的“Medical water”行）
* ⑫ 运营/工程/科研用水（Payload）：**TBD（架构相关）**（BVAD 表中明确标注 TBD/architecture dependent）

2.（2）NASA 人因标准（NASA‑STD‑3001）给出的“饮用水最低保障”

* ① 饮用水最低配给：**≥ 2.0 kg/(人·天)**（用于保持水合状态）
* ② 眼部冲洗：**≥ 0.5 kg**（粉尘/异物等颗粒事件）
* ③ 医疗事件：**每次事件 ≥ 5 kg**（化学暴露/灼伤等）
* ④ EVA 额外饮水：**额外 240 mL/小时**（在舱外活动期间，叠加在日常配给之上）

2.（3）NASA 在 ISS 上的“真实量级提醒”（把模型与现实对齐）

* ① NASA 指出：**每名航天员每天大约需要 1 加仑（~3.8 L）水**，覆盖饮用、食物准备与基础卫生（brushing teeth 等）

  * (i) 注意：这是 ISS 的“现实用水量级”，而 BVAD 的“成熟基地”包含更完整的卫生能力，因此两者可以用来做**低/高两端情景**。

---

## 3. 废水产生结构（决定“能回收多少”）

3.（1）NASA BVAD 给出的“成熟行星基地”稳态废水产生（单位：kg/(人·天)，Table 4‑21）

* ① 尿液（Urine）：**1.50**
* ② 尿冲（Urinal flush）：**0.50**
* ③ 尿液侧废水合计（Total urine wastewater load）：**2.00**
* ④ 卫生废水合计（Total hygiene wastewater load）：**10.17+**（“+”表示有些分项仍为 TBD 或与架构有关）
* ⑤ 舱内湿度冷凝水（Crew latent humidity condensate）：**2.90**（呼吸与出汗带来的水汽回收）
* ⑥ 总废水负荷（Total wastewater load）：**15.07+**

3.（2）为什么要把“冷凝水”单列

* ① NASA 在 ISS 的水回收系统中，**湿度冷凝水**是重要来源之一（呼吸/汗液 → 水汽 → 冷凝 → 回收）
* ② 对大规模基地（10 万人）来说，这条支路往往贡献稳定、连续的回收水流量（利于系统稳态设计）

---

## 4. 回收率（Recovery Rate）——权威机构给出的“可达到的闭环水平”

4.（1）NASA（ISS）实测与目标：总回收率可达 98%

* ① NASA 指出：探索任务理想状态需要 **接近 98%** 的水回收
* ② ISS 的 ECLSS 水系统通过 Brine Processor Assembly（BPA）演示：

  * (i) **BPA 之前**：总回收率约 **93–94%**
  * (ii) **加入 BPA 后**：总回收率达到 **98%**
* ③ NASA 的直观解释：收集 100 磅水，损失约 2 磅，其余持续循环

4.（2）把回收率放进模型的建议写法

* ① 设回收率 r（例如 r = 0.98 或 r = 0.94）
* ② **净补给水 = 总用水 × (1 − r) + 其它不可回收损失项**

  * (i) 若你暂时拿不到“其它损失项”的权威值，可先并入 (1 − r) 的“等效损失”，用灵敏度分析兜底

---

## 5. 农业/生物再生用水（若基地有食物自给）

5.（1）NASA BVAD 给出的生物质生产用水强度

* ① 生物质生产用水（Biomass production water consumption）：**4.00 kg/(m²·天)**（成熟基地情景）

  * (i) 这通常可视为“给植物的营养液/灌溉水”的周转量级；实际能否回收取决于你是否把植物蒸腾水汽也纳入冷凝回收链条

5.（2）如何把它接入第 3 题

* ① 设植物舱面积 A (m²)
* ② 农业用水（gross）≈ **4.00 × A** (kg/天)
* ③ 若假设蒸腾水汽也被冷凝系统捕获，则农业用水的“净补给”同样乘以 (1 − r)

---

## 6. 直接可用的“净补给水”计算模板（把数据填进去即可）

6.（1）变量定义

* ① N：人口（= 100,000）
* ② d：天数（= 365）
* ③ w_person：人均总用水（kg/(人·天)）

  * (i) 高配（成熟基地）：w_person = **9.12**（BVAD Table 4‑20）
  * (ii) 低配（ISS 量级）：w_person ≈ **3.8**（NASA “~1 gallon/day”）
* ④ r：总回收率（0.94 ~ 0.98，NASA ISS 实测区间）
* ⑤ A：植物舱面积（m²，若有农业）

6.（2）公式

* ① 年总用水（gross）

  * (i) 生活端：W_gross_life = N × w_person × d
  * (ii) 农业端：W_gross_agri = (4.00 × A) × d
  * (iii) 运营端：W_gross_payload = N × w_payload × d（若考虑科研/工程，w_payload 需你自定）
* ② 年净补给水（net make‑up）

  * (i) W_net ≈ (W_gross_life + W_gross_agri + W_gross_payload) × (1 − r)

6.（3）示例（只作为“量级自检”，不是替你定参数）

* ① 情景 H（成熟基地 + 98% 回收）：w_person = 9.12，r = 0.98

  * (i) W_net_life ≈ 100000 × 9.12 × 365 × 0.02 ≈ **6.66×10^6 kg/年 ≈ 6,660 吨/年**
* ② 情景 L（ISS 量级 + 98% 回收）：w_person = 3.8，r = 0.98

  * (i) W_net_life ≈ **2,770 吨/年**

---

## 引用（权威来源）

1. NASA. *NASA Achieves Water Recovery Milestone on International Space Station* (Jun 20, 2023; page last updated Feb 3, 2025). [https://www.nasa.gov/missions/station/iss-research/nasa-achieves-water-recovery-milestone-on-international-space-station/](https://www.nasa.gov/missions/station/iss-research/nasa-achieves-water-recovery-milestone-on-international-space-station/)
2. NASA. *Life Support Baseline Values and Assumptions Document (BVAD), NASA/TP‑2015‑218570, Revision 2 (Feb 2022).*（见 Table 4‑20 & Table 4‑21）[https://ntrs.nasa.gov/api/citations/20210024855/downloads/BVAD_2.15.22-final.pdf](https://ntrs.nasa.gov/api/citations/20210024855/downloads/BVAD_2.15.22-final.pdf)
3. NASA. *NASA‑STD‑3001, Volume 2, Revision B*（Human Factors, Habitability & Environmental Health；饮用水、EVA 额外饮水、眼部冲洗、医疗应急水等要求）[https://standards.nasa.gov/sites/default/files/standards/NASA/C/Historical/nasa-std-3001_vol_2_rev_b.pdf](https://standards.nasa.gov/sites/default/files/standards/NASA/C/Historical/nasa-std-3001_vol_2_rev_b.pdf)
