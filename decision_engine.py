import pandas as pd
from indicators import (
    calculate_ma,
    detect_candlestick_patterns,
    get_support_resistance,
    get_multi_level_support_resistance,
    get_starting_zone,
    get_selling_zone
)
from analysis import judge_market_state, calculate_overheat, classify_market_zone


def _to_float_or_none(value):
    """Normalize a scalar to float, invalid values become None."""
    if value is None:
        return None
    v = pd.to_numeric(pd.Series([value]), errors='coerce').iloc[0]
    if pd.isna(v):
        return None
    return float(v)


# ---------------- 防呆 / 輔助函數 ----------------
def safe_dataframe(df: pd.DataFrame):
    if df is None or df.empty:
        raise ValueError("DataFrame is empty or None")
    required_cols = ['Close', 'Open', 'High', 'Low', 'Volume']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"DataFrame missing required column: {col}")
    return df


def safe_start_zone(df: pd.DataFrame, start_zone=(None, None)):
    start_low, start_high = start_zone
    if start_low is None or start_high is None:
        start_low, start_high = get_starting_zone(df)
    return _to_float_or_none(start_low), _to_float_or_none(start_high)


def safe_sell_zone(start_low, start_high, sell_zone=(None, None)):
    sell_low, sell_high = sell_zone
    if sell_low is None or sell_high is None:
         sell_low, sell_high = get_selling_zone(start_low, start_high)
    return _to_float_or_none(sell_low), _to_float_or_none(sell_high)

def determine_trend(close, ma20, ma60):
    close = _to_float_or_none(close)
    ma20 = _to_float_or_none(ma20)
    ma60 = _to_float_or_none(ma60)

    if close is None or ma20 is None or ma60 is None:
        return "趨勢資料不足"
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
    ma5 = _to_float_or_none(ma5)
    close = _to_float_or_none(close)

    if ma5 is None or close is None:
        return "均線資料不足"

    if 'MA5' in df.columns:
        last_5 = df.tail(5)
        ma5_up_days = (last_5['Close'] > last_5['MA5']).sum()
        if close > ma5 and ma5_up_days >= 3:
            return "站穩（短線安全）"
        elif close > ma5:
            return "試探（需觀察）"
        else:
            return "跌破（短線轉弱）"
    else:
        return "未知"


def determine_market_temp(heat_score):
    heat_score = _to_float_or_none(heat_score)
    if heat_score is None:
        return "未知"

    if heat_score < 20:
        return "冷靜（可布局）"
    elif heat_score < 50:
        return "正常"
    elif heat_score < 70:
        return "偏熱（避免追價）"
    else:
        return "過熱（高風險）"


def get_latest_support_resistance(df):
    support_list, resistance_list = get_support_resistance(df)
    support_level = support_list[-1] if support_list else None
    resistance_level = resistance_list[-1] if resistance_list else None
    return _to_float_or_none(support_level), _to_float_or_none(resistance_level)

def infer_support_resistance_from_zones(multi_zones, close):
    close = _to_float_or_none(close)
    if close is None or not isinstance(multi_zones, dict):
        return None, None

    supports = []
    resistances = []
    for zones in multi_zones.values():
        for low, high in zones.get("support", []):
            low = _to_float_or_none(low)
            high = _to_float_or_none(high)
            if low is not None and high is not None:
                supports.append((low, high))
        for low, high in zones.get("resistance", []):
            low = _to_float_or_none(low)
            high = _to_float_or_none(high)
            if low is not None and high is not None:
                resistances.append((low, high))

    support_level = max((high for _, high in supports if high <= close), default=None)
    resistance_level = min((low for low, _ in resistances if low >= close), default=None)
    return support_level, resistance_level


def determine_add_targets(start_low, chip_strength):
    if start_low is None:
        return []
    add_targets = [round(start_low * pct, 2) for pct in [0.95, 0.90]]
    if chip_strength > 3:
        add_targets = [round(t * 0.98, 2) for t in add_targets]
    return add_targets


