#!/usr/bin/env python3
"""Task 5: Multi-criteria decision engine (EWM + AHP + TOPSIS).

输入：包含三方案(A/B/C)的指标统计 JSON。
支持两种取值口径：分位数或均值+λσ，统一 5 个成本型指标：
T(完工时间)、C(成本)、N_fail(失效次数)、S_moon(99%安全库存阈值)、E_impact(环境代价)。
权重：EWM 信息权重；AHP 主观权重(三套偏好)；组合权重 w = λ w_AHP + (1-λ) w_EWM。
方法：成本型转效益型后做 TOPSIS，返回得分、排序、权重、CR。
可选鲁棒性：随机 Dirichlet 扰动组合权重，统计胜率。
"""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path
from typing import Dict, List, Tuple

MetricVector = List[float]
ScenarioMatrix = Dict[str, MetricVector]


METRIC_ORDER = ["T", "C", "N_fail", "S_moon", "E_impact"]
RI_TABLE = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.9, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45}


def quantile_from_samples(samples: List[float], q: float) -> float:
    if not samples:
        raise ValueError("samples empty")
    data = sorted(samples)
    k = max(0, min(len(data) - 1, int(math.ceil(q * len(data)) - 1)))
    return float(data[k])


def extract_value(stat: Dict[str, float], mode: str, q: float, lam_sigma: float) -> float:
    if mode == "quantile":
        key = f"p{int(q*100):02d}"
        if key in stat:
            return float(stat[key])
        if "quantiles" in stat and str(q) in stat["quantiles"]:
            return float(stat["quantiles"][str(q)])
        if "samples" in stat:
            return quantile_from_samples(stat["samples"], q)
    if mode == "mean_sigma":
        if "mean" in stat and "std" in stat:
            return float(stat["mean"] + lam_sigma * stat["std"])
        if "samples" in stat:
            m = sum(stat["samples"]) / len(stat["samples"])
            var = sum((x - m) ** 2 for x in stat["samples"]) / max(1, len(stat["samples"]) - 1)
            return float(m + lam_sigma * math.sqrt(var))
    if "mean" in stat:
        return float(stat["mean"])
    raise ValueError("stat lacks required fields")


def load_decision_matrix(data: Dict[str, Dict[str, Dict[str, float]]], mode: str, q: float, lam_sigma: float) -> ScenarioMatrix:
    matrix: ScenarioMatrix = {}
    for sid, metrics in data.items():
        vec: MetricVector = []
        for m in METRIC_ORDER:
            if m not in metrics:
                raise ValueError(f"scenario {sid} missing metric {m}")
            vec.append(extract_value(metrics[m], mode, q, lam_sigma))
        matrix[sid] = vec
    return matrix


def ewm_weights(matrix: ScenarioMatrix) -> List[float]:
    # 成本型转效益型：列最大值 - 值
    cols = list(zip(*matrix.values()))
    benefit = []
    for col in cols:
        mx = max(col)
        benefit.append([mx - x + 1e-12 for x in col])
    m = len(matrix)
    n = len(METRIC_ORDER)
    pj = []
    for j in range(n):
        col = benefit[j]
        s = sum(col)
        probs = [c / s if s > 0 else 1.0 / m for c in col]
        ent = -sum(p * math.log(p + 1e-12) for p in probs) / math.log(m)
        pj.append(ent)
    dj = [1 - e for e in pj]
    s = sum(dj)
    return [d / s if s > 0 else 1.0 / n for d in dj]


def ahp_from_vector(w: List[float]) -> List[List[float]]:
    return [[w[i] / w[j] for j in range(len(w))] for i in range(len(w))]


def ahp_weights(matrix: List[List[float]]) -> Tuple[List[float], float]:
    n = len(matrix)
    # 几何平均法
    gm = [math.prod(row) ** (1.0 / n) for row in matrix]
    s = sum(gm)
    w = [g / s for g in gm]
    # 一致性
    aw = [sum(matrix[i][j] * w[j] for j in range(n)) for i in range(n)]
    lam_max = sum(aw[i] / w[i] for i in range(n)) / n
    ci = (lam_max - n) / (n - 1) if n > 1 else 0.0
    ri = RI_TABLE.get(n, 1.49)
    cr = ci / ri if ri > 0 else 0.0
    return w, cr


def default_ahp_profile(name: str) -> Tuple[List[float], float]:
    profiles = {
        "economy": [0.22, 0.38, 0.14, 0.12, 0.14],
        "safety": [0.16, 0.16, 0.3, 0.26, 0.12],
        "green": [0.18, 0.16, 0.16, 0.15, 0.35],
    }
    if name not in profiles:
        raise ValueError("unknown ahp profile")
    mat = ahp_from_vector(profiles[name])
    return ahp_weights(mat)


