import pandas as pd


def calc_volume_baseline(df, window=20):
    """計算成交量基準欄位 avg_volume_20（可自訂 window）。"""
    if df is None or df.empty:
        return df

    data = df.copy()
    if 'Volume' not in data.columns:
        data['avg_volume_20'] = pd.NA
        return data

    volume = pd.to_numeric(data['Volume'], errors='coerce')
    data['avg_volume_20'] = volume.rolling(window=window, min_periods=1).mean()
    return data


def detect_volume_state(df, shrink_ratio=0.7, expand_ratio=2.0):
    """依最新量比判斷：量縮 / 正常 / 爆量。"""
    if df is None or df.empty or 'Volume' not in df.columns:
        return "正常"

    data = df if 'avg_volume_20' in df.columns else calc_volume_baseline(df)

    latest_volume = pd.to_numeric(pd.Series([data['Volume'].iloc[-1]]), errors='coerce').iloc[0]
    latest_avg = pd.to_numeric(pd.Series([data['avg_volume_20'].iloc[-1]]), errors='coerce').iloc[0]

    if pd.isna(latest_volume) or pd.isna(latest_avg) or latest_avg <= 0:
        return "正常"

    ratio = latest_volume / latest_avg
    if ratio <= shrink_ratio:
        return "量縮"
    if ratio >= expand_ratio:
        return "爆量"
    return "正常"


def detect_price_volume_pattern(df):
    """判斷價格量能結構：下跌量縮 / 上漲量增 / 突破爆量 / 正常。"""
    if df is None or df.empty or len(df) < 2:
        return "正常"

    data = df if 'avg_volume_20' in df.columns else calc_volume_baseline(df)

    close = pd.to_numeric(data['Close'], errors='coerce')
    volume = pd.to_numeric(data['Volume'], errors='coerce')

    latest_close = close.iloc[-1]
    prev_close = close.iloc[-2]
    if pd.isna(latest_close) or pd.isna(prev_close):
        return "正常"

    volume_state = detect_volume_state(data)

    if latest_close < prev_close and volume_state == "量縮":
        return "下跌量縮"

    if latest_close > prev_close and volume_state in {"正常", "爆量"}:
        latest_avg = pd.to_numeric(pd.Series([data['avg_volume_20'].iloc[-1]]), errors='coerce').iloc[0]
        if not pd.isna(latest_avg) and latest_avg > 0 and volume.iloc[-1] > latest_avg:
            return "上漲量增"

    recent_high = close.iloc[-21:-1].max() if len(close) > 21 else close.iloc[:-1].max()
    if (
        not pd.isna(recent_high)
        and latest_close > recent_high
        and volume_state == "爆量"
    ):
        return "突破爆量"

    return "正常"