def generate_advice(df, trend, ma5_status, position, ma5, start_low, sell_high, chip_strength, support_level, resistance_level):
    ma5 = _to_float_or_none(ma5)
    stop_loss_price = min(df['Close'].iloc[-2:].min(), support_level if support_level else df['Close'].iloc[-1]*0.9)
    take_profit_price = sell_high if sell_high is not None else (resistance_level if resistance_level is not None else df['Close'].iloc[-1]*1.2)
    add_targets = determine_add_targets(start_low, chip_strength)
    reduce_target = ma5

    # 持有者策略
    if trend == "多頭趨勢" and ma5_status != "跌破（短線轉弱）":
        hold_advice = f"續抱，跌破 5 日線減碼至 {reduce_target:.2f}" if reduce_target is not None else "續抱，但均線資料不足請保守"
    elif ma5_status.startswith("跌破"):
        hold_advice = f"反彈減碼，控管風險，停損點 {stop_loss_price:.2f}"
    else:
        hold_advice = "保守觀察"

    # 空手者策略
    if position == "起漲區（低風險）":
        entry_advice = f"可分批布局，目標加碼價 {add_targets}"
    elif position == "延伸段（趨勢續航）":
        entry_advice = f"等待拉回 5 日線 ({ma5:.2f})" if ma5 is not None else "等待均線資料完整後再評估"
    else:
        entry_advice = "不追高，等待修正"

    return stop_loss_price, take_profit_price, add_targets, reduce_target, hold_advice, entry_advice


# ---------------- 決策引擎主函數 ----------------
def decision_engine(df, start_zone=(None, None), sell_zone=(None, None), macro_risk=0, chip_strength=0):
    df = safe_dataframe(df)
    close = _to_float_or_none(df['Close'].iloc[-1])
    if close is None:
        raise ValueError("最新 Close 值無效，無法分析")

    # 直接從 df 取均線
    ma5 = _to_float_or_none(df['MA5'].iloc[-1]) if 'MA5' in df.columns else close
    ma20 = _to_float_or_none(df['MA20'].iloc[-1]) if 'MA20' in df.columns else close
    ma60 = _to_float_or_none(df['MA60'].iloc[-1]) if 'MA60' in df.columns else close

    # 趨勢判斷
    trend = determine_trend(close, ma20, ma60)

    # 起漲區 & 賣出區防呆
    start_low, start_high = safe_start_zone(df, start_zone)
    sell_low, sell_high = safe_sell_zone(start_low, start_high, sell_zone)

    # 價格位置
    position = determine_position(close, start_low, start_high, sell_low, sell_high)

    # 五日線狀態
    ma5_status = determine_ma5_status(df, ma5, close)

    # 市場溫度
    heat_score = calculate_overheat(df)
    market_temp = determine_market_temp(heat_score)

    # K線結構 & 支撐壓力
    patterns = detect_candlestick_patterns(df)
    support_level, resistance_level = get_latest_support_resistance(df)
    multi_zones = get_multi_level_support_resistance(df)
    market_zone_status = classify_market_zone(close, multi_zones)

    # 行為層分析
    behavior, behavior_reasons = judge_market_state(
            df,
            support_level,
            {'total': heat_score, 'zones': multi_zones},
            patterns,
            zones=multi_zones
        )
    # 操作建議
    stop_loss_price, take_profit_price, add_targets, reduce_target, hold_advice, entry_advice = generate_advice(
            df, trend, ma5_status, position, ma5, start_low, sell_high, chip_strength, support_level, resistance_level
        )

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

        "stop_loss": stop_loss_price,
        "take_profit": take_profit_price,
        "patterns": patterns,
        "support_level": support_level,
        "resistance_level": resistance_level,
        "multi_zones": multi_zones,
        "market_zone_status": market_zone_status
    }
