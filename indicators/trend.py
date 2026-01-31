import pandas as pd

def calculate_ma(df, periods=[5,20,60,200], handler=None):
    """
    計算均線，handler 可以控制回傳形式
    df: DataFrame，需有 Close 欄位
    periods: list of int
    handler: None (預設回傳 dict) 或 自訂函式
    """
    if df is None or df.empty or 'Close' not in df.columns:
        raise ValueError("DataFrame is empty or缺少 Close 欄位")
    
    ma_data = {f"MA{p}": df['Close'].rolling(p).mean() for p in periods}

    if handler is None:
        # 預設回傳 dict of latest values
        return {k: v.iloc[-1] for k,v in ma_data.items()}
    else:
        # 由 handler 決定怎麼處理
        return handler(df, ma_data)
