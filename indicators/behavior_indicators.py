# indicators/behavior_indicators.py

import pandas as pd

def rebound_strength(df):
    if len(df) < 4:
        return 0.0
    recent = df['Close'].iloc[-3:]
    prev_drop = df['Close'].iloc[-4] - df['Close'].iloc[-3]
    if prev_drop <= 0:
        return 0.0
    rebound = (recent.max() - recent.min()) / prev_drop
    return min(rebound, 1.0)

def selling_pressure(df):
    if 'Volume' not in df.columns or len(df) < 2:
        return 1.0
    recent_vol = df['Volume'].iloc[-3:].mean()
    prev_vol = df['Volume'].iloc[-4:-1].mean()
    if prev_vol == 0:
        return 1.0
    return recent_vol / prev_vol

def support_reclaim(df, support):
    if len(df) < 2:
        return False
    close = df['Close'].iloc[-1]
    prev_close = df['Close'].iloc[-2]
    return prev_close < support <= close
