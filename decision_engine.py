import pandas as pd
from indicators import (
    calculate_ma,
    detect_candlestick_patterns,
    get_support_resistance,
    get_multi_level_support_resistance,
    get_starting_zone,
    get_selling_zone,
    calc_volume_baseline,
    detect_volume_state,
    detect_price_volume_pattern,
    calc_rsi,
    calc_macd,
    calc_bollinger_bands,
    calc_atr,
)
from analysis import judge_market_state, calculate_overheat, classify_market_zone
from strategy.exit import build_exit_plan
from strategy.position import calc_position_size


def _to_float_or_none(value):
    """Normalize a scalar to float, invalid values become None."""
    if value is None:
        return None
    v = pd.to_numeric(pd.Series([value]), errors='coerce').iloc[0]
    if pd.isna(v):
        return None
    return float(v)


def build_weekly_trend(df: pd.DataFrame):
    if df is None or df.empty or 'Date' not in df.columns:
        return "資料不足"

    weekly = df.copy()
    weekly['Date'] = pd.to_datetime(weekly['Date'], errors='coerce')
    weekly = weekly.dropna(subset=['Date']).sort_values('Date').set_index('Date')
    if weekly.empty:
        return "資料不足"

    week_df = weekly.resample('W-FRI').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum',
    }).dropna(subset=['Close'])
    if len(week_df) < 20:
        return "資料不足"

    ma20 = week_df['Close'].rolling(20).mean().iloc[-1]
    close = week_df['Close'].iloc[-1]
    if close > ma20:
        return "週K多頭"
    return "週K空頭"


def build_indicator_resonance(df: pd.DataFrame, support_level):
    close = _to_float_or_none(df['Close'].iloc[-1]) if 'Close' in df.columns else None
    if close is None:
        return {"signals": [], "score": 0, "label": "資料不足"}

    signals = []
    score = 0

    rsi = calc_rsi(df).iloc[-1] if len(df) >= 15 else None
    macd_df = calc_macd(df)
    bb_df = calc_bollinger_bands(df)

    macd = _to_float_or_none(macd_df['MACD'].iloc[-1]) if not macd_df.empty else None
    macd_signal = _to_float_or_none(macd_df['MACD_signal'].iloc[-1]) if not macd_df.empty else None
    bb_lower = _to_float_or_none(bb_df['BB_lower'].iloc[-1]) if not bb_df.empty else None

    if rsi is not None and rsi <= 35:
        signals.append("RSI偏低")
        score += 1
    if None not in (macd, macd_signal) and macd > macd_signal:
        signals.append("MACD黃金交叉")
        score += 1
    if bb_lower is not None and close <= bb_lower * 1.02:
        signals.append("接近布林下軌")
        score += 1
    if support_level is not None and close <= support_level * 1.02:
        signals.append("接近支撐")
        score += 1

    if score >= 3:
        label = "多指標共振（偏多）"
    elif score == 2:
        label = "部分共振（中性偏多）"
    else:
        label = "共振不足"

    return {"signals": signals, "score": score, "label": label}


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


def infer_support_resistance_from_history(df: pd.DataFrame, close, lookback=120):
    """
    當區間推導不到有效支撐/壓力時，使用近期高低點估算最近的上下緣價位。
    """
    close = _to_float_or_none(close)
    if close is None or df is None or df.empty:
        return None, None

    window_df = df.tail(lookback) if lookback and lookback > 0 else df

    support_level = None
    resistance_level = None

    if 'Low' in window_df.columns:
        lows = pd.to_numeric(window_df['Low'], errors='coerce').dropna()
        below_close = lows[lows <= close]
        if not below_close.empty:
            support_level = _to_float_or_none(below_close.max())

    if 'High' in window_df.columns:
        highs = pd.to_numeric(window_df['High'], errors='coerce').dropna()
        above_close = highs[highs >= close]
        if not above_close.empty:
            resistance_level = _to_float_or_none(above_close.min())

    return support_level, resistance_level


def build_dynamic_price_zone(level, atr, fallback_buffer=0.01):
    level = _to_float_or_none(level)
    atr = _to_float_or_none(atr)
    if level is None:
        return None

    buffer_size = atr if atr is not None and atr > 0 else level * fallback_buffer
    lower = round(level - buffer_size, 2)
    upper = round(level + buffer_size, 2)
    return [min(lower, upper), max(lower, upper)]


