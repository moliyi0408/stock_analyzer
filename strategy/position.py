def position_hint(trend, heat):
    if trend == "多頭趨勢" and "冷靜" in heat:
        return "可分批布局"
    return "保守操作"


def calc_position_size(capital, risk_pct, entry_price, stop_loss_price):
    """
    倉位控制公式：
    position = capital * risk_pct / (entry_price - stop_loss_price)
    回傳值為可投入金額（受限於總資金）
    """
    if capital <= 0 or risk_pct <= 0:
        return 0
    if entry_price is None or stop_loss_price is None:
        return 0

    stop_distance = entry_price - stop_loss_price
    if stop_distance <= 0:
        return 0

    risk_budget = capital * risk_pct
    shares = risk_budget / stop_distance
    position_value = shares * entry_price
    return min(round(position_value, 2), float(capital))
