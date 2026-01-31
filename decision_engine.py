import pandas as pd
from indicators import calculate_ma, detect_candlestick_patterns, get_support_resistance
from analysis import judge_market_state, calculate_overheat

def decision_engine(df, start_zone=(None, None), sell_zone=(None, None), macro_risk=0, chip_strength=0):
    """
    全方位決策引擎（重構 + 防呆版）
    
    df: DataFrame，需包含 Close, Open, High, Low, Volume
    start_zone, sell_zone: tuple (low, high) 起漲區 & 賣出區
    macro_risk: 總經面風險（0~100）
    chip_strength: 籌碼承接分數（-10~10）
    """

    if df is None or df.empty:
        raise ValueError("DataFrame is empty or None, cannot perform decision analysis")

    # 防呆欄位
    required_cols = ['Close','Open','High','Low','Volume']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"DataFrame missing required column: {col}")

    close = df['Close'].iloc[-1]

    # ---------- 1️⃣ 計算均線 ----------
    ma_dict = calculate_ma(df)  # dict of 最新值
    ma5 = ma_dict.get('MA5', close)
    ma20 = ma_dict.get('MA20', close)
    ma60 = ma_dict.get('MA60', close)
    ma200 = ma_dict.get('MA200', close)

    # ---------- 2️⃣ 趨勢判斷 ----------
    if close > ma20 and ma20 > ma60:
        trend = "多頭趨勢"
    elif close < ma20 and ma20 < ma60:
        trend = "空頭趨勢"
    else:
        trend = "盤整趨勢"

    # ---------- 3️⃣ 價格位置 ----------
    start_low, start_high = start_zone
    sell_low, sell_high = sell_zone

    position = "未知"
    if start_low is not None and start_high is not None and close <= start_high:
        position = "起漲區（低風險）"
    elif sell_low is not None and sell_high is not None and close < sell_low:
        position = "延伸段（趨勢續航）"
    elif sell_low is not None and sell_high is not None:
        position = "壓力區（派發風險）"

    # ---------- 4️⃣ 五日線狀態 ----------
    if 'MA5' in df.columns:
        last_5 = df.tail(5)
        ma5_up_days = (last_5['Close'] > last_5['MA5']).sum()
        if close > ma5 and ma5_up_days >= 3:
            ma5_status = "站穩（短線安全）"
        elif close > ma5:
            ma5_status = "試探（需觀察）"
        else:
            ma5_status = "跌破（短線轉弱）"
    else:
        ma5_status = "未知"

    # ---------- 5️⃣ 市場溫度 ----------
    heat_score = calculate_overheat(df)
    if heat_score < 20:
        market_temp = "冷靜（可布局）"
    elif heat_score < 50:
        market_temp = "正常"
    elif heat_score < 70:
        market_temp = "偏熱（避免追價）"
    else:
        market_temp = "過熱（高風險）"

    # ---------- 6️⃣ 結構層分析 ----------
    patterns = detect_candlestick_patterns(df)
    support_list, resistance_list = get_support_resistance(df)
    support_level = support_list[-1] if support_list else None
    resistance_level = resistance_list[-1] if resistance_list else None

    # ---------- 7️⃣ 行為層分析 ----------
    behavior, behavior_reasons = judge_market_state(df, support_level, {'total': heat_score}, patterns)

    # ---------- 8️⃣ 操作建議 ----------
    stop_loss_price = min(df['Close'].iloc[-2:].min(), support_level if support_level else close*0.9)
    take_profit_price = sell_high if sell_high else close*1.2

    # 分批加碼建議
    add_targets = []
    if start_low is not None:
        add_targets = [round(start_low * pct,2) for pct in [0.95, 0.90]]
        if chip_strength > 3:
            add_targets = [round(t*0.98,2) for t in add_targets]

    # 減碼參考價位
    reduce_target = ma5

    # 持有者策略文字
    if trend == "多頭趨勢" and ma5_status != "跌破（短線轉弱）":
        hold_advice = f"續抱，跌破 5 日線減碼至 {reduce_target:.2f}"
    elif ma5_status.startswith("跌破"):
        hold_advice = f"反彈減碼，控管風險，停損點 {stop_loss_price:.2f}"
    else:
        hold_advice = "保守觀察"

    # 空手者策略文字
    if position == "起漲區（低風險）":
        entry_advice = f"可分批布局，目標加碼價 {add_targets}"
    elif position == "延伸段（趨勢續航）":
        entry_advice = f"等待拉回 5 日線 ({ma5:.2f})"
    else:
        entry_advice = "不追高，等待修正"

    return {
        "trend": trend,
        "position": position,
        "ma5_status": ma5_status,
        "market_temp": market_temp,
        "heat_score": heat_score,
        "behavior": behavior,
        "behavior_reasons": behavior_reasons,
        "hold_advice": hold_advice,
        "reduce_target": reduce_target,
        "entry_advice": entry_advice,
        "add_targets": add_targets,
        "stop_loss": stop_loss_price,
        "take_profit": take_profit_price,
        "patterns": patterns,
        "support_level": support_level,
        "resistance_level": resistance_level
    }