def detect_market_structure(df: pd.DataFrame, window=10):
    if df is None or len(df) < window * 2 or 'High' not in df.columns or 'Low' not in df.columns:
        return {
            "structure": "資料不足",
            "interpretation": "樣本不足，無法判斷市場結構",
            "higher_high": None,
            "higher_low": None,
        }

    highs = pd.to_numeric(df['High'], errors='coerce')
    lows = pd.to_numeric(df['Low'], errors='coerce')

    recent_high = _to_float_or_none(highs.iloc[-window:].max())
    prev_high = _to_float_or_none(highs.iloc[-window * 2:-window].max())
    recent_low = _to_float_or_none(lows.iloc[-window:].min())
    prev_low = _to_float_or_none(lows.iloc[-window * 2:-window].min())

    if None in (recent_high, prev_high, recent_low, prev_low):
        return {
            "structure": "資料不足",
            "interpretation": "高低點資料缺失，無法判斷",
            "higher_high": None,
            "higher_low": None,
        }

    higher_high = recent_high > prev_high
    higher_low = recent_low > prev_low
    lower_high = recent_high < prev_high
    lower_low = recent_low < prev_low

    if higher_high and higher_low:
        structure = "HH / HL"
        interpretation = "多頭延續"
    elif lower_high and lower_low:
        structure = "LH / LL"
        interpretation = "空頭延續"
    elif higher_high and lower_low:
        structure = "HH / LL"
        interpretation = "高波動轉折，留意假突破"
    elif lower_high and higher_low:
        structure = "LH / HL"
        interpretation = "收斂整理，等待方向"
    else:
        structure = "EQ"
        interpretation = "區間震盪"

    return {
        "structure": structure,
        "interpretation": interpretation,
        "higher_high": higher_high,
        "higher_low": higher_low,
    }


def build_confidence_breakdown(scorecard, patterns, heat_score, market_trend):
    base_score = 50
    trend_part = round(((scorecard.get("trend_score") or 50) - 50) * 0.35, 2)
    volume_part = round(((scorecard.get("volume_structure_score") or 50) - 50) * 0.30, 2)

    pattern_bias = (patterns or {}).get("overall_bias", "neutral")
    candle_part = {
        "bullish": 8,
        "neutral": 0,
        "bearish": -8,
    }.get(pattern_bias, 0)

    heat_part = 4
    if heat_score >= 70:
        heat_part = -12
    elif heat_score >= 50:
        heat_part = -6
    elif heat_score >= 20:
        heat_part = 0

    market_filter_part = {"多頭": 4, "中性": 0, "空頭": -6}.get(market_trend, 0)
    chip_part = round(((scorecard.get("chip_score") or 50) - 50) * 0.20, 2)

    total = round(
        base_score
        + trend_part
        + volume_part
        + candle_part
        + heat_part
        + market_filter_part
        + chip_part,
        2,
    )

    return {
        "基準分": base_score,
        "趨勢權重": trend_part,
        "量價結構": volume_part,
        "K線結構": candle_part,
        "市場溫度": heat_part,
        "大盤濾網": market_filter_part,
        "籌碼": chip_part,
        "總分": max(0, min(100, total)),
    }


def calculate_rr_metrics(entry_price, stop_loss, take_profit, min_rr=1.5):
    entry_price = _to_float_or_none(entry_price)
    stop_loss = _to_float_or_none(stop_loss)
    take_profit = _to_float_or_none(take_profit)

    if None in (entry_price, stop_loss, take_profit):
        return {"risk": None, "reward": None, "rr": None, "rr_threshold": min_rr, "rr_pass": False}

    risk = round(entry_price - stop_loss, 4)
    reward = round(take_profit - entry_price, 4)

    if risk <= 0:
        return {"risk": risk, "reward": reward, "rr": None, "rr_threshold": min_rr, "rr_pass": False}

    rr = round(reward / risk, 2)
    return {
        "risk": risk,
        "reward": reward,
        "rr": rr,
        "rr_threshold": min_rr,
        "rr_pass": rr >= min_rr,
    }


def determine_add_targets(start_low, chip_strength):
    if start_low is None:
        return []
    add_targets = [round(start_low * pct, 2) for pct in [0.95, 0.90]]
    if chip_strength > 3:
        add_targets = [round(t * 0.98, 2) for t in add_targets]
    return add_targets


def build_buy_recommendation(close, support_level, start_low, final_score, position, trend):
    """建立可直接下單參考的買入建議價位（分批）。"""
    close = _to_float_or_none(close)
    support_level = _to_float_or_none(support_level)
    start_low = _to_float_or_none(start_low)

    if close is None:
        return {
            "strategy": "資料不足，無法提供買入價位",
            "tiers": [],
            "risk_note": "請確認行情資料完整後再評估",
            "preferred_buy_zone": None,
        }

    # 以「接近現價且不追高」為原則，避免回傳高於現價的加碼點
    primary_anchor = support_level if support_level is not None else (start_low if start_low is not None else close)
    # 若錨點高於現價，代表可能已跌破原支撐，改用現價附近折價做承接
    if primary_anchor > close:
        primary_anchor = close * 0.99

    aggressive = final_score >= 75 and position == "起漲區（低風險）" and trend == "多頭趨勢"
    if aggressive:
        percents = [1.00, 0.97, 0.94]
        strategy = "偏積極分批布局"
    elif final_score >= 60:
        percents = [0.99, 0.96, 0.92]
        strategy = "中性分批承接"
    else:
        percents = [0.98, 0.94]
        strategy = "保守等待，不追價"

    tiers = []
    for idx, pct in enumerate(percents, start=1):
        price = round(primary_anchor * pct, 2)
        if price <= close * 1.01:  # 防止建議價偏離現價過高
            tiers.append({"batch": idx, "price": price})

    # 避免重複/逆序
    dedup_prices = []
    for tier in tiers:
        if tier["price"] not in dedup_prices:
            dedup_prices.append(tier["price"])
    tiers = [{"batch": i + 1, "price": p} for i, p in enumerate(sorted(dedup_prices, reverse=True))]

    preferred_buy_zone = None
    if tiers:
        high = tiers[0]["price"]
        low = tiers[-1]["price"]
        preferred_buy_zone = [low, high]

    risk_note = "若跌破最末買點且無法站回，建議暫停加碼並重新評估"

    return {
        "strategy": strategy,
        "tiers": tiers,
        "risk_note": risk_note,
        "preferred_buy_zone": preferred_buy_zone,
    }


def _score_to_grade(final_score):
    if final_score >= 75:
        return "A", "強"
    if final_score >= 60:
        return "B", "中"
    return "C", "弱"


def _mup_level(score):
    if score >= 80:
        return "高"
    if score >= 60:
        return "中"
    return "低"


def _mup_status(score):
    if score >= 90:
        return "共振啟動", "CONFIRMED"
    if score >= 75:
        return "準主升浪", "READY"
    if score >= 60:
        return "潛力觀察", "WATCHLIST"
    return "無效", "IGNORE"


