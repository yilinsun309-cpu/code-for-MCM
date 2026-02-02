


**A情况**

[开始] 场景=1 I0=71 S_moon=0.0 cap_eff=529784.64
{
  "runs": 1,
  "feasible_runs": 0,
  "stockout_runs": 1,
  "W_gross_life_ton": 5734150.0,
  "W_gross_agri_ton": 0.0,
  "W_gross_payload_ton": 0.0,
  "W_gross_ton": 5734150.0,
  "W_net_ton": 2752392.0,
  "c_base_ton_per_day": 7540.799999999999,
  "c_max_ton_per_day": 7540.799999999999,
  "max_gap_quantile_days": 17.077507909615754,
  "S_moon_star_ton": 128778.07164483046,
  "W_q_quantile_days": 11.077507909615752,
  "S_moon_min_ton": 189104.47164483045,
  "delta_replacement_days": 14.0,
  "I_safe": 71,
  "launch_slot_interval_days": 0.0949531737773153,
  "mean_min_inventory_ton": 0.0,
  "min_inventory_ton": 0.0,
  "mean_arrivals": 3990.0,
  "mean_direct_arrivals": 0.0,
  "mean_failures": 49.0,
  "mean_launches": 47.0,
  "max_inventory_queue": 68,
  "max_inventory_wait_days": 11.077507909615752,
  "max_launch_wait_days": 6.6467221644120675,
  "mean_cost_usd": 79968319065.6,
  "min_cost_usd": 79968319065.6,
  "max_cost_usd": 79968319065.6
}



**B情况**
(base) PS D:\MCM\code-for-MCM> python 代码/question3/Q3.py --n-mc 1 --verbose --log-every 10000 --scenario 2
[MC] 运行 1/1
[开始] 场景=2 I0=71 S_moon=0.0 cap_eff=0.00
{
  "runs": 1,
  "feasible_runs": 0,
  "stockout_runs": 1,
  "W_gross_life_ton": 5734150.0,
  "W_gross_agri_ton": 0.0,
  "W_gross_payload_ton": 0.0,
  "W_gross_ton": 5734150.0,
  "W_net_ton": 2752392.0,
  "c_base_ton_per_day": 7540.799999999999,
  "c_max_ton_per_day": 7540.799999999999,
  "max_gap_quantile_days": 14.626170655567279,
  "S_moon_star_ton": 110293.02767950173,
  "W_q_quantile_days": 14.171956295526432,
  "S_moon_min_ton": 212439.08803330568,
  "delta_replacement_days": 14.0,
  "I_safe": 71,
  "launch_slot_interval_days": 0.0949531737773153,
  "mean_min_inventory_ton": 0.0,
  "min_inventory_ton": 0.0,
  "mean_arrivals": 1298.0,
  "mean_direct_arrivals": 1298.0,
  "mean_failures": 32.0,
  "mean_launches": 30.0,
  "max_inventory_queue": 0,
  "max_inventory_wait_days": 0.0,
  "max_launch_wait_days": 14.171956295526432,
  "mean_cost_usd": 19470000000.0,
  "min_cost_usd": 19470000000.0,
  "max_cost_usd": 19470000000.0
}


**C情况**
(base) PS D:\MCM\code-for-MCM> python 代码/question3/Q3.py --n-mc 1 --verbose --log-every 10000 --scenario 3
[MC] 运行 1/1
[开始] 场景=3 I0=71 S_moon=0.0 cap_eff=529784.64
{
  "runs": 1,
  "feasible_runs": 0,
  "stockout_runs": 1,
  "W_gross_life_ton": 5734150.0,
  "W_gross_agri_ton": 0.0,
  "W_gross_payload_ton": 0.0,
  "W_gross_ton": 5734150.0,
  "W_net_ton": 2752392.0,
  "c_base_ton_per_day": 7540.799999999999,
  "c_max_ton_per_day": 7540.799999999999,
  "max_gap_quantile_days": 5.999999999999999,
  "S_moon_star_ton": 45244.79999999999,
  "W_q_quantile_days": 6.6467221644120675,
  "S_moon_min_ton": 155692.80249739852,
  "delta_replacement_days": 14.0,
  "I_safe": 71,
  "launch_slot_interval_days": 0.0949531737773153,
  "mean_min_inventory_ton": 0.0,
  "min_inventory_ton": 0.0,
  "mean_arrivals": 4040.0,
  "mean_direct_arrivals": 117.0,
  "mean_failures": 56.0,
  "mean_launches": 54.0,
  "max_inventory_queue": 52,
  "max_inventory_wait_days": 5.077507909615754,
  "max_launch_wait_days": 6.6467221644120675,
  "mean_cost_usd": 80624117685.6,
  "min_cost_usd": 80624117685.6,
  "max_cost_usd": 80624117685.6
}