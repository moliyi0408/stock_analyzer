# analysis/behavior.py
from ._behavior_core import rebound_strength, selling_pressure, support_reclaim

def judge_market_state(df, support, overheat, patterns):
    """
    綜合判斷：洗盤 / 中性 / 出貨
    """
    rebound = rebound_strength(df)
    sell_press = selling_pressure(df)
    reclaim = support_reclaim(df, support)

    score = 0
    reasons = []

    # 行為層
    if rebound > 0.6:
        score += 1
        reasons.append("跌後反彈有力")
    if sell_press < 1.0:
        score += 1
        reasons.append("下跌量縮，非倒貨")
    if reclaim:
        score += 1
        reasons.append("跌破支撐後站回")

    # 結構層（你原本就有）
    if patterns and patterns.get('overall_bias') == 'bullish':
        score += 1
        reasons.append("K 線結構偏多")
    if overheat and overheat.get('total', 0) > 60:
        score -= 1
        reasons.append("市場過熱，高檔風險")

    if score >= 3:
        return "洗盤偏多，可續抱", reasons
    elif score <= 0:
        return "出貨風險升高，反彈減碼", reasons
    else:
        return "震盪整理，觀察為主", reasons
