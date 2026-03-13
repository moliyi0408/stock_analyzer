import pandas as pd

from data.chip_loaders import load_chip_csv
from data.fetch_price import fetch_price


def prepare_full_feature_df(stock_id, lookback_months=6, include_chip=True):
    """準備價量 + 籌碼合併資料。"""
    price_df = prepare_full_stock_csv(stock_id, lookback_months=lookback_months)
    if price_df is None or price_df.empty:
        return pd.DataFrame()

    feature_df = price_df.copy()
    feature_df["Date"] = pd.to_datetime(feature_df["Date"], errors="coerce")
    feature_df = feature_df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    if include_chip:
        chip_df = load_chip_csv(stock_id)
        if not chip_df.empty:
            feature_df = feature_df.merge(chip_df, on="Date", how="left")

    return feature_df


def prepare_full_stock_csv(stock_id, lookback_months=6):
    """以 cache-first 取得 TWSE 價格資料。"""
    df = fetch_price(stock_id=stock_id, lookback_months=lookback_months)
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    return df
