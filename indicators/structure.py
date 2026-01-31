# indicators/structure.py
import pandas as pd

def get_starting_zone(df, window=20):
    """
    計算起漲區
    """
    if df.empty or len(df) < window:
        return None, None

    close = df['Close']
    vol = df['Volume']

    min_std = float('inf')
    zone_start = zone_end = None

    for i in range(len(close) - window + 1):
        window_prices = close[i:i+window]
        window_vol = vol[i:i+window]
        std = window_prices.std()
        avg_vol = window_vol.mean()

        if std < min_std and avg_vol > 0:
            min_std = std
            zone_start = window_prices.min()
            zone_end = window_prices.max()

    if zone_start is None or zone_end is None:
        return None, None

    return round(zone_start, 2), round(zone_end, 2)

def get_selling_zone(start_low, start_high, profit_ratio=0.3):
    """
    計算賣出區間
    """
    if start_low is None or start_high is None:
        return None, None
    sell_low = round(start_high * (1 + profit_ratio*0.8), 2)
    sell_high = round(start_high * (1 + profit_ratio), 2)
    return sell_low, sell_high

def get_support_resistance(df, bin_size=5, top_n=3):
    """
    計算支撐壓力區
    """
    if df.empty:
        return [], []

    close_prices = df['Close'].dropna()
    min_price = close_prices.min()
    max_price = close_prices.max()

    bins = list(range(int(min_price//bin_size)*bin_size, int(max_price//bin_size + 2)*bin_size, bin_size))
    hist = pd.cut(close_prices, bins=bins).value_counts().sort_values(ascending=False)
    top_bins = hist.head(top_n).index.tolist()
    
    mid_price = close_prices.mean()
    support = sorted([b.left for b in top_bins if b.right <= mid_price])
    resistance = sorted([b.right for b in top_bins if b.left >= mid_price])

    return support, resistance

"""
Structure & Pattern Indicators
-------------------------------
📌 功能：
- 支撐/壓力區計算
- K 線型態分析（十字線、長影線、仙人指路）
- 偏多/偏空結構判斷
"""

# ----------------- K線型態分析工具 -----------------
def get_candle_features(row):
    """計算 K 線各部分比例"""
    body = abs(row['Close'] - row['Open'])
    full = row['High'] - row['Low']
    upper = row['High'] - max(row['Open'], row['Close'])
    lower = min(row['Open'], row['Close']) - row['Low']

    if full == 0:
        return None

    return {
        "body_ratio": body / full,
        "upper_ratio": upper / full,
        "lower_ratio": lower / full,
        "is_bull": row['Close'] > row['Open']
    }

def is_doji(row):
    f = get_candle_features(row)
    return f and f['body_ratio'] <= 0.1

def is_long_upper_shadow(row):
    f = get_candle_features(row)
    return f and f['upper_ratio'] >= 0.6 and f['body_ratio'] <= 0.3

def is_long_lower_shadow(row):
    f = get_candle_features(row)
    return f and f['lower_ratio'] >= 0.6 and f['body_ratio'] <= 0.3

def detect_xianren(df):
    """判斷仙人指路型態"""
    if len(df) < 15:
        return False

    recent = df.iloc[-10:]
    prev = df.iloc[-20:-10]

    uptrend = (prev['Close'].iloc[-1] / prev['Close'].iloc[0]) > 1.1
    last = recent.iloc[-1]
    f = get_candle_features(last)
    if not f:
        return False

    small_body = f['body_ratio'] < 0.3
    long_upper = f['upper_ratio'] > 0.5
    vol_shrink = last['Volume'] < recent['Volume'].mean()

    return uptrend and small_body and long_upper and vol_shrink

def candle_bias_score(row):
    """偏多/偏空結構分數"""
    f = get_candle_features(row)
    if not f:
        return 0

    score = 0
    if f['lower_ratio'] > 0.4:
        score += 1
    if f['is_bull'] and f['body_ratio'] > 0.3:
        score += 1
    if f['upper_ratio'] > 0.4:
        score -= 1
    if not f['is_bull'] and f['body_ratio'] > 0.3:
        score -= 1
    if f['body_ratio'] < 0.1:  # 十字線降權
        score *= 0.5
    return score

def detect_candlestick_patterns(df, lookback=5):
    """整合型態分析"""
    if df.empty or len(df) < lookback:
        return {}

    recent = df.iloc[-lookback:]
    doji_cnt = long_upper_cnt = long_lower_cnt = bias_score = 0

    for _, row in recent.iterrows():
        if is_doji(row):
            doji_cnt += 1
        if is_long_upper_shadow(row):
            long_upper_cnt += 1
        if is_long_lower_shadow(row):
            long_lower_cnt += 1
        bias_score += candle_bias_score(row)

    xianren = detect_xianren(df)

    # 狀態解讀
    if bias_score >= 3:
        overall = "bullish"
        meaning = "K 線結構偏多，低檔承接力較強"
    elif bias_score <= -3:
        overall = "bearish"
        meaning = "K 線結構偏空，高檔賣壓明顯"
    else:
        overall = "neutral"
        meaning = "K 線結構偏中性，等待方向"

    return {
        "lookback_days": lookback,
        "bias_score": bias_score,
        "overall_bias": overall,
        "meaning": meaning,
        "details": {
            "doji_days": doji_cnt,
            "long_upper_days": long_upper_cnt,
            "long_lower_days": long_lower_cnt,
            "xianren": xianren
        }
    }
