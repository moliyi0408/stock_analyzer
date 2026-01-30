# Behavior Layer（行為層）

def rebound_strength(df, lookback=3):
    if len(df) < lookback + 2:
        return 0
    recent = df.iloc[-lookback-1:]
    drop = recent['Close'].iloc[-2] - recent['Close'].iloc[-3]
    rebound = recent['Close'].iloc[-1] - recent['Close'].iloc[-2]
    if drop >= 0:
        return 0
    return rebound / abs(drop)

def selling_pressure(df, lookback=5):
    recent = df.iloc[-lookback:]
    down = recent[recent['Close'] < recent['Open']]['Volume']
    up = recent[recent['Close'] > recent['Open']]['Volume']
    if len(down) == 0 or len(up) == 0:
        return 1
    return down.mean() / up.mean()

def support_reclaim(df, support_level, tolerance=0.02):
    if len(df) < 2 or support_level is None:
        return False
    prev = df.iloc[-2]
    last = df.iloc[-1]
    broke = prev['Close'] < support_level
    reclaim = last['Close'] > support_level * (1 - tolerance)
    return broke and reclaim

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
    if patterns and patterns['overall_bias'] == 'bullish':
        score += 1
        reasons.append("K 線結構偏多")
    if overheat and overheat['total'] > 60:
        score -= 1
        reasons.append("市場過熱，高檔風險")

    if score >= 3:
        return "洗盤偏多，可續抱", reasons
    elif score <= 0:
        return "出貨風險升高，反彈減碼", reasons
    else:
        return "震盪整理，觀察為主", reasons