def build_mup_scorecard(df, scorecard):
    """把主升浪圖形訊號轉成可計算分數，輸出可讀的工程化解釋。"""
    close = _to_float_or_none(df['Close'].iloc[-1]) if 'Close' in df.columns else None
    ma5 = _to_float_or_none(df['MA5'].iloc[-1]) if 'MA5' in df.columns else None
    ma20 = _to_float_or_none(df['MA20'].iloc[-1]) if 'MA20' in df.columns else None
    ma60 = _to_float_or_none(df['MA60'].iloc[-1]) if 'MA60' in df.columns else None
    today_open = _to_float_or_none(df['Open'].iloc[-1]) if 'Open' in df.columns else None
    today_low = _to_float_or_none(df['Low'].iloc[-1]) if 'Low' in df.columns else None
    yesterday_high = _to_float_or_none(df['High'].iloc[-2]) if 'High' in df.columns and len(df) >= 2 else None
    pct_change = _to_float_or_none(df['Close'].pct_change().iloc[-1]) if len(df) >= 2 and 'Close' in df.columns else None
    latest_volume = _to_float_or_none(df['Volume'].iloc[-1]) if 'Volume' in df.columns else None

    max_120 = _to_float_or_none(df['High'].tail(120).max()) if 'High' in df.columns else None
    min_20 = _to_float_or_none(df['Low'].tail(20).min()) if 'Low' in df.columns else None
    max_20 = _to_float_or_none(df['High'].tail(20).max()) if 'High' in df.columns else None
    drawdown = ((max_120 - close) / max_120) if None not in (max_120, close) and max_120 else None
    consolidation_range = ((max_20 - min_20) / min_20) if None not in (max_20, min_20) and min_20 else None

    vol_df = calc_volume_baseline(df.copy())
    avg_volume = _to_float_or_none(vol_df["avg_volume_20"].iloc[-1]) if "avg_volume_20" in vol_df.columns else None
    volume_ratio = (latest_volume / avg_volume) if (latest_volume is not None and avg_volume not in (None, 0)) else None
    vol_3d = _to_float_or_none(df['Volume'].iloc[-4]) if 'Volume' in df.columns and len(df) >= 4 else None
    vol_2d = _to_float_or_none(df['Volume'].iloc[-3]) if 'Volume' in df.columns and len(df) >= 3 else None
    vol_1d = _to_float_or_none(df['Volume'].iloc[-2]) if 'Volume' in df.columns and len(df) >= 2 else None

    is_limit_like = pct_change is not None and pct_change >= 0.095
    gap_up = None not in (today_open, yesterday_high) and today_open > yesterday_high
    gap_not_filled = None not in (today_low, yesterday_high) and today_low > yesterday_high
    above_ma5 = None not in (close, ma5) and close > ma5

    consecutive_up_days = 0
    if 'Close' in df.columns and len(df) >= 2:
        for i in range(len(df) - 1, 0, -1):
            now = _to_float_or_none(df['Close'].iloc[i])
            prev = _to_float_or_none(df['Close'].iloc[i - 1])
            if None in (now, prev) or now <= prev:
                break
            consecutive_up_days += 1

    score_structure = 0
    if drawdown is not None and drawdown >= 0.3:
        score_structure += 8
    if consolidation_range is not None and consolidation_range <= 0.15:
        score_structure += 6
    if is_limit_like:
        score_structure += 6

    score_momentum = 0
    if gap_up:
        score_momentum += 7
    if gap_not_filled:
        score_momentum += 5
    if consecutive_up_days >= 4:
        score_momentum += 5
    if above_ma5:
        score_momentum += 3

    score_volume = 0
    if volume_ratio is not None and volume_ratio >= 2:
        score_volume += 12
    if None not in (vol_3d, vol_2d, vol_1d, latest_volume) and vol_3d < vol_2d < vol_1d < latest_volume:
        score_volume += 8
    if volume_ratio is not None and volume_ratio >= 1.5 and vol_1d is not None and avg_volume is not None and vol_1d >= avg_volume * 1.5:
        score_volume += 5

    score_chip = 0
    chip_base = scorecard.get("chip_score") if isinstance(scorecard, dict) else None
    trend_base = scorecard.get("trend_score") if isinstance(scorecard, dict) else None
    position_base = scorecard.get("position_score") if isinstance(scorecard, dict) else None
    if isinstance(chip_base, (int, float)):
        score_chip += min(12, round(chip_base * 0.12))
    if isinstance(trend_base, (int, float)) and trend_base >= 70:
        score_chip += 4
    if isinstance(position_base, (int, float)) and position_base >= 65:
        score_chip += 4
    score_chip = min(20, score_chip)

    score_risk = 0
    not_overextended = None not in (close, ma5) and ma5 not in (None, 0) and ((close - ma5) / ma5) < 0.1
    if not_overextended:
        score_risk += 5
    if None not in (close, ma20, ma60) and close >= ma20 >= ma60:
        score_risk += 5
    if volume_ratio is not None and volume_ratio < 3.5:
        score_risk += 5

    total_score = score_structure + score_momentum + score_volume + score_chip + score_risk
    total_score = max(0, min(100, round(total_score, 2)))
    status_zh, status_code = _mup_status(total_score)

    missing_conditions = []
    if not (volume_ratio is not None and volume_ratio >= 2):
        missing_conditions.append("放量")
    if not (gap_up and gap_not_filled):
        missing_conditions.append("跳空")
    if consecutive_up_days < 4:
        missing_conditions.append("連陽續攻")
    if score_structure < 12:
        missing_conditions.append("底部結構")
    if score_chip < 12:
        missing_conditions.append("籌碼集中")

    return {
        "structure_score": score_structure,
        "momentum_score": score_momentum,
        "volume_score": score_volume,
        "chip_score": score_chip,
        "risk_score": score_risk,
        "total_score": total_score,
        "score_range": f"{max(0, int(total_score - 5))}~{min(100, int(total_score + 5))}",
        "structure_level": _mup_level(score_structure / 20 * 100 if score_structure is not None else 0),
        "momentum_level": _mup_level(score_momentum / 20 * 100 if score_momentum is not None else 0),
        "volume_level": _mup_level(score_volume / 25 * 100 if score_volume is not None else 0),
        "chip_level": _mup_level(score_chip / 20 * 100 if score_chip is not None else 0),
        "status": status_zh,
        "status_code": status_code,
        "missing_conditions": missing_conditions[:3],
    }


