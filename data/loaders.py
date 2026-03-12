import os
import pandas as pd
from io import StringIO
from datetime import datetime
from dateutil.relativedelta import relativedelta
import requests

from data.chip_loaders import load_chip_csv

# ----------------- 1️⃣ 民國年轉西元 -----------------
def convert_tw_date(tw_date):
    try:
        parts = tw_date.split('/')
        year = int(parts[0]) + 1911
        month = int(parts[1])
        day = int(parts[2])
        return pd.Timestamp(year, month, day)
    except Exception:
        return pd.NaT

# ----------------- 2️⃣ 下載單月 TWSE CSV -----------------
def download_twse_csv_auto(stock_id, year_month):
    url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=csv&date={year_month}01&stockNo={stock_id}"
    r = requests.get(url)
    r.encoding = 'big5'

    data = "\n".join([line for line in r.text.splitlines() if len(line.split('","')) > 8])
    if not data:
        print(f"⚠ {year_month} CSV 沒資料")
        return pd.DataFrame()

    df = pd.read_csv(StringIO(data))
    df.columns = [c.replace('"','').strip() for c in df.columns]

    # 數值欄位轉數字
    for col in ['成交股數','成交金額','開盤價','最高價','最低價','收盤價','漲跌價差','成交筆數']:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str)
                .str.replace(',', '')
                .str.replace('+', '')
                .str.replace('X', '')
                .str.strip(),
                errors='coerce'
            )

    # 日期與英文欄位
    df['Date']   = df['日期'].apply(convert_tw_date) if '日期' in df.columns else pd.NaT
    df['Close']  = df['收盤價'] if '收盤價' in df.columns else pd.NA
    df['Volume'] = df['成交股數'] if '成交股數' in df.columns else pd.NA
    df['Open']   = df['開盤價'] if '開盤價' in df.columns else pd.NA
    df['High']   = df['最高價'] if '最高價' in df.columns else pd.NA
    df['Low']    = df['最低價'] if '最低價' in df.columns else pd.NA

    df = df.dropna(subset=['Date']).reset_index(drop=True)
    df = df.sort_values('Date').reset_index(drop=True)
    return df

# ----------------- 3️⃣ 安全讀取完整 CSV -----------------
def safe_read_full_csv(file_path):
    if not os.path.exists(file_path):
        return pd.DataFrame()
    
    df = pd.read_csv(file_path)
    if 'Date' not in df.columns:
        return pd.DataFrame()
    
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df.dropna(subset=['Date']).reset_index(drop=True)

    for col in ['Close','Volume','Open','High','Low']:
        if col not in df.columns:
            df[col] = pd.NA
        else:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    return df.sort_values('Date').reset_index(drop=True)

# ----------------- 4️⃣ 合併多個月份資料 -----------------
def merge_months_csv(stock_id, months):
    all_data = []
    for m in months:
        df = download_twse_csv_auto(stock_id, m)
        if not df.empty:
            all_data.append(df)

    if not all_data:
        print(f"⚠ {stock_id} 最近 {len(months)} 個月沒有資料")
        return pd.DataFrame()

    full_df = pd.concat(all_data, ignore_index=True)
    full_df = full_df.sort_values('Date').reset_index(drop=True)

    os.makedirs('data', exist_ok=True)
    full_file = f"data/full_stock_{stock_id}.csv"
    full_df.to_csv(full_file, index=False, encoding='utf-8')
    print(f"✅ 合併完整 CSV 已存: {full_file}")
    return full_df

# ----------------- 5️⃣ 更新單月資料 -----------------
def update_full_csv(stock_id, year_month):
    full_file = f"data/full_stock_{stock_id}.csv"
    full_df = safe_read_full_csv(full_file)

    new_df = download_twse_csv_auto(stock_id, year_month)
    if new_df.empty:
        return full_df

    if not full_df.empty and 'Date' in new_df.columns:
        new_df = new_df[~new_df['Date'].isin(full_df['Date'])]

    updated_df = pd.concat([full_df, new_df], ignore_index=True)
    updated_df = updated_df.sort_values('Date').reset_index(drop=True)

    os.makedirs('data', exist_ok=True)
    updated_df.to_csv(full_file, index=False, encoding='utf-8')
    print(f"✅ 完整 CSV 已更新: {full_file} ({year_month})")
    return updated_df

# ----------------- 6️⃣ 抓最近 N 個月 -----------------
def get_last_n_months(n, end_date=None):
    if end_date is None:
        end_date = datetime.today()
    months = []
    for i in range(n):
        dt = end_date - relativedelta(months=i)
        months.append(dt.strftime("%Y%m"))
    return months

# ----------------- 7️⃣ 自動準備完整 CSV -----------------


def prepare_full_feature_df(stock_id, lookback_months=6, include_chip=True):
    """
    準備價量 + 籌碼合併資料：
    1) 價量資料由 prepare_full_stock_csv 取得
    2) 依 Date 左連接籌碼欄位
    """
    price_df = prepare_full_stock_csv(stock_id, lookback_months=lookback_months)
    if price_df is None or price_df.empty:
        return pd.DataFrame()

    feature_df = price_df.copy()
    feature_df['Date'] = pd.to_datetime(feature_df['Date'], errors='coerce')
    feature_df = feature_df.dropna(subset=['Date']).sort_values('Date').reset_index(drop=True)

    if include_chip:
        chip_df = load_chip_csv(stock_id)
        if not chip_df.empty:
            feature_df = feature_df.merge(chip_df, on='Date', how='left')

    return feature_df

def prepare_full_stock_csv(stock_id, lookback_months=6):
    """
    自動準備完整 CSV：
    1️⃣ 如果 CSV 不存在 → 下載最近 lookback_months → 合併成 CSV
    2️⃣ 如果 CSV 存在 → 只更新最新月份
    3️⃣ 回傳安全 DataFrame
    """
    full_file = f"data/full_stock_{stock_id}.csv"
    df = safe_read_full_csv(full_file)
    today = datetime.today()
    latest_month = today.strftime("%Y%m")

    # CSV 不存在或空 → 下載最近 N 個月
    if df.empty:
        print("⚠ 完整 CSV 不存在或為空，開始下載最近幾個月資料")
        months = get_last_n_months(lookback_months, today)
        df = merge_months_csv(stock_id, months)
        if df.empty:
            print("⚠ 下載後仍沒有資料")
            return pd.DataFrame()
        return df

    # CSV 存在 → 檢查最新月份
    max_date = df['Date'].max()
    max_month = max_date.strftime("%Y%m") if pd.notna(max_date) else None
    if max_month != latest_month:
        print(f"⚠ CSV 最新月份 {max_month} 不是最新月份 {latest_month}，更新最新月份")
        df = update_full_csv(stock_id, latest_month)
    else:
        print("✅ CSV 已是最新，不需下載資料")

        # ✅ 最後再次強制回傳 DataFrame
    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame()
    return df
