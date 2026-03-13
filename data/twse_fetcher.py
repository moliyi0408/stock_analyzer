from __future__ import annotations

from io import StringIO

import pandas as pd
import requests


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
    response = requests.get(url, timeout=15)
    response.encoding = "big5"

    data = "\n".join([line for line in response.text.splitlines() if len(line.split('\",\"')) > 8])
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