def build_factor_scorecard(df, chip_df=None):
    """建立多因子評分卡，輸出各子分數與總分。"""
    df = safe_dataframe(df)
    chip_source = chip_df if chip_df is not None else df

    close = _to_float_or_none(df['Close'].iloc[-1])
    ma20 = _to_float_or_none(df['MA20'].iloc[-1]) if 'MA20' in df.columns else close
    ma60 = _to_float_or_none(df['MA60'].iloc[-1]) if 'MA60' in df.columns else close

    trend = determine_trend(close, ma20, ma60)
    trend_score = {
        "多頭趨勢": 85,
        "盤整趨勢": 55,
        "空頭趨勢": 25,
        "趨勢資料不足": 45
    }.get(trend, 45)

    start_low, start_high = safe_start_zone(df)
    sell_low, sell_high = safe_sell_zone(start_low, start_high)
    position = determine_position(close, start_low, start_high, sell_low, sell_high)
    position_score = {
        "起漲區（低風險）": 85,
        "延伸段（趨勢續航）": 65,
        "壓力區（派發風險）": 35,
        "未知": 50
    }.get(position, 50)

    vol_df = calc_volume_baseline(df.copy())
    volume_state = detect_volume_state(vol_df)
    price_volume_signal = detect_price_volume_pattern(vol_df)
    latest_avg_volume = _to_float_or_none(vol_df["avg_volume_20"].iloc[-1]) if "avg_volume_20" in vol_df.columns else None
    latest_volume = _to_float_or_none(vol_df["Volume"].iloc[-1])
    volume_ratio = (latest_volume / latest_avg_volume) if (latest_volume is not None and latest_avg_volume not in (None, 0)) else None

    volume_structure_score = 50
    if volume_state in ("放量", "爆量"):
        volume_structure_score += 15
    elif volume_state == "縮量":
        volume_structure_score -= 8

    if price_volume_signal in ("價量齊揚（健康）", "縮量上漲（惜售）"):
        volume_structure_score += 15
    elif price_volume_signal == "價跌量增（出貨警訊）":
        volume_structure_score -= 18

    if volume_ratio is not None:
        if 1.1 <= volume_ratio <= 2.5:
            volume_structure_score += 8
        elif volume_ratio > 3:
            volume_structure_score -= 6
    volume_structure_score = max(0, min(100, volume_structure_score))

    chip_signals, chip_signal_score = calculate_chip_signals(chip_source)
    chip_score = max(0, min(100, chip_signal_score * 25))

    heat_score = calculate_overheat(df)
    risk_penalty = 0
    if heat_score >= 70:
        risk_penalty += 20
    elif heat_score >= 50:
        risk_penalty += 10

    if position == "壓力區（派發風險）":
        risk_penalty += 12

    support_level, resistance_level = get_latest_support_resistance(df)
    if close is not None and resistance_level is not None and resistance_level > 0:
        if close >= resistance_level * 0.98:
            risk_penalty += 8

    raw_score = (
        trend_score * 0.30
        + position_score * 0.25
        + volume_structure_score * 0.20
        + chip_score * 0.25
    )
    final_score = round(max(0, min(100, raw_score - risk_penalty)), 2)
    grade, strength = _score_to_grade(final_score)

    return {
        "trend_score": trend_score,
        "position_score": position_score,
        "volume_structure_score": volume_structure_score,
        "chip_score": chip_score,
        "risk_penalty": risk_penalty,
        "final_score": final_score,
        "grade": grade,
        "strength": strength,
        "weights": {
            "trend": 0.30,
            "position": 0.25,
            "volume_structure": 0.20,
            "chip": 0.25,
        },
        "context": {
            "trend": trend,
            "position": position,
            "volume_state": volume_state,
            "price_volume_signal": price_volume_signal,
            "volume_ratio": volume_ratio,
            "heat_score": heat_score,
            "chip_signals": chip_signals,
            "chip_signal_score": chip_signal_score,
            "support_level": support_level,
            "resistance_level": resistance_level,
        }
    }


def build_hold_strategy_profile(trend, ma5_status, final_score, reduce_target, stop_loss_price):
    reduce_target = _to_float_or_none(reduce_target)
    stop_loss_price = _to_float_or_none(stop_loss_price)
    profile = {
        "mode": "observe",
        "label": "觀察等待型",
        "trigger": "分數介於中性區，且趨勢/均線未形成明確續抱或減碼訊號",
        "usage": "適合訊號未完全共振時，先觀察支撐與量價是否改善",
        "advice": "保守觀察",
    }

    if final_score >= 75 and trend == "多頭趨勢" and ma5_status != "跌破（短線轉弱）":
        profile.update({
            "mode": "trend_follow",
            "label": "續抱趨勢型",
            "trigger": "高分強勢股 + 多頭趨勢 + 未跌破短期均線",
            "usage": "適合持股續抱，優先讓趨勢延伸，跌破短線均線再減碼",
            "advice": (
                f"續抱，跌破 5 日線減碼至 {reduce_target:.2f}"
                if reduce_target is not None
                else "續抱，但均線資料不足請保守"
            ),
        })
    elif final_score < 60 or str(ma5_status).startswith("跌破"):
        profile.update({
            "mode": "risk_control",
            "label": "風險控管型",
            "trigger": "分數偏弱或已跌破短期均線，優先處理回檔風險",
            "usage": "適合持股風險升高時，先看反彈減碼與停損執行",
            "advice": (
                f"反彈減碼，控管風險，停損點 {stop_loss_price:.2f}"
                if stop_loss_price is not None
                else "反彈減碼，控管風險"
            ),
        })

    return profile


