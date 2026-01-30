# decision_engine.py
import pandas as pd

def decision_engine(df, start_zone, sell_zone, support, resistance, heat_score, macro_risk=0, chip_strength=0):
    """
    全方位決策引擎
    df: DataFrame
    start_zone, sell_zone: 起漲區 & 賣出區 tuple (low, high)
    support, resistance: 支撐 / 壓力
    heat_score: 市場過熱分數
    macro_risk: 總經面風險（0~100）
    chip_strength: 籌碼承接分數（-10~10）
    """
    close = df['Close'].iloc[-1]
    ma5 = df['MA5'].iloc[-1]
    ma20 = df['MA20'].iloc[-1]
    ma60 = df['MA60'].iloc[-1]
    ma200 = df.get('MA200', pd.Series([close]*len(df))).iloc[-1]

    # ========= 1️⃣ 趨勢判斷 =========
    if close > ma20 and ma20 > ma60:
        trend = "多頭趨勢"
    elif close < ma20 and ma20 < ma60:
        trend = "空頭趨勢"
    else:
        trend = "盤整趨勢"

    # ========= 2️⃣ 價格位置 =========
    start_low, start_high = start_zone
    sell_low, sell_high = sell_zone

    if close <= start_high:
        position = "起漲區（低風險）"
    elif close < sell_low:
        position = "延伸段（趨勢續航）"
    else:
        position = "壓力區（派發風險）"

    # ========= 3️⃣ 五日線狀態 =========
    last_5 = df.tail(5)
    ma5_up_days = (last_5['Close'] > last_5['MA5']).sum()

    if close > ma5 and ma5_up_days >= 3:
        ma5_status = "站穩（短線安全）"
    elif close > ma5:
        ma5_status = "試探（需觀察）"
    else:
        ma5_status = "跌破（短線轉弱）"

    # ========= 4️⃣ 市場溫度 =========
    if heat_score < 20:
        market_temp = "冷靜（可布局）"
    elif heat_score < 50:
        market_temp = "正常"
    elif heat_score < 70:
        market_temp = "偏熱（避免追價）"
    else:
        market_temp = "過熱（高風險）"

    # ========= 5️⃣ 行為風險 =========
    long_upper = (df['High'] - df[['Open', 'Close']].max(axis=1)) > \
                 (df[['Open', 'Close']].max(axis=1) - df['Low']) * 1.5
    recent_upper = long_upper.tail(5).sum()

    if recent_upper >= 2 and close < ma5:
        behavior = "出貨疑慮"
    elif close < ma5:
        behavior = "洗盤可能"
    else:
        behavior = "結構正常"

    # ========= 6️⃣ 操作建議 =========
    stop_loss = min(df['Close'].iloc[-2:].min(), support[0] if support else close*0.9)
    take_profit = sell_high if sell_high is not None else close*1.2

    # 分批加碼建議（跌破前低 5%、10%）
    add_targets = [round(start_low * pct,2) for pct in [0.95, 0.90]]
    if chip_strength > 3:
        add_targets = [round(t*0.98,2) for t in add_targets]  # 籌碼強，提前加碼

    # 減碼參考價位
    reduce_target = ma5  # 反彈到 MA5 減碼

    # 持有者策略文字
    if trend == "多頭趨勢" and ma5_status != "跌破（短線轉弱）":
        hold_advice = f"續抱，跌破 5 日線減碼至 {reduce_target:.2f}"
    elif ma5_status.startswith("跌破"):
        hold_advice = f"反彈減碼，控管風險，停損點 {stop_loss:.2f}"
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
        "behavior": behavior,
        "hold_advice": hold_advice,
        "reduce_target": reduce_target,
        "entry_advice": entry_advice,
        "add_targets": add_targets,
        "stop_loss": stop_loss,
        "take_profit": take_profit
    }
