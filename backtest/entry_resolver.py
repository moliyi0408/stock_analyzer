from typing import Optional


def _safe_float(value) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def resolve_entry_price(signal: dict, mode: str = "first_tier") -> Optional[float]:
    """
    將 analysis/decision_engine 的模糊建議，轉成 backtest 可執行的單一進場價。

    mode:
      - first_tier: 第一批買點（預設）
      - last_tier: 最保守買點
      - mid_zone: 買入區間中位數
      - support_level: 直接用支撐價
      - resistance_breakout: 直接用壓力價（突破測試）
      - effective_entry: 使用 decision_engine 的 effective_entry_price
    """
    if not isinstance(signal, dict):
        return None

    buy_reco = signal.get("buy_recommendation") or {}
    tiers = buy_reco.get("tiers") if isinstance(buy_reco, dict) else None
    preferred_zone = buy_reco.get("preferred_buy_zone") if isinstance(buy_reco, dict) else None

    tier_prices = []
    if isinstance(tiers, list):
        for tier in tiers:
            if isinstance(tier, dict):
                price = _safe_float(tier.get("price"))
                if price is not None:
                    tier_prices.append(price)

    if mode == "first_tier":
        return tier_prices[0] if tier_prices else None

    if mode == "last_tier":
        return tier_prices[-1] if tier_prices else None

    if mode == "mid_zone" and isinstance(preferred_zone, list) and len(preferred_zone) == 2:
        low = _safe_float(preferred_zone[0])
        high = _safe_float(preferred_zone[1])
        if low is not None and high is not None:
            return (low + high) / 2

    if mode == "support_level":
        return _safe_float(signal.get("support_level"))

    if mode == "resistance_breakout":
        return _safe_float(signal.get("resistance_level"))

    if mode == "effective_entry":
        return _safe_float(signal.get("effective_entry_price"))

    return None
