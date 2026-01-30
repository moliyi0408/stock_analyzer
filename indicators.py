# Indicator Layer（技術指標層）
import pandas as pd

def add_moving_averages(df):
    """
    計算 MA5 / MA20 / MA60
    """
    df = df.copy()
    df['MA5'] = df['Close'].rolling(5).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA60'] = df['Close'].rolling(60).mean()
    return df

# RSI 計算
def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# 計算起漲區
def get_starting_zone(df, window=20):
    if df.empty or len(df) < window:
        print(f"⚠ 資料不足 ({len(df)} 筆)，無法計算起漲區")
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
        print("⚠ 起漲區計算失敗")
        return None, None

    return round(zone_start,2), round(zone_end,2)

# 計算賣出區間
def get_selling_zone(start_low, start_high, profit_ratio=0.3):
    if start_low is None or start_high is None:
        return None, None
    sell_low = round(start_high * (1 + profit_ratio*0.8),2)
    sell_high = round(start_high * (1 + profit_ratio),2)
    return sell_low, sell_high

# 計算支撐壓力區
def get_support_resistance(df, bin_size=5, top_n=3):
    if df.empty:
        print("⚠ 無資料計算支撐/壓力")
        return [], []

    close_prices = df['Close'].dropna()
    current_price = close_prices.iloc[-1]

    min_price = close_prices.min()
    max_price = close_prices.max()

    bins = list(range(int(min_price//bin_size)*bin_size, int(max_price//bin_size + 2)*bin_size, bin_size))
    hist = pd.cut(close_prices, bins=bins).value_counts().sort_values(ascending=False)
    top_bins = hist.head(top_n).index.tolist()
    
    #先用「成交密集區」找區間，再依歷史位置分類
    mid_price = close_prices.mean()
    support = sorted([b.left for b in top_bins if b.right <= mid_price])
    resistance = sorted([b.right for b in top_bins if b.left >= mid_price])

    return support, resistance

# 計算市場過熱指數核心
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
        # 接近壓力區（±3%）
        if abs(current_price - r) / r < 0.03:
            pressure_score = max(pressure_score, 15)
        # 已突破主要壓力
        if current_price > r:
            pressure_score = max(pressure_score, 20)

    # 總分
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
