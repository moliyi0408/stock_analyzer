from __future__ import annotations

from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests
from dateutil.relativedelta import relativedelta

CACHE_DIR = Path(__file__).resolve().parent / "cache"


def convert_tw_date(tw_date: str):
    try:
        parts = tw_date.split("/")
        year = int(parts[0]) + 1911
        month = int(parts[1])
        day = int(parts[2])
        return pd.Timestamp(year, month, day)
    except Exception:
        return pd.NaT


def download_twse_csv_auto(stock_id: str, year_month: str) -> pd.DataFrame:
    url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=csv&date={year_month}01&stockNo={stock_id}"
    response = requests.get(url, timeout=15)
    response.encoding = "big5"

    data = "\n".join([line for line in response.text.splitlines() if len(line.split('","')) > 8])
    if not data:
        return pd.DataFrame()

    df = pd.read_csv(StringIO(data))
    df.columns = [c.replace('"', "").strip() for c in df.columns]

    for col in ["成交股數", "成交金額", "開盤價", "最高價", "最低價", "收盤價", "漲跌價差", "成交筆數"]:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(",", "").str.replace("+", "").str.replace("X", "").str.strip(),
                errors="coerce",
            )

    df["Date"] = df["日期"].apply(convert_tw_date) if "日期" in df.columns else pd.NaT
    df["Close"] = df["收盤價"] if "收盤價" in df.columns else pd.NA
    df["Volume"] = df["成交股數"] if "成交股數" in df.columns else pd.NA
    df["Open"] = df["開盤價"] if "開盤價" in df.columns else pd.NA
    df["High"] = df["最高價"] if "最高價" in df.columns else pd.NA
    df["Low"] = df["最低價"] if "最低價" in df.columns else pd.NA

    df = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    return df


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
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")


def _needs_refresh(df: pd.DataFrame) -> bool:
    if df.empty or "Date" not in df.columns:
        return True
    last_date = pd.to_datetime(df["Date"], errors="coerce").max()
    if pd.isna(last_date):
        return True
    return last_date.date() < datetime.today().date()


def fetch_price(stock_id: str, lookback_months: int = 6, force_refresh: bool = False) -> pd.DataFrame:
    """Get TWSE price data with file cache.

    Cache path: data/cache/{stock_id}_price.csv
    """
    cache_file = CACHE_DIR / f"{stock_id}_price.csv"
    cached = _safe_read_price_cache(cache_file)

    if not force_refresh and not _needs_refresh(cached):
        return cached

    if cached.empty:
        months = _get_last_n_months(lookback_months)
        refreshed = _merge_months(stock_id, months)
    else:
        latest_month = datetime.today().strftime("%Y%m")
        new_df = download_twse_csv_auto(stock_id, latest_month)
        if new_df.empty:
            refreshed = cached
        else:
            new_df = new_df[~new_df["Date"].isin(cached["Date"])]
            refreshed = pd.concat([cached, new_df], ignore_index=True).sort_values("Date").drop_duplicates(subset=["Date"]).reset_index(drop=True)

    if refreshed.empty:
        return pd.DataFrame()

    _write_cache(cache_file, refreshed)
    return refreshed
