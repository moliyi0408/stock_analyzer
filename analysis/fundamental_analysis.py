from __future__ import annotations

from typing import Any, Dict

import pandas as pd

from indicators.fundamental_indicators import calc_fundamental_indicators


def analyze_fundamentals(df: pd.DataFrame) -> Dict[str, Any]:
    """Analyze latest and trend-level fundamental indicators."""
    indicator_df = calc_fundamental_indicators(df)
    if indicator_df.empty:
        return {
            "has_data": False,
            "metrics": {},
            "signals": {
                "good_gross_margin": False,
                "good_operating_margin": False,
                "eps_growing": False,
            },
            "score": 0,
            "summary": "基本面資料不足",
        }

    latest = indicator_df.iloc[-1]
    eps_change_series = indicator_df["EPS_change"].dropna()
    recent_eps_trend = eps_change_series.tail(3).mean() if not eps_change_series.empty else None

    signals = {
        "good_gross_margin": bool(pd.notna(latest.get("GrossMargin")) and latest["GrossMargin"] >= 0.30),
        "good_operating_margin": bool(pd.notna(latest.get("OperatingMargin")) and latest["OperatingMargin"] >= 0.15),
        "eps_growing": bool(pd.notna(latest.get("EPS_change")) and latest["EPS_change"] > 0),
    }

    score = sum(1 for passed in signals.values() if passed)

    return {
        "has_data": True,
        "as_of": latest["date"].strftime("%Y-%m-%d") if pd.notna(latest["date"]) else None,
        "metrics": {
            "gross_margin": latest.get("GrossMargin"),
            "operating_margin": latest.get("OperatingMargin"),
            "eps": latest.get("EPS"),
            "eps_change": latest.get("EPS_change"),
            "eps_change_3p_avg": recent_eps_trend,
        },
        "signals": signals,
        "score": score,
        "summary": f"通過 {score}/3 項基本面條件",
        "data": indicator_df,
    }
