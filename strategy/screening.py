import pandas as pd


def _numeric_tail(series: pd.Series, n: int):
    values = pd.to_numeric(series, errors='coerce').dropna()
    if len(values) < n:
        return None
    return values.tail(n)


def near_120d_low(df: pd.DataFrame, threshold: float = 0.15) -> bool:
    if 'Close' not in df.columns or len(df) < 120:
        return False

    close_series = pd.to_numeric(df['Close'], errors='coerce')
    rolling_120_low = close_series.rolling(window=120, min_periods=120).min().iloc[-1]
    latest_close = close_series.iloc[-1]

    if pd.isna(rolling_120_low) or pd.isna(latest_close) or rolling_120_low <= 0:
        return False

    return (latest_close - rolling_120_low) / rolling_120_low <= threshold


def volume_contracting_n_days(df: pd.DataFrame, n: int = 5) -> bool:
    if 'Volume' not in df.columns:
        return False

    tail_volumes = _numeric_tail(df['Volume'], n)
    if tail_volumes is None:
        return False

    slope_down = tail_volumes.iloc[-1] < tail_volumes.iloc[0]
    split = max(1, n // 2)
    first_avg = tail_volumes.iloc[:split].mean()
    second_avg = tail_volumes.iloc[split:].mean()
    avg_decreasing = second_avg < first_avg

    return bool(slope_down or avg_decreasing)


def no_new_low_5d(df: pd.DataFrame) -> bool:
    if 'Low' not in df.columns or len(df) < 6:
        return False

    low_series = pd.to_numeric(df['Low'], errors='coerce').dropna()
    if len(low_series) < 6:
        return False

    recent_low = low_series.tail(5).min()
    prior_low = low_series.iloc[:-5].min()

    if pd.isna(recent_low) or pd.isna(prior_low):
        return False

    return recent_low >= prior_low


def sudden_volume_expansion(df: pd.DataFrame, multiplier: float = 2.0) -> bool:
    if 'Volume' not in df.columns or len(df) < 20:
        return False

    volume_series = pd.to_numeric(df['Volume'], errors='coerce')
    latest_volume = volume_series.iloc[-1]
    avg_volume_20 = volume_series.rolling(window=20, min_periods=20).mean().iloc[-1]

    if pd.isna(latest_volume) or pd.isna(avg_volume_20) or avg_volume_20 <= 0:
        return False

    return latest_volume > avg_volume_20 * multiplier


def evaluate_primary_uptrend_candidate(df: pd.DataFrame, volume_contract_n_days: int = 5):
    signals = {
        'near_120d_low': near_120d_low(df),
        'volume_contracting_n_days': volume_contracting_n_days(df, n=volume_contract_n_days),
        'no_new_low_5d': no_new_low_5d(df),
        'sudden_volume_expansion': sudden_volume_expansion(df),
    }

    reasons = []
    for name, hit in signals.items():
        reasons.append(f"{name}: {'符合' if hit else '未符合'}")

    return {
        'is_primary_uptrend_candidate': all(signals.values()),
        'primary_uptrend_candidate_reasons': reasons,
        'primary_uptrend_candidate_signals': signals,
    }
