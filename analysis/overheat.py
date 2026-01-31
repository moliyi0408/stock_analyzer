# analysisoverheat.py

def market_temperature(rsi):
    if rsi > 70:
        return "過熱（高風險）"
    elif rsi < 30:
        return "低溫（超賣）"
    else:
        return "冷靜（可布局）"

def calculate_overheat(df):
    """
    市場溫度分數 0~100
    使用簡單 RSI 或價格漲幅 proxy
    """
    if len(df) < 14:
        return 50  # 中性
    
    recent = df['Close'].iloc[-14:]
    change = recent.pct_change().fillna(0)
    up = change[change > 0].sum()
    down = abs(change[change < 0].sum())
    
    score = (up / (up + down)) * 100 if (up + down) > 0 else 50
    return min(max(score, 0), 100)
