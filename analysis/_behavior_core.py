# analysis/_behavior_core.py

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
