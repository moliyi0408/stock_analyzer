# patterns.py Pattern & Structure Layer（結構層）

# 基礎 K 線結構
def get_candle_features(row):
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

# 十字線
def is_doji(row):
    f = get_candle_features(row)
    return f['body_ratio'] <= 0.1

# 長上影線
def is_long_upper_shadow(row):
    f = get_candle_features(row)
    return f['upper_ratio'] >= 0.6 and f['body_ratio'] <= 0.3

# 長下影線
def is_long_lower_shadow(row):
    f = get_candle_features(row)
    return f['lower_ratio'] >= 0.6 and f['body_ratio'] <= 0.3

# 仙人指路
def detect_xianren(df):
    if len(df) < 15:
        return False

    recent = df.iloc[-10:]
    prev = df.iloc[-20:-10]

    # 條件 A：前段上漲
    uptrend = (prev['Close'].iloc[-1] / prev['Close'].iloc[0]) > 1.1

    # 條件 B：整理 K
    last = recent.iloc[-1]
    f = get_candle_features(last)

    if not f:
        return False

    small_body = f['body_ratio'] < 0.3
    long_upper = f['upper_ratio'] > 0.5

    # 條件 C：量縮
    vol_shrink = last['Volume'] < recent['Volume'].mean()

    return uptrend and small_body and long_upper and vol_shrink

def candle_bias_score(row):
    f = get_candle_features(row)
    if not f:
        return 0

    score = 0

    # 偏多結構
    if f['lower_ratio'] > 0.4:
        score += 1
    if f['is_bull'] and f['body_ratio'] > 0.3:
        score += 1

    # 偏空結構
    if f['upper_ratio'] > 0.4:
        score -= 1
    if not f['is_bull'] and f['body_ratio'] > 0.3:
        score -= 1

    # 十字線降權
    if f['body_ratio'] < 0.1:
        score *= 0.5

    return score

# 型態分析模組
def detect_candlestick_patterns(df, lookback=5):
    if df.empty or len(df) < lookback:
        return {}

    recent = df.iloc[-lookback:]

    doji_cnt = 0
    long_upper_cnt = 0
    long_lower_cnt = 0
    bias_score = 0

    for _, row in recent.iterrows():
        if is_doji(row):
            doji_cnt += 1
        if is_long_upper_shadow(row):
            long_upper_cnt += 1
        if is_long_lower_shadow(row):
            long_lower_cnt += 1

        bias_score += candle_bias_score(row)

    # 仙人指路（仍然保留你的邏輯）
    xianren = detect_xianren(df)

    # === 狀態解讀 ===
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
