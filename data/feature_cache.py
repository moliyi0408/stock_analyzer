from __future__ import annotations

from pathlib import Path

import pandas as pd

from data.storage_paths import TECHNICAL_FEATURE_CACHE_DIR
from indicators import calc_atr, calc_macd, calc_rsi, calculate_ma


def _cache_path(stock_id: str) -> Path:
    return TECHNICAL_FEATURE_CACHE_DIR / f"{stock_id}_indicators.parquet"


def _build_technical_indicators(price_df: pd.DataFrame) -> pd.DataFrame:
    technical_df = price_df.copy()
    technical_df["Date"] = pd.to_datetime(technical_df["Date"], errors="coerce")
    technical_df = technical_df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    technical_df = calculate_ma(technical_df, handler=lambda df, ma: pd.concat([df, pd.DataFrame(ma)], axis=1))
    technical_df["RSI14"] = calc_rsi(technical_df, period=14)
    technical_df["ATR14"] = calc_atr(technical_df, period=14)
    technical_df = pd.concat([technical_df, calc_macd(technical_df)], axis=1)

    return technical_df


def build_or_load_technical_feature_cache(stock_id: str, price_df: pd.DataFrame, force_refresh: bool = False) -> pd.DataFrame:
    """建立或讀取技術指標快取。"""
    cache_path = _cache_path(stock_id)

    if not force_refresh and cache_path.exists():
        cached = pd.read_parquet(cache_path)
        cached["Date"] = pd.to_datetime(cached["Date"], errors="coerce")
        cached = cached.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
        return cached

    if price_df is None or price_df.empty:
        return pd.DataFrame()

    technical_df = _build_technical_indicators(price_df)
    TECHNICAL_FEATURE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    technical_df.to_parquet(cache_path, index=False)
    return technical_df
