from __future__ import annotations

from typing import Any, Dict

import pandas as pd


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    num = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(num):
        return None
    return float(num)


def _score_by_thresholds(value: float | None, thresholds: list[tuple[float, int]]) -> int:
    if value is None:
        return 50
    for min_value, score in thresholds:
        if value >= min_value:
            return score
    return thresholds[-1][1]


def _score_roe(roe: float | None) -> int:
    # 單位為比率（例如 0.15 = 15%）
    return _score_by_thresholds(
        roe,
        [
            (0.20, 100),
            (0.15, 85),
            (0.10, 70),
            (0.05, 55),
            (0.00, 35),
            (-1.00, 20),
        ],
    )


def _score_operating_margin(operating_margin: float | None) -> int:
    return _score_by_thresholds(
        operating_margin,
        [
            (0.20, 100),
            (0.10, 82),
            (0.05, 65),
            (0.00, 45),
            (-1.00, 25),
        ],
    )


def _score_gross_margin(gross_margin: float | None) -> int:
    return _score_by_thresholds(
        gross_margin,
        [
            (0.40, 100),
            (0.25, 80),
            (0.15, 65),
            (0.00, 45),
            (-1.00, 25),
        ],
    )


def _score_eps_growth(eps_change: float | None, eps_change_avg: float | None) -> int:
    latest_score = _score_by_thresholds(
        eps_change,
        [
            (0.20, 95),
            (0.10, 80),
            (0.00, 65),
            (-0.10, 45),
            (-1.00, 25),
        ],
    )
    avg_score = _score_by_thresholds(
        eps_change_avg,
        [
            (0.15, 90),
            (0.05, 75),
            (0.00, 60),
            (-0.10, 45),
            (-1.00, 30),
        ],
    )
    return round(latest_score * 0.7 + avg_score * 0.3)


def _score_debt_ratio(debt_ratio: float | None) -> int:
    # 負債比越低越穩健
    if debt_ratio is None:
        return 50
    if debt_ratio < 0.30:
        return 95
    if debt_ratio < 0.50:
        return 78
    if debt_ratio < 0.70:
        return 60
    return 35


def _score_to_rating(score: int) -> str:
    if score >= 80:
        return "A"
    if score >= 65:
        return "B"
    if score >= 50:
        return "C"
    return "D"


def fundamental_strategy(analysis_result: Dict[str, Any], snapshot: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Generate operation suggestions from fundamental analysis result."""
    if not analysis_result or not analysis_result.get("has_data"):
        return {
            "action": "觀望",
            "rating": "N/A",
            "position_plan": "先不進場",
            "summary": "基本面資料不足，先觀察",
            "reasons": ["目前可用的財報期數不足，無法確認趨勢"],
            "risk_notes": ["等待下一次財報更新後再評估"],
        }

    signals = analysis_result.get("signals", {})
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    metrics = analysis_result.get("metrics", {})
    gross_margin = _to_float(metrics.get("gross_margin"))
    operating_margin = _to_float(metrics.get("operating_margin"))
    eps_change = _to_float(metrics.get("eps_change"))
    eps_change_avg = _to_float(metrics.get("eps_change_3p_avg"))
    roe = _to_float(snapshot.get("roe"))
    debt_ratio = _to_float(snapshot.get("debt_ratio"))

    weighted_scores = {
        "roe": _score_roe(roe),
        "operating_margin": _score_operating_margin(operating_margin),
        "gross_margin": _score_gross_margin(gross_margin),
        "eps_growth": _score_eps_growth(eps_change, eps_change_avg),
        "debt_ratio": _score_debt_ratio(debt_ratio),
    }
    score = round(
        weighted_scores["roe"] * 0.30
        + weighted_scores["operating_margin"] * 0.25
        + weighted_scores["gross_margin"] * 0.15
        + weighted_scores["eps_growth"] * 0.20
        + weighted_scores["debt_ratio"] * 0.10
    )
    rating = _score_to_rating(score)

    gross_ok = bool(signals.get("good_gross_margin"))
    op_ok = bool(signals.get("good_operating_margin"))
    eps_ok = bool(signals.get("eps_growing"))

    reasons = []
    if gross_ok:
        reasons.append("毛利率維持在健康區間")
    if op_ok:
        reasons.append("營業利益率具支撐")
    if eps_ok:
        reasons.append("EPS 季增率為正，獲利動能延續")
    if roe is not None and roe < 0.05:
        reasons.append("ROE 偏低，股東資本使用效率仍待改善")
    if operating_margin is not None and operating_margin < 0.05:
        reasons.append("營運效率偏弱（營業利益率偏低）")
    if debt_ratio is not None and debt_ratio >= 0.50:
        reasons.append("負債比率位於中高區，需持續追蹤償債壓力")

    if score >= 80:
        action = "偏多"
        position_plan = "可分 2~3 批布局"
        summary = "獲利能力與成長動能均衡，基本面屬強勢"
        risk_notes = ["仍需搭配技術面停損", "若下季 EPS 轉負應降評"]
    elif score >= 65:
        action = "偏多"
        position_plan = "小部位試單，拉回再加碼"
        summary = "基本面整體偏健康，但部分指標仍需追蹤"
        risk_notes = ["避免一次重壓", "若營收成長放緩需減碼"]
    elif score >= 50:
        action = "中性"
        position_plan = "以觀察/防守倉為主"
        summary = "基本面中性，尚未形成明確的高品質成長結構"
        risk_notes = ["等待下一季財報確認營運改善"]
    else:
        action = "保守"
        position_plan = "避免新倉"
        summary = "營運效率偏弱（ROE 與營業利益率偏低），建議保守應對"
        risk_notes = ["等待財報改善訊號再評估", "僅適合短線反彈策略"]

    return {
        "action": action,
        "rating": rating,
        "fundamental_score": score,
        "score_weights": {
            "roe": 0.30,
            "operating_margin": 0.25,
            "gross_margin": 0.15,
            "eps_growth": 0.20,
            "debt_ratio": 0.10,
        },
        "score_breakdown": weighted_scores,
        "position_plan": position_plan,
        "summary": summary,
        "reasons": reasons if reasons else ["目前資料呈現中性，需觀察後續財報"],
        "risk_notes": risk_notes,
        "focus_metrics": {
            "gross_margin": metrics.get("gross_margin"),
            "operating_margin": metrics.get("operating_margin"),
            "eps_change": metrics.get("eps_change"),
            "eps_change_3p_avg": metrics.get("eps_change_3p_avg"),
            "roe": snapshot.get("roe"),
            "debt_ratio": snapshot.get("debt_ratio"),
            "free_cash_flow": snapshot.get("free_cash_flow"),
        },
    }
