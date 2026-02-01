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
def get_support_resistance_zones(
    df,
    bin_size=5,
    density_ratio=0.6,
    fallback_include_all=True
):
    """
    回傳支撐 / 壓力「區間」，防呆版
    """
    if df.empty or 'Close' not in df.columns:
        return {"support": [], "resistance": []}

    # 強制轉 float，過濾掉 NaN / 非數值
    close = pd.to_numeric(df['Close'], errors='coerce').dropna()
    if close.empty:
        return {"support": [], "resistance": []}

    min_p, max_p = close.min(), close.max()

    # 建立價格分箱
    bins = list(range(
        int(min_p // bin_size) * bin_size,
        int(max_p // bin_size + 2) * bin_size,
        bin_size
    ))

    hist = pd.cut(close, bins=bins).value_counts()

    max_count = hist.max()
    dense_bins = hist[hist >= max_count * density_ratio]

    mid_price = close.mean()

    support, resistance = [], []

    for b in hist.index:
        zone = (round(b.left, 2), round(b.right, 2))
        if b in dense_bins.index:
            if b.right <= mid_price:
                support.append(zone)
            elif b.left >= mid_price:
                resistance.append(zone)
        else:
            if fallback_include_all:
                if b.right <= mid_price:
                    support.append(zone)
                elif b.left >= mid_price:
                    resistance.append(zone)

    return {
        "support": sorted(support),
        "resistance": sorted(resistance)
    }

def get_multi_level_support_resistance(df):
    """
    多層級（多批資金）支撐 / 壓力
    """
    levels = {
        "short_term": 60,   # 短線資金 最近 60 根
        "swing": 120,       # 波段資金 最近 120 根
        "long_term": 250    # 長線資金 最近 250 根
    }

    result = {}

    for level, lookback in levels.items():
        sub_df = df.iloc[-lookback:] if len(df) >= lookback else df

        # bin_size 用波動自適應
        bin_size = max(1, int(sub_df['Close'].std()))

        zones = get_support_resistance_zones(
            sub_df,
            bin_size=bin_size
        )

        result[level] = zones

    return result


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
