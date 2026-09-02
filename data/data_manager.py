from __future__ import annotations

import pandas as pd

from data.chip_loaders import load_chip_csv
from data.fetch_fundamental import fetch_fundamental
from data.feature_cache import build_or_load_technical_feature_cache
from data.fetch_price import fetch_price


def get_price(stock_id: str, lookback_months: int = 6, force_refresh: bool = False) -> pd.DataFrame:
    """取得可供使用的最新價格資料。

    價格快取的讀取、TWSE 資料比對與快取更新都只能經由這個資料層進行。
    CLI、Web 與其他呼叫端不應自行讀取或判斷價格 CSV 是否需要更新。
    ``force_refresh`` 僅保留給明確要求重新寫入快取的維運用途；一般流程不應使用它。
    """
    return fetch_price(stock_id=stock_id, lookback_months=lookback_months, force_refresh=force_refresh)


def get_fundamental(stock_id: str, force_refresh: bool = False) -> dict:
    """取得可用的基本面資料；資料層負責快取有效性與 API 更新。"""
    return fetch_fundamental(stock_id=stock_id, force_refresh=force_refresh)


def get_feature_data(
    stock_id: str,
    lookback_months: int = 6,
    include_chip: bool = True,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """取得與目前價格快取同步的價量、技術指標與籌碼資料。"""
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
