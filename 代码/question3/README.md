# Task 3 月面供水缓冲仿真说明

本目录的 `Q3.py` 实现论文 Task 3 的年度供水库存与断供风险模型，基于 Task 2 的 DES 框架，并新增月面库存状态与安全库存估计。

## 运行方式

```bash
python 代码/question3/Q3.py --n-mc 50
```

可选参数：

- `--scenario`：选择情景 1/2/3（默认 3）
- `--n-mc`：蒙特卡洛运行次数
- `--seed`：随机种子
- `--S-moon`：初始安全库存（ton）
- `--w-person`：人均日用水量（kg/day，默认 157.1）
- `--A-m2`：植物舱面积（m^2）
- `--w-agri`：农业用水强度（kg/m^2/day，默认 4.0）
- `--w-payload`：运营/科研用水（kg/person/day）
- `--extra-loss`：额外不可回收损失比例（0~1）
- `--elevator-delay`：太空电梯单程延迟（day，默认 14）
- `--r-base`：基线回收率（默认 0.52）
- `--delta-r`：退化期回收率下降量
- `--r-degrade-start` / `--r-degrade-end`：退化期起止（day）
- `--eta-pack`：水装载效率
- `--kappa-svc`：服务时间放大系数
- `--alpha`：安全库存置信水平
- `--config`：JSON 配置文件

## 输出说明

程序输出 JSON 摘要，包括：

- 年需求量 `W_gross_ton` / `W_net_ton`
- 基线与最劣日消耗 `c_base_ton_per_day` / `c_max_ton_per_day`
- 断供风险分位间隔 `max_gap_quantile_days`
- 安全库存估计 `S_moon_star_ton`
- 断供统计、交付次数、故障次数、排队等待等指标
- 年度成本统计（USD）
