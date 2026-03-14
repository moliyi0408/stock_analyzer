from __future__ import annotations

from typing import Any, Dict


def fundamental_strategy(analysis_result: Dict[str, Any]) -> Dict[str, Any]:
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
    gross_ok = bool(signals.get("good_gross_margin"))
    op_ok = bool(signals.get("good_operating_margin"))
    eps_ok = bool(signals.get("eps_growing"))

    metrics = analysis_result.get("metrics", {})

    reasons = []
    if gross_ok:
        reasons.append("毛利率維持在健康區間")
    if op_ok:
        reasons.append("營業利益率具支撐")
    if eps_ok:
        reasons.append("EPS 季增率為正，獲利動能延續")

    if gross_ok and op_ok and eps_ok:
        return {
            "action": "偏多",
            "rating": "A",
            "position_plan": "可分 2~3 批布局",
            "summary": "毛利率、營業利益率佳且 EPS 成長，基本面屬強勢",
            "reasons": reasons,
            "risk_notes": ["仍需搭配技術面停損", "若下季 EPS 轉負應降評"],
            "focus_metrics": {
                "gross_margin": metrics.get("gross_margin"),
                "operating_margin": metrics.get("operating_margin"),
                "eps_change": metrics.get("eps_change"),
            },
        }
    if eps_ok and (gross_ok or op_ok):
        return {
            "action": "偏多",
            "rating": "B",
            "position_plan": "小部位試單，拉回再加碼",
            "summary": "EPS 成長且至少一項獲利指標達標，可偏多但不追高",
            "reasons": reasons,
            "risk_notes": ["避免一次重壓", "若營收成長放緩需減碼"],
            "focus_metrics": {
                "gross_margin": metrics.get("gross_margin"),
                "operating_margin": metrics.get("operating_margin"),
                "eps_change": metrics.get("eps_change"),
            },
        }
    if not eps_ok and (gross_ok or op_ok):
        return {
            "action": "中性",
            "rating": "C",
            "position_plan": "以觀察/防守倉為主",
            "summary": "獲利能力尚可，但 EPS 動能不足",
            "reasons": reasons if reasons else ["至少一項獲利能力指標仍在合理區間"],
            "risk_notes": ["等待 EPS 回升再擴大倉位"],
            "focus_metrics": {
                "gross_margin": metrics.get("gross_margin"),
                "operating_margin": metrics.get("operating_margin"),
                "eps_change": metrics.get("eps_change"),
            },
        }
    return {
        "action": "保守",
        "rating": "D",
        "position_plan": "避免新倉",
        "summary": "獲利率與 EPS 動能不足，建議保守應對",
        "reasons": ["毛利率/營業利益率未達門檻", "EPS 季增率未轉正"],
        "risk_notes": ["等待財報改善訊號再評估", "僅適合短線反彈策略"],
        "focus_metrics": {
            "gross_margin": metrics.get("gross_margin"),
            "operating_margin": metrics.get("operating_margin"),
            "eps_change": metrics.get("eps_change"),
        },
    }
