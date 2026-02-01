你是资深科研工程师。请基于我给你的论文 Model 1（Scenario A/B/C）实现一个可复现实验的 Python 求解脚本，并把文件放到项目根目录下的「代码/」文件夹中（例如：代码/solve_model1.py）。要求：可直接运行、结构清晰、带类型标注与注释、并在你每次输出时给出“完整代码文件内容”（不要只给 diff）。

========================
1) 任务目标（What to build）
========================
实现三个情景的求解与报告：
- Scenario A（Pure Elevator）：闭式解（closed-form）计算最短工期 T_A*、所需火箭数 N_Rock,A*、总成本 C_A。
- Scenario B（Pure Rocket）：闭式解计算最少发射次数 N_Rock,B*、最短工期 T_B*、总成本 C_B。
- Scenario C（Hybrid）：对整数决策变量 N_Rock 做双目标优化（time vs cost），生成 Pareto 前沿（Pareto frontier），并使用论文的 weighted-sum method 生成一组 Pareto-optimal 解；同时给出一个推荐解（例如 knee point/折中点）。

脚本应输出：
1) 三情景的关键结果（T、N_Rock、M_SE、成本分项、C_total）
2) Scenario C 的 Pareto 解集（CSV）
3) 一张 Pareto 图（横轴 T，纵轴 C 或反之）
4) 推荐解（含 alpha、N_Rock、T、C）

========================
2) 输入参数（Parameters & Defaults）
========================
请把参数集中管理（放到脚本上面的全局变量那里）
单位必须在注释里写清楚。

全局需求：
- M_goal：总需求质量（ton）。默认 1e8（公式(2)）
时间与能力：
- Cap_SE：太空电梯年运力（ton/yr）。默认 5.37e5（Table 1）
- Cap_Rock：单次火箭可运载荷（ton）。默认 125（Table 1）
- f_total：地面年最大发射频次（launches/yr）。默认可用论文 Table 2(2050 forecast) 各发射场求和；也允许用户直接给标量。
  建议默认：f_total = 2300+950+190+70+140+100+35+25+24 = 3834 launches/yr（来自 Table 2 的高增长情景）
- f_cycle：在轨循环往返次数上限（cycles/yr per rocket）。默认 60（约 365/6，Table 1 注释）

成本参数（USD）：
- C_launch：单次发射成本（USD/launch）。默认按 Table 1 的 1.5e8；但论文 2.3 Data Preparation 还有 cost decay：
  Cost(t)=C0*exp[-k*(t-t0)]（论文式(1)），给出 C0=150M、k≈0.096，并提到“平均单次约 15M”。
  实现上：把 C_launch 当可配置标量；另外可选实现 mode="avg15m" 或 mode="decay"（按 t 计算）。
- C_elec_unit：电梯每吨电费（USD/ton）。默认 4.15（Table 1）
- C_maint：年维护费（USD/yr）。默认 1.2e8（Table 1）
- C_TV_fixed：转移系统固定成本（USD）。默认 3.0e8（Table 1；论文公式把它当固定项，不乘 T）

优化相关：
- alpha_grid：alpha∈[0,1] 的取值列表，如 np.linspace(0,1,21)
- 推荐解选择：默认用 knee point（可用“归一化后到理想点距离最小”或“到连接极端点直线距离最大”方法）

========================
3) 必须实现的公式（Model equations）
========================
严格按论文 Model 1 的定义实现，函数名建议与情景对应。

(1) 基本约束/定义（用于理解与核对）
- M_delivered ≥ M_goal（式(3)）
- M_SE ≤ Cap_SE*T（式(4)）
- N_Rock ≤ f_total*T（式(5)）
- M_Apex→Moon ≤ N_Rock*f_cycle*Cap_Rock*T（式(6)）

(2) Scenario A：闭式解（论文 3.2.1）
- M_SE = M_goal（式(14)）
- T_A* = M_goal/Cap_SE（式(16)）
- N_Rock,A* = ceil( Cap_SE/(f_cycle*Cap_Rock) )（式(20)）
- C_A = C_launch*N_Rock,A* + C_elec_unit*M_SE + C_maint*T_A* + C_TV_fixed（式(21)）

