def determine_trend(close, ma20, ma60):
    if close > ma20 and ma20 > ma60:
        return "多頭趨勢"
    elif close < ma20 and ma20 < ma60:
        return "空頭趨勢"
    else:
        return "盤整趨勢"

def determine_position(close, start_low, start_high, sell_low, sell_high):
    if start_low is not None and start_high is not None and close <= start_high:
        return "起漲區（低風險）"
    elif sell_low is not None and sell_high is not None and close < sell_low:
        return "延伸段（趨勢續航）"
    elif sell_low is not None and sell_high is not None:
        return "壓力區（派發風險）"
    else:
        return "未知"

def determine_ma5_status(df, ma5, close):
    if 'MA5' in df.columns:
        last_5 = df.tail(5)
        ma5_up_days = (last_5['Close'] > last_5['MA5']).sum()
        if close > ma5 and ma5_up_days >= 3:
            return "站穩（短線安全）"
        elif close > ma5:
            return "試探（需觀察）"
        else:
            return "跌破（短線轉弱）"
    return "未知"

def determine_market_temp(heat_score):
    if heat_score < 20:
        return "冷靜（可布局）"
    elif heat_score < 50:
        return "正常"
    elif heat_score < 70:
        return "偏熱（避免追價）"
    else:
        return "過熱（高風險）"
