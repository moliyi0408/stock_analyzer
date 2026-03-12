# analysis/behavior.py
from indicators import rebound_strength, selling_pressure, support_reclaim


LEVEL_LABELS = {
    "short_term": "短線",
    "swing": "波段",
    "long_term": "長線",
}

def judge_market_state(df, support, overheat, patterns, zones=None, volume_state=None, price_volume_signal=None):
    """
    綜合判斷：洗盤 / 中性 / 出貨
    """
    rebound = rebound_strength(df)
    sell_press = selling_pressure(df)
    reclaim = support_reclaim(df, support)

    close = df['Close'].iloc[-1]

    score = 0
    reasons = []

    # 行為層
    if rebound > 0.6:
        score += 1
        reasons.append("跌後反彈有力")
    if sell_press < 1.0:
        score += 1
        reasons.append("下跌量縮，非倒貨")

    if price_volume_signal == "下跌量縮":
        score += 1
        reasons.append("量價結構：下跌量縮，籌碼相對穩定")

    if reclaim:
        score += 1
        reasons.append("跌破支撐後站回")

    # ---------- 結構層（K 線） ----------
    if patterns and patterns.get('overall_bias') == 'bullish':
        score += 1
        reasons.append("K 線結構偏多")

   # ---------- 多層結構解讀 ----------
    zone_context = []

    def in_zone(price, zone):
        return zone[0] <= price <= zone[1]

    if zones:
        for level, data in zones.items():
            level_name = LEVEL_LABELS.get(level, str(level))
            for z in data.get("support", []):
                if in_zone(close, z):
                    zone_context.append(f"{level_name}支撐")
            for z in data.get("resistance", []):
                if in_zone(close, z):
                    zone_context.append(f"{level_name}壓力")

    if zone_context:
        reasons.append(f"價格位於{' / '.join(zone_context)}區")

        # 關鍵判斷：踩壓力不加分
        if any("壓力" in z for z in zone_context):
            score -= 1

    # ---------- 市場情緒 ----------
    if overheat and overheat.get('total', 0) > 60:
        score -= 1
        reasons.append("市場過熱，高檔風險")

    if (
        volume_state == "爆量"
        and patterns
        and patterns.get("details", {}).get("long_upper_days", 0) >= 2
    ):
        score -= 1
        reasons.append("高檔爆量長上影，追價風險升高")
        
    # ---------- 最終判斷 ----------

    if score >= 3:
        return "洗盤偏多，可續抱", reasons
    elif score <= 0:
        return "出貨風險升高，反彈減碼", reasons
    else:
        return "震盪整理，觀察為主", reasons