def generate_advice(df, trend, ma5_status, position, ma5, start_low, sell_high, chip_strength, support_level, resistance_level, final_score=60):
    ma5 = _to_float_or_none(ma5)
    close = _to_float_or_none(df['Close'].iloc[-1])
    recent_low = _to_float_or_none(df['Low'].iloc[-5:].min()) if 'Low' in df.columns and len(df) >= 5 else close

    # 停損以「關鍵支撐下方緩衝」為主，避免總是貼著現價導致訊號失真
    if support_level is not None:
        stop_loss_price = support_level * 0.97
    elif recent_low is not None:
        stop_loss_price = recent_low * 0.99
    elif close is not None:
        stop_loss_price = close * 0.9
    else:
        stop_loss_price = None

    stop_loss_price = round(stop_loss_price, 2) if stop_loss_price is not None else None

    # 空頭或震盪時，優先以「近期壓力」作為停利，避免目標過遠造成 RR 失真
    if trend != "多頭趨勢":
        base_tp = resistance_level if resistance_level is not None else sell_high
    else:
        base_tp = sell_high if sell_high is not None else resistance_level

    if base_tp is None and close is not None:
        base_tp = close * 1.2
    take_profit_price = round(base_tp, 2) if base_tp is not None else None

    add_targets = determine_add_targets(start_low, chip_strength)
    reduce_target = ma5
    hold_strategy = build_hold_strategy_profile(
        trend=trend,
        ma5_status=ma5_status,
        final_score=final_score,
        reduce_target=reduce_target,
        stop_loss_price=stop_loss_price,
    )
    hold_advice = hold_strategy["advice"]

    # 空手者策略（分數閾值驅動）
    if final_score >= 75 and position == "起漲區（低風險）":
        entry_advice = f"可分批布局，目標加碼價 {add_targets}"
    elif final_score >= 60 and position == "延伸段（趨勢續航）":
        entry_advice = f"等待拉回 5 日線 ({ma5:.2f})" if ma5 is not None else "等待均線資料完整後再評估"
    elif support_level is not None and close is not None and close < support_level:
        entry_advice = "支撐失守，暫不承接，等待重新站回支撐或新底型形成"
    else:
        entry_advice = "不追高，等待修正"

    return stop_loss_price, take_profit_price, add_targets, reduce_target, hold_advice, entry_advice, hold_strategy


def adjust_holding_stop_loss(entry_price, stop_loss_price, support_level=None, atr=None):
    """持有模式下重新校正停損，避免分析停損高於持倉成本。"""
    entry_price = _to_float_or_none(entry_price)
    stop_loss_price = _to_float_or_none(stop_loss_price)
    support_level = _to_float_or_none(support_level)
    atr = _to_float_or_none(atr)

    if entry_price is None:
        return stop_loss_price, None

    if stop_loss_price is not None and stop_loss_price < entry_price:
        return round(stop_loss_price, 2), None

    fallback_candidates = []
    if support_level is not None and support_level > 0:
        fallback_candidates.append(round(support_level * 0.97, 2))
    if atr is not None and atr > 0:
        fallback_candidates.append(round(entry_price - atr * 0.8, 2))
    fallback_candidates.append(round(entry_price * 0.97, 2))

    valid_candidates = [price for price in fallback_candidates if price < entry_price and price > 0]
    adjusted_stop = min(valid_candidates) if valid_candidates else round(entry_price * 0.97, 2)

    warning = (
        "停損高於或等於成本，已在 holding 模式改用持倉風控停損；"
        "建議重新評估風險結構或優先減碼"
    )
    return adjusted_stop, warning




def _calc_buy_streak(series: pd.Series) -> int:
    streak = 0
    for value in reversed(series.tolist()):
        v = pd.to_numeric(pd.Series([value]), errors='coerce').iloc[0]
        if pd.isna(v) or v <= 0:
            break
        streak += 1
    return streak


