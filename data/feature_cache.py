from __future__ import annotations

from pathlib import Path

import pandas as pd

from data.storage_paths import TECHNICAL_FEATURE_CACHE_DIR
from indicators import calc_atr, calc_macd, calc_rsi, calculate_ma


def _cache_path(stock_id: str) -> Path:
    return TECHNICAL_FEATURE_CACHE_DIR / f"{stock_id}_indicators.csv"


def _build_technical_indicators(price_df: pd.DataFrame) -> pd.DataFrame:
    technical_df = price_df.copy()
    technical_df["Date"] = pd.to_datetime(technical_df["Date"], errors="coerce")
    technical_df = technical_df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    technical_df = calculate_ma(technical_df, handler=lambda df, ma: pd.concat([df, pd.DataFrame(ma)], axis=1))
    technical_df["RSI14"] = calc_rsi(technical_df, period=14)
    technical_df["ATR14"] = calc_atr(technical_df, period=14)
    technical_df = pd.concat([technical_df, calc_macd(technical_df)], axis=1)

    return technical_df


def _latest_date(df: pd.DataFrame) -> pd.Timestamp | None:
    if df is None or df.empty or "Date" not in df.columns:
        return None
    latest = pd.to_datetime(df["Date"], errors="coerce").max()
    if pd.isna(latest):
        return None
    return latest.normalize()


def _read_feature_cache(cache_path: Path) -> pd.DataFrame:
    cached = pd.read_csv(cache_path)
    cached["Date"] = pd.to_datetime(cached["Date"], errors="coerce")
    return cached.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)


def build_or_load_technical_feature_cache(stock_id: str, price_df: pd.DataFrame, force_refresh: bool = False) -> pd.DataFrame:
    """建立或讀取技術指標快取。

    技術指標 cache 必須跟最新價格資料同一天；否則會重新計算，避免
    價格 cache 已更新但分析仍沿用舊指標檔的狀況。
    """
    cache_path = _cache_path(stock_id)

    if price_df is None or price_df.empty:
        return pd.DataFrame()

    price_latest_date = _latest_date(price_df)

    if not force_refresh and cache_path.exists():
        cached = _read_feature_cache(cache_path)
        if _latest_date(cached) == price_latest_date:
            return cached
        print(
            f"ℹ️ {stock_id} 技術指標快取日期 {_latest_date(cached).date() if _latest_date(cached) is not None else 'N/A'} "
            f"落後價格日期 {price_latest_date.date() if price_latest_date is not None else 'N/A'}，重新計算"
        )

    technical_df = _build_technical_indicators(price_df)
    TECHNICAL_FEATURE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    technical_df.to_csv(cache_path, index=False)
    return technical_df
