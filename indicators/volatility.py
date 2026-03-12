import pandas as pd


def calc_bollinger_bands(data, period=20, num_std=2):
    if isinstance(data, pd.DataFrame):
        if "Close" not in data.columns:
            raise ValueError("DataFrame input must contain a 'Close' column")
        close = data["Close"]
    elif isinstance(data, pd.Series):
        close = data
    else:
        raise TypeError("calc_bollinger_bands expects a pandas DataFrame or Series")

    mid = close.rolling(period).mean()
    std = close.rolling(period).std(ddof=0)
    upper = mid + num_std * std
    lower = mid - num_std * std

    return pd.DataFrame(
        {
            "BB_mid": mid,
            "BB_upper": upper,
            "BB_lower": lower,
            "BB_width": (upper - lower) / mid,
        },
        index=close.index,
    )


def calc_atr(data, period=14):
    if not isinstance(data, pd.DataFrame):
        raise TypeError("calc_atr expects a pandas DataFrame")

    required_cols = {"High", "Low", "Close"}
    if not required_cols.issubset(data.columns):
        raise ValueError("DataFrame input must contain High, Low, Close columns")

    high = pd.to_numeric(data["High"], errors="coerce")
    low = pd.to_numeric(data["Low"], errors="coerce")
    close = pd.to_numeric(data["Close"], errors="coerce")

    prev_close = close.shift(1)
    tr_components = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    )
    true_range = tr_components.max(axis=1)
    atr = true_range.rolling(period).mean()
    return atr
