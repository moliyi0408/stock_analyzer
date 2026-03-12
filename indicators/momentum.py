# indicators/momentum.py
import pandas as pd

def calc_rsi(data, period=14):
    if isinstance(data, pd.DataFrame):
        if "Close" not in data.columns:
            raise ValueError("DataFrame input must contain a 'Close' column")
        close = data["Close"]
    elif isinstance(data, pd.Series):
        close = data
    else:
        raise TypeError("calc_rsi expects a pandas DataFrame or Series")

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calc_williams_r(df, period=14):
    highest_high = df["High"].rolling(period).max()
    lowest_low = df["Low"].rolling(period).min()
    wr = -100 * (highest_high - df["Close"]) / (highest_high - lowest_low)
    return wr
