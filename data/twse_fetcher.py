from __future__ import annotations

from io import StringIO

import pandas as pd
import requests


FINMIND_API_URL = "https://api.finmindtrade.com/api/v4/data"


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
    """Download a month of TWSE day data and normalize columns."""
    url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=csv&date={year_month}01&stockNo={stock_id}"
    try:
        response = requests.get(url, timeout=15)
        response.encoding = "big5"
    except Exception:
        return _download_finmind_month(stock_id, year_month)

    data = "\n".join([line for line in response.text.splitlines() if len(line.split('\",\"')) > 8])
    if not data:
        return _download_finmind_month(stock_id, year_month)

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
    if df.empty:
        return _download_finmind_month(stock_id, year_month)
    return df


def _download_finmind_month(stock_id: str, year_month: str) -> pd.DataFrame:
    """Fallback: use FinMind daily price for both listed and OTC stocks."""
    try:
        period = pd.Period(year_month, freq="M")
    except Exception:
        return pd.DataFrame()

    params = {
        "dataset": "TaiwanStockPrice",
        "data_id": stock_id,
        "start_date": period.start_time.strftime("%Y-%m-%d"),
        "end_date": period.end_time.strftime("%Y-%m-%d"),
    }

    try:
        response = requests.get(FINMIND_API_URL, params=params, timeout=15)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return pd.DataFrame()

    rows = payload.get("data", []) if isinstance(payload, dict) else []
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    rename_map = {
        "date": "Date",
        "close": "Close",
        "Trading_Volume": "Volume",
        "open": "Open",
        "max": "High",
        "min": "Low",
    }
    df = df.rename(columns=rename_map)

    required_cols = ["Date", "Close", "Volume", "Open", "High", "Low"]
    for col in required_cols:
        if col not in df.columns:
            df[col] = pd.NA

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    for col in ["Close", "Volume", "Open", "High", "Low"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
