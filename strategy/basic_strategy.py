from __future__ import annotations

from typing import Any, Dict


def fundamental_strategy(analysis_result: Dict[str, Any]) -> str:
    """Generate basic advice from fundamental analysis result."""
    if not analysis_result or not analysis_result.get("has_data"):
        return "Hold: 基本面資料不足，先觀察"

    signals = analysis_result.get("signals", {})
    gross_ok = bool(signals.get("good_gross_margin"))
    op_ok = bool(signals.get("good_operating_margin"))
    eps_ok = bool(signals.get("eps_growing"))

    if gross_ok and op_ok and eps_ok:
        return "Strong Buy: 毛利率、營業利益率佳，且 EPS 持續成長"
    if eps_ok and (gross_ok or op_ok):
        return "Buy: EPS 成長且部分獲利能力指標良好"
    if not eps_ok and (gross_ok or op_ok):
        return "Hold: 獲利能力尚可，但 EPS 尚未轉強"
    return "Sell / Avoid: 基本面動能不足，建議保守"
