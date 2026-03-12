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