(3) Scenario B：闭式解（论文 3.2.2）
- N_Rock,B* = ceil( M_goal/Cap_Rock )（式(24)）
- T_B* = N_Rock,B*/f_total（式(26)）
- C_B = C_launch*N_Rock,B* + C_maint*T_B*（式(27)）
  注：B 不包含电费与 C_TV_fixed（论文说明）

(4) Scenario C：优化（论文 3.3）
决策变量：
- N_Rock ∈ Z_{\ge 0}（式(28)）

质量分解：
- M_direct = N_Rock*Cap_Rock（式(29)）
- M_SE = max(0, M_goal - N_Rock*Cap_Rock)（式(30)）

稳态有效运率：
- R(N_Rock) = min( Cap_SE, N_Rock*f_cycle*Cap_Rock )（式(32)）

剩余运输时间与部署时间：
- T_remain = M_SE / R(N_Rock)（式(33)；注意 R=0 要判定不可行）
- T_deploy = N_Rock / f_total（式(34)）
- T(N_Rock) = max(T_deploy, T_remain)（式(35)）

成本：
- C(N_Rock)= C_launch*N_Rock + C_elec_unit*M_SE + C_maint*T(N_Rock) + C_TV_fixed（式(36)）

可行搜索范围（重要，用于减少搜索）：
- N_low = ceil( Cap_SE/(f_cycle*Cap_Rock) )
- N_high = ceil( M_goal/Cap_Rock )
  （论文式(39)）

双目标与加权和：
- 目标：min ( T(N), C(N) )（式(37)）
- 归一化加权目标：
  J(N)= alpha*T(N)/T_ref + (1-alpha)*C(N)/C_ref（式(38)）
  其中 T_ref、C_ref 取“所有可行解中观察到的最大 T、最大 C”（按论文叙述）

实现要求：
- 先枚举 N∈[N_low, N_high]（整数），计算 (T,C,M_SE,R,...) 并过滤不可行项（如 R=0 且 M_SE>0）
- 计算 Pareto 前沿（非支配解：同时不劣且至少一项更优）
- 对每个 alpha，从可行解中最小化 J(N) 得到一组解（weighted-sum 产生的 Pareto-optimal 子集）
- 推荐解：
  1) 计算 Pareto 前沿上的 “knee point”：建议对 (T,C) 做 min-max 归一化后，找距离理想点(0,0)最近的点，或找离极端点连线距离最大的点；
  2) 输出推荐 N、T、C，并解释选择依据（写在结果 JSON 的字段里）

========================
4) 工程化要求（Project-ready）
========================
目录与文件：
- 代码/solve_model1.py（主脚本）
- 可选：代码/config_model1.yaml（参数配置示例）
- 输出目录：results/model1/（若不存在则创建）
输出文件：
- results/model1/scenario_summary.json（A/B/C 总结）
- results/model1/pareto_all_feasible.csv（可行解全量或采样；列含 N_Rock,T,C,M_SE,R）
- results/model1/pareto_front.csv（Pareto 前沿）
- results/model1/weighted_sum_solutions.csv（不同 alpha 对应的最优解）
- results/model1/pareto.png（Pareto 图）

CLI（命令行）：
- python 代码/solve_model1.py --config 代码/config_model1.yaml
- 支持 --no-plot（不画图）、--alpha-steps 21、--export-all（导出全量可行点）等参数

健壮性：
- 参数合法性检查：Cap_SE>0, Cap_Rock>0, f_total>0, f_cycle>0
- 防止除零：若 R(N)=0 且 M_SE>0 => 不可行
- 大范围枚举性能：允许用 numpy 向量化加速；至少保证 N_high=8e5 规模可在合理时间内运行（避免 O(N^2)）
- 结果要可复现：不要用随机数

可视化：
- 用 matplotlib 画 Pareto scatter；标注（annotate）推荐解、以及 alpha=0/1 的极端解

========================
5) 输出解释（What to print）
========================
脚本运行结束在控制台打印一段简洁摘要：
- Scenario A: T_A*, N_A*, C_A
- Scenario B: T_B*, N_B*, C_B
- Scenario C: 可行解数量、Pareto 点数量、推荐 N、推荐 T、推荐 C、对应 alpha（如果推荐解来自 weighted-sum，也给出）

请严格按以上要求实现，并输出完整代码内容（包含 import、主函数、参数解析、文件输出、绘图函数等）。