def normalize_benefit(matrix: ScenarioMatrix) -> ScenarioMatrix:
    cols = list(zip(*matrix.values()))
    norm_cols = []
    for col in cols:
        mx = max(col)
        benefit = [mx - x + 1e-12 for x in col]
        denom = math.sqrt(sum(b * b for b in benefit))
        norm_cols.append([b / denom if denom > 0 else 0.0 for b in benefit])
    scenario_ids = list(matrix.keys())
    normalized: ScenarioMatrix = {sid: [norm_cols[j][i] for j in range(len(METRIC_ORDER))] for i, sid in enumerate(scenario_ids)}
    return normalized


def topsis(matrix: ScenarioMatrix, weights: List[float]) -> Dict[str, float]:
    norm = normalize_benefit(matrix)
    ids = list(norm.keys())
    n = len(METRIC_ORDER)
    weighted = {sid: [norm[sid][j] * weights[j] for j in range(n)] for sid in ids}
    ideal_pos = [max(weighted[sid][j] for sid in ids) for j in range(n)]
    ideal_neg = [min(weighted[sid][j] for sid in ids) for j in range(n)]
    scores: Dict[str, float] = {}
    for sid in ids:
        dp = math.sqrt(sum((weighted[sid][j] - ideal_pos[j]) ** 2 for j in range(n)))
        dn = math.sqrt(sum((weighted[sid][j] - ideal_neg[j]) ** 2 for j in range(n)))
        scores[sid] = dn / (dp + dn + 1e-12)
    return scores


def dirichlet(center: List[float], kappa: float, rng: random.Random) -> List[float]:
    alphas = [c * kappa for c in center]
    samples = [rng.gammavariate(a, 1.0) for a in alphas]
    s = sum(samples)
    return [x / s for x in samples]


def robustness(scores_func, base_w: List[float], samples: int, seed: int) -> Dict[str, float]:
    rng = random.Random(seed)
    wins = {sid: 0 for sid in scores_func(base_w).keys()}
    for _ in range(samples):
        w = dirichlet(base_w, 200.0, rng)
        res = scores_func(w)
        best = max(res.items(), key=lambda x: x[1])[0]
        wins[best] += 1
    total = float(samples)
    return {k: v / total for k, v in wins.items()}


def main() -> None:
    p = argparse.ArgumentParser(description="Task5 decision engine (EWM + AHP + TOPSIS)")
    p.add_argument("--input", required=True, help="JSON with scenarios.{A,B,C}.{metric} stats")
    p.add_argument("--mode", choices=["quantile", "mean_sigma"], default="quantile", help="Value extraction mode")
    p.add_argument("--quantile", type=float, default=0.95, help="Quantile for metrics (cost-type)")
    p.add_argument("--lambda-sigma", type=float, default=1.0, help="Mean+lambda*sigma multiplier")
    p.add_argument("--lambda-combine", type=float, default=0.5, help="λ for weight blending")
    p.add_argument("--ahp-profile", choices=["economy", "safety", "green"], default="economy", help="AHP preference set")
    p.add_argument("--robust-samples", type=int, default=0, help="Dirichlet perturbation count for win rate")
    p.add_argument("--seed", type=int, default=42, help="RNG seed")
    p.add_argument("--output", type=str, default=None, help="Output JSON path (default question5/results/decision.json)")
    args = p.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        raw = json.load(f)
    scenarios = raw.get("scenarios")
    if not scenarios:
        raise ValueError("input missing scenarios")

    matrix = load_decision_matrix(scenarios, args.mode, args.quantile, args.lambda_sigma)

    w_ewm = ewm_weights(matrix)
    w_ahp, cr = default_ahp_profile(args.ahp_profile)
    lam = args.lambda_combine
    w_comb = [lam * a + (1 - lam) * e for a, e in zip(w_ahp, w_ewm)]
    s_comb = topsis(matrix, w_comb)

    result = {
        "metric_order": METRIC_ORDER,
        "decision_matrix": matrix,
        "weights": {
            "ewm": w_ewm,
            "ahp": w_ahp,
            "ahp_CR": cr,
            "lambda": lam,
            "combined": w_comb,
        },
        "topsis_score": s_comb,
        "ranking": sorted(s_comb, key=s_comb.get, reverse=True),
    }

    if args.robust_samples > 0:
        def scorer(w):
            return topsis(matrix, w)
        result["robust_win_rate"] = robustness(scorer, w_comb, args.robust_samples, args.seed)

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = Path(__file__).resolve().parent / "results" / "decision.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
