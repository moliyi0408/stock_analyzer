# data_layer.py
import requests
import pandas as pd
from io import StringIO
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta

# 民國年轉西元
def convert_tw_date(tw_date):
    # tw_date: '115/01/02'
    parts = tw_date.split('/')
    year = int(parts[0]) + 1911
    month = int(parts[1])
    day = int(parts[2])
    return pd.Timestamp(year, month, day)

# 下載指定月份 TWSE CSV
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

    for col in ['成交股數','成交金額','開盤價','最高價','最低價','收盤價','漲跌價差','成交筆數']:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str)
                .str.replace(',', '')
                .str.replace('+','')
                .str.replace('X','')
                .str.strip(),
                errors='coerce'
            )

    if '日期' in df.columns:
        df['Date'] = df['日期'].apply(convert_tw_date)
    if '收盤價' in df.columns:
        df['Close'] = df['收盤價']
    if '成交股數' in df.columns:
        df['Volume'] = df['成交股數']
    if '開盤價' in df.columns:
        df['Open'] = df['開盤價']
    if '最高價' in df.columns:
        df['High'] = df['最高價']
    if '最低價' in df.columns:
        df['Low'] = df['最低價']

    df = df.sort_values('Date').reset_index(drop=True)
    return df

# 合併多個月份 CSV
def merge_months_csv(stock_id, months):
    all_data = []
    for m in months:
        df = download_twse_csv_auto(stock_id, m)
        if not df.empty:
            all_data.append(df)
    if not all_data:
        print("⚠ 沒有任何月份資料")
        return pd.DataFrame()
    full_df = pd.concat(all_data, ignore_index=True)
    full_df = full_df.sort_values('Date').reset_index(drop=True)
    full_file = f"full_stock_{stock_id}.csv"
    full_df.to_csv(full_file, index=False, encoding='utf-8')
    print(f"✅ 合併完整 CSV 已存: {full_file}")
    return full_df

# 更新單月資料
def update_full_csv(stock_id, year_month):
    full_file = f"full_stock_{stock_id}.csv"
    if os.path.exists(full_file):
        full_df = pd.read_csv(full_file)
        full_df['Date'] = pd.to_datetime(full_df['Date'])
    else:
        full_df = pd.DataFrame()

    new_df = download_twse_csv_auto(stock_id, year_month)
    if new_df.empty:
        print(f"⚠ {year_month} 無資料，不更新完整 CSV")
        return full_df

    if not full_df.empty:
        new_df = new_df[~new_df['Date'].isin(full_df['Date'])]

    updated_df = pd.concat([full_df, new_df], ignore_index=True)
    updated_df = updated_df.sort_values('Date').reset_index(drop=True)
    updated_df.to_csv(full_file, index=False, encoding='utf-8')
    print(f"✅ 完整 CSV 已更新: {full_file} ({year_month})")
    return updated_df

# 抓最近 N 個月
def get_last_n_months(n, end_date=None):
    if end_date is None:
        end_date = datetime.today()
    months = []
    for i in range(n):
        dt = end_date - relativedelta(months=i)
        months.append(dt.strftime("%Y%m"))
    return months
