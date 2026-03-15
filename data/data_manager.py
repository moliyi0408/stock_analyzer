from __future__ import annotations

import pandas as pd

from data.chip_loaders import load_chip_csv
from data.fetch_fundamental import fetch_fundamental
from data.feature_cache import build_or_load_technical_feature_cache
from data.fetch_price import fetch_price


def get_price(stock_id: str, lookback_months: int = 6, force_refresh: bool = False) -> pd.DataFrame:
    """取得價格資料（含 cache）。"""
    return fetch_price(stock_id=stock_id, lookback_months=lookback_months, force_refresh=force_refresh)


def get_fundamental(stock_id: str, force_refresh: bool = False) -> dict:
    """取得基本面資料（含 cache）。"""
    return fetch_fundamental(stock_id=stock_id, force_refresh=force_refresh)


def get_feature_data(
    stock_id: str,
    lookback_months: int = 6,
    include_chip: bool = True,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """取得價量 + 籌碼合併資料。"""
    price_df = get_price(stock_id=stock_id, lookback_months=lookback_months, force_refresh=force_refresh)
    if price_df.empty:
        return pd.DataFrame()

    feature_df = build_or_load_technical_feature_cache(
        stock_id=stock_id,
        price_df=price_df,
        force_refresh=force_refresh,
    )
    if feature_df.empty:
        return pd.DataFrame()

    if include_chip:
        chip_df = load_chip_csv(stock_id)
        if not chip_df.empty:
            feature_df = feature_df.merge(chip_df, on="Date", how="left")

    return feature_df