def calculate_chip_signals(df: pd.DataFrame):
    """計算籌碼因子訊號與分數。"""
    signals = {
        "foreign_buy_streak": 0,
        "foreign_buy_streak_signal": False,
        "price_up_margin_down": False,
        "holder_accumulation": False,
    }
    score = 0

    if 'foreign_net_buy' in df.columns:
        streak = _calc_buy_streak(df['foreign_net_buy'].dropna())
        signals["foreign_buy_streak"] = int(streak)
        if streak >= 5:
            score += 2
            signals["foreign_buy_streak_signal"] = True
        elif streak >= 3:
            score += 1
            signals["foreign_buy_streak_signal"] = True

    if len(df) >= 2 and 'Close' in df.columns:
        price_change = _to_float_or_none(df['Close'].iloc[-1])
        prev_price = _to_float_or_none(df['Close'].iloc[-2])
        margin_change = None
        if 'margin_change_1d' in df.columns:
            margin_change = _to_float_or_none(df['margin_change_1d'].iloc[-1])
        elif 'margin_balance' in df.columns:
            margin_change = _to_float_or_none(df['margin_balance'].iloc[-1] - df['margin_balance'].iloc[-2])

        if price_change is not None and prev_price is not None and margin_change is not None:
            if price_change > prev_price and margin_change < 0:
                signals["price_up_margin_down"] = True
                score += 1

    if len(df) >= 2 and 'holder_1000_up_ratio' in df.columns and 'holder_retail_ratio' in df.columns:
        large_now = _to_float_or_none(df['holder_1000_up_ratio'].iloc[-1])
        large_prev = _to_float_or_none(df['holder_1000_up_ratio'].iloc[-2])
        retail_now = _to_float_or_none(df['holder_retail_ratio'].iloc[-1])
        retail_prev = _to_float_or_none(df['holder_retail_ratio'].iloc[-2])

        if None not in (large_now, large_prev, retail_now, retail_prev):
            if large_now > large_prev and retail_now < retail_prev:
                signals["holder_accumulation"] = True
                score += 1

    return signals, score

