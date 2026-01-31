# indicators/overheat.py
from .momentum import calc_rsi

def calc_overheat_score(df, start_zone, resistance_zones):
    """
    回傳過熱分數與細項（0 ~ 約100）
    """
    if df.empty or 'Close' not in df.columns:
        return None

    close = df['Close'].dropna()
    if len(close) < 30:
        return None

    current_price = close.iloc[-1]

    # RSI
    rsi_series = calc_rsi(close)
    rsi = rsi_series.iloc[-1]

    if rsi < 65:
        rsi_score = 0
    elif rsi < 70:
        rsi_score = 10
    elif rsi < 80:
        rsi_score = 18
    else:
        rsi_score = 25

    # 均線乖離（20MA）
    ma20 = close.rolling(20).mean().iloc[-1]
    deviation = (current_price - ma20) / ma20 * 100

    if deviation < 5:
        ma_score = 0
    elif deviation < 10:
        ma_score = 10
    elif deviation < 15:
        ma_score = 18
    else:
        ma_score = 25

    # 起漲區距離
    start_low, start_high = start_zone
    if start_high and start_high > 0:
        ratio = current_price / start_high
        if ratio < 1.15:
            start_score = 0
        elif ratio < 1.3:
            start_score = 10
        elif ratio < 1.5:
            start_score = 18
        else:
            start_score = 25
    else:
        start_score = 0

    # 壓力區風險
    pressure_score = 0
    for r in resistance_zones:
        if abs(current_price - r) / r < 0.03:
            pressure_score = max(pressure_score, 15)
        if current_price > r:
            pressure_score = max(pressure_score, 20)

    total = rsi_score + ma_score + start_score + pressure_score

    return {
        "total": int(total),
        "current_price": round(current_price, 2),
        "rsi": round(rsi, 2),
        "rsi_score": rsi_score,
        "ma_deviation": round(deviation, 2),
        "ma_score": ma_score,
        "start_zone_score": start_score,
        "pressure_score": pressure_score
    }
