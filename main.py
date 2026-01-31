import os
import pandas as pd
from data.loaders import prepare_full_stock_csv
from indicators import (
    calculate_ma, get_starting_zone, get_selling_zone
)
from decision_engine import decision_engine
from logs import save_analysis_log


def main():
    # ---------- 1️⃣ 設定股票代號與下載月份 ----------
    stock_id = "00635U"
    df = prepare_full_stock_csv(stock_id, lookback_months=6)

    if not isinstance(df, pd.DataFrame) or df.empty:
        print("⚠ 無法取得任何資料，程式終止")
        return

    # ---------- 2️⃣ 計算技術指標 ----------
    df = calculate_ma(df, handler=lambda df, ma: pd.concat([df, pd.DataFrame(ma)], axis=1))

    # ---------- 3️⃣ 計算起漲區與賣出區 ----------
    start_low = start_high = None
    if isinstance(df, pd.DataFrame) and 'Close' in df.columns and 'Volume' in df.columns:
        try:
            start_low, start_high = get_starting_zone(df)
        except Exception:
            print("⚠ 起漲區計算失敗，使用 fallback")
    
    # fallback
    if start_low is None or start_high is None:
        if 'Close' in df.columns and not df['Close'].isna().all():
            start_low = start_high = df['Close'].iloc[-1]
        else:
            start_low = start_high = None
            print("⚠ 無法取得有效收盤價，起漲區設定為 None")

    # 計算賣出區
    try:
        sell_low, sell_high = get_selling_zone(start_low, start_high)
    except Exception:
        sell_low = sell_high = None

    # ---------- 4️⃣ 呼叫統合決策引擎 ----------
    try:
        result = decision_engine(
            df=df,
            start_zone=(start_low, start_high),
            sell_zone=(sell_low, sell_high),
            chip_strength=5
        )
    except Exception as e:
        print(f"⚠ 統合決策引擎發生錯誤: {e}")
        result = {}

    # ---------- 5️⃣ 印出結果 ----------
    print("========================================📊 股票分析結果")
    print(f"股票代號：{stock_id}")

    if 'Close' in df.columns and not df['Close'].isna().all():
        print(f"現價：{df['Close'].iloc[-1]:.2f}")
    else:
        print("現價：N/A")

    # 以下欄位防呆
    def safe_get(key, default="N/A"):
        return result.get(key, default) if result else default

    print(f"趨勢：{safe_get('trend')}")
    print(f"價格位置：{safe_get('position')}")
    print(f"五日線狀態：{safe_get('ma5_status')}")
    print(f"市場溫度：{safe_get('market_temp')}（分數 {safe_get('heat_score')}）")
    print(f"行為判斷：{safe_get('behavior')}")
    print(f"行為理由：{safe_get('behavior_reasons')}")
    print(f"持有者策略：{safe_get('hold_advice')}")
    print(f"空手者策略：{safe_get('entry_advice')}")
    print(f"分批加碼目標：{safe_get('add_targets')}")
    print(f"停損參考價：{safe_get('stop_loss')}")
    print(f"停利參考價：{safe_get('take_profit')}")
    print(f"支撐價：{safe_get('support_level')}")
    print(f"壓力價：{safe_get('resistance_level')}")
    
    patterns = safe_get('patterns', {})
    print(f"K 線結構：{patterns.get('overall_bias','N/A')} - {patterns.get('meaning','')}")
    print("========================================")
    save_analysis_log(
    stock_id=stock_id,
    df=df,
    result=result
)

if __name__ == "__main__":
    main()