# ---------------- 決策引擎主函數 ----------------
def decision_engine(
    df,
    start_zone=(None, None),
    sell_zone=(None, None),
    macro_risk=0,
    chip_strength=0,
    capital=1_000_000,
    risk_pct=0.02,
    market_trend="中性",
    entry_price=None,
    holding_mode="analysis",
):
    df = safe_dataframe(df)
    close = _to_float_or_none(df['Close'].iloc[-1])
    if close is None:
        raise ValueError("最新 Close 值無效，無法分析")
    actual_entry_price = _to_float_or_none(entry_price)
    if holding_mode not in {"analysis", "holding", "auto"}:
        holding_mode = "analysis"
    if holding_mode == "auto":
        holding_mode = "holding" if actual_entry_price is not None else "analysis"
    effective_entry_price = actual_entry_price if actual_entry_price is not None else close

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

    # 量能結構
    df = calc_volume_baseline(df)
    volume_state = detect_volume_state(df)
    price_volume_signal = detect_price_volume_pattern(df)
    latest_avg_volume = _to_float_or_none(df["avg_volume_20"].iloc[-1]) if "avg_volume_20" in df.columns else None
    latest_volume = _to_float_or_none(df["Volume"].iloc[-1])
    volume_ratio = (latest_volume / latest_avg_volume) if (latest_volume is not None and latest_avg_volume not in (None, 0)) else None

    # K線結構 & 支撐壓力
    patterns = detect_candlestick_patterns(df)
    multi_zones = get_multi_level_support_resistance(df)
    support_level, resistance_level = get_latest_support_resistance(df)
    inferred_support, inferred_resistance = infer_support_resistance_from_zones(multi_zones, close)
    history_support, history_resistance = infer_support_resistance_from_history(df, close)

    # 若主支撐明顯高於現價，代表可能已跌破；改用區間推導出的近端支撐避免誤導
    if support_level is None or (support_level is not None and support_level > close):
        support_level = (
            inferred_support
            if inferred_support is not None
            else (history_support if history_support is not None else support_level)
        )
    if resistance_level is None:
        resistance_level = inferred_resistance if inferred_resistance is not None else history_resistance
    market_zone_status = classify_market_zone(close, multi_zones)
    weekly_trend = build_weekly_trend(df)
    atr_series = calc_atr(df)
    latest_atr = _to_float_or_none(atr_series.iloc[-1]) if len(atr_series) else None
    support_zone = build_dynamic_price_zone(support_level, latest_atr)
    resistance_zone = build_dynamic_price_zone(resistance_level, latest_atr)
    market_structure = detect_market_structure(df)
    recent_high = _to_float_or_none(df['High'].tail(20).max()) if 'High' in df.columns else close

    # 行為層分析
    behavior, behavior_reasons = judge_market_state(
            df,
            support_level,
            {'total': heat_score, 'zones': multi_zones},
            patterns,
            zones=multi_zones,
            volume_state=volume_state,
            price_volume_signal=price_volume_signal
        )
    chip_signals, chip_score = calculate_chip_signals(df)
    try:
        scorecard = build_factor_scorecard(df)
    except Exception:
        scorecard = {
            "trend_score": None,
            "position_score": None,
            "volume_structure_score": None,
            "chip_score": None,
            "risk_penalty": None,
            "final_score": 60,
            "grade": "B",
            "strength": "中",
            "weights": {},
            "context": {}
        }

    final_score = scorecard.get("final_score", 60)
    resonance = build_indicator_resonance(df, support_level)

    if market_trend == "空頭":
        final_score = max(0, final_score - 10)

    confidence_breakdown = build_confidence_breakdown(scorecard, patterns, heat_score, market_trend)
    mup_scorecard = build_mup_scorecard(df, scorecard)


    buy_recommendation = build_buy_recommendation(
            close=close,
            support_level=support_level,
            start_low=start_low,
            final_score=final_score,
            position=position,
            trend=trend
        )

    # 操作建議
    stop_loss_price, take_profit_price, add_targets, reduce_target, hold_advice, entry_advice, hold_strategy = generate_advice(
            df,
            trend,
            ma5_status,
            position,
            ma5,
            start_low,
            sell_high,
            chip_strength + chip_score,
            support_level,
            resistance_level,
            final_score
        )
    holding_stop_warning = None
    if holding_mode == "holding":
        stop_loss_price, holding_stop_warning = adjust_holding_stop_loss(
            entry_price=effective_entry_price,
            stop_loss_price=stop_loss_price,
            support_level=support_level,
            atr=latest_atr,
        )
        if holding_stop_warning:
            if hold_advice:
                hold_advice = f"⚠ {holding_stop_warning}；{hold_advice}"
            else:
                hold_advice = f"⚠ {holding_stop_warning}"
            hold_strategy = {
                **(hold_strategy or {}),
                "mode": "risk_control",
                "label": "持倉風控型",
                "trigger": "holding 模式下原始停損高於或等於成本，已改用持倉風控停損",
                "usage": "適合已有持股且原停損失真時，優先以成本下方風控線管理部位",
                "advice": hold_advice,
                "holding_stop_warning": holding_stop_warning,
            }

    rr_metrics = calculate_rr_metrics(effective_entry_price, stop_loss_price, take_profit_price, min_rr=1.5)
    if holding_mode != "holding" and not rr_metrics["rr_pass"]:
        entry_advice = f"RR {rr_metrics.get('rr')} 低於門檻 {rr_metrics['rr_threshold']}，建議略過此次交易"

    position_size = calc_position_size(
        capital=capital,
        risk_pct=risk_pct,
        entry_price=effective_entry_price,
        stop_loss_price=stop_loss_price,
    )
    exit_plan = build_exit_plan(
        entry_price=effective_entry_price,
        stop_loss_price=stop_loss_price,
        current_price=close,
        highest_price=recent_high,
        atr=latest_atr,
        ma5=ma5,
        ema20=ma20,
        trend=trend,
        final_score=final_score,
        holding_mode=holding_mode,
        hold_strategy=hold_strategy,
    )

    if market_trend == "空頭":
        entry_advice = f"⚠ 大盤空頭濾網啟用：{entry_advice}（建議降低倉位或觀望）"

    return {
        "trend": trend,
        "position": position,
        "ma5_status": ma5_status,
        "market_temp": market_temp,
        "heat_score": heat_score,
        "behavior": behavior,
        "behavior_reasons": behavior_reasons,
        "hold_advice": hold_advice,
        "hold_strategy": hold_strategy,
        "reduce_target": reduce_target,
        "entry_advice": entry_advice,
        "buy_recommendation": buy_recommendation,
        "analysis_mode": holding_mode,
        "actual_entry_price": actual_entry_price,
        "effective_entry_price": effective_entry_price,
        "current_price": close,
        "exit_plan": exit_plan,
        "holding_stop_warning": holding_stop_warning,

        "stop_loss": stop_loss_price,
        "take_profit": take_profit_price,
        "patterns": patterns,
        "support_level": support_level,
        "resistance_level": resistance_level,
        "support_zone": support_zone,
        "resistance_zone": resistance_zone,
        "atr": latest_atr,
        "multi_zones": multi_zones,
        "market_zone_status": market_zone_status,
        "market_structure": market_structure,
        "volume_state": volume_state,
        "price_volume_signal": price_volume_signal,
        "avg_volume_20": latest_avg_volume,
        "volume_ratio": volume_ratio,
        "chip_signals": chip_signals,
        "chip_score": chip_score,
        "scorecard": scorecard,
        "final_score": final_score,
        "score_grade": scorecard.get("grade"),
        "score_strength": scorecard.get("strength")
        ,"weekly_trend": weekly_trend,
        "multi_timeframe_signal": f"{weekly_trend} / 日K:{trend}",
        "indicator_resonance": resonance,
        "position_sizing": {
            "capital": capital,
            "risk_pct": risk_pct,
            "suggested_position_value": position_size,
            "formula": "capital × risk_pct / (entry_price - stop_loss)",
        },
        "market_filter": market_trend,
        "ai_confidence_score": round(confidence_breakdown["總分"], 2),
        "ai_confidence_breakdown": confidence_breakdown,
        "rr_metrics": rr_metrics,
        "mup_scorecard": mup_scorecard,
    }
