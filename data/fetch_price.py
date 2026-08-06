from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd
from dateutil.relativedelta import relativedelta

from data.storage_paths import PRICE_CACHE_DIR
from data.twse_fetcher import download_twse_csv_auto


def _get_last_n_months(n: int, end_date: datetime | None = None) -> list[str]:
    end_date = end_date or datetime.today()
    months = []
    for i in range(n):
        dt = end_date - relativedelta(months=i)
        months.append(dt.strftime("%Y%m"))
    return months


def _safe_read_price_cache(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    df = pd.read_csv(path)
    if "Date" not in df.columns:
        return pd.DataFrame()

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    for col in ["Close", "Volume", "Open", "High", "Low"]:
        if col not in df.columns:
            df[col] = pd.NA
        else:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def _merge_months(stock_id: str, months: Iterable[str]) -> pd.DataFrame:
    chunks = [download_twse_csv_auto(stock_id, m) for m in months]
    chunks = [c for c in chunks if not c.empty]
    if not chunks:
        return pd.DataFrame()
    return pd.concat(chunks, ignore_index=True).sort_values("Date").drop_duplicates(subset=["Date"]).reset_index(drop=True)


def _write_cache(path: Path, df: pd.DataFrame) -> None:
    PRICE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")


def _latest_date(df: pd.DataFrame) -> pd.Timestamp | None:
    if df.empty or "Date" not in df.columns:
        return None
    last_date = pd.to_datetime(df["Date"], errors="coerce").max()
    if pd.isna(last_date):
        return None
    return last_date.normalize()


def _refresh_from_source(stock_id: str, cached: pd.DataFrame, lookback_months: int) -> pd.DataFrame:
    if cached.empty:
        return _merge_months(stock_id, _get_last_n_months(lookback_months))

    latest_month = datetime.today().strftime("%Y%m")
    source_df = download_twse_csv_auto(stock_id, latest_month)
    if source_df.empty:
        return cached

    cached_latest = _latest_date(cached)
    source_latest = _latest_date(source_df)
    if cached_latest is not None and source_latest is not None and source_latest <= cached_latest:
        return cached

    new_df = source_df[~source_df["Date"].isin(cached["Date"])]
    return (
        pd.concat([cached, new_df], ignore_index=True)
        .sort_values("Date")
        .drop_duplicates(subset=["Date"])
        .reset_index(drop=True)
    )


def fetch_price(stock_id: str, lookback_months: int = 6, force_refresh: bool = False) -> pd.DataFrame:
    """Get TWSE price data with file cache.

    Cache path: datas/price/{stock_id}_price.csv. When cache exists, compare it
    with the latest available TWSE data instead of the calendar date, so holidays
    and pre-close trading days do not force unnecessary refreshes.
    """
    cache_file = PRICE_CACHE_DIR / f"{stock_id}_price.csv"
    cached = _safe_read_price_cache(cache_file)

    refreshed = _refresh_from_source(stock_id, cached, lookback_months)

    if refreshed.empty:
        return pd.DataFrame()

    if force_refresh or not cache_file.exists() or _latest_date(refreshed) != _latest_date(cached):
        _write_cache(cache_file, refreshed)
    return refreshed
