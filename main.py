import pandas as pd
from data.loaders import prepare_full_stock_csv
from indicators import calculate_ma
from decision_engine import decision_engine
from logs import save_analysis_log

def main():
    stock_id = "1609"

    # 1️⃣ 下載資料
    df = prepare_full_stock_csv(stock_id, lookback_months=6)
    if df is None or df.empty:
        print("⚠ 無法取得資料，程式終止")
        return

    # 2️⃣ 計算均線 
    df = calculate_ma(df, handler=lambda df, ma: pd.concat([df, pd.DataFrame(ma)], axis=1))

    # 3️⃣ 呼叫決策引擎
    try:
        result = decision_engine(df=df, chip_strength=5)
    except Exception as e:
            latest_snapshot = {}
            for col in ['Close', 'MA5', 'MA20', 'MA60']:
                if col in df.columns and not df.empty:
                    latest_snapshot[col] = df[col].iloc[-1]
                else:
                    latest_snapshot[col] = 'MISSING'
            print(f"⚠ 決策引擎錯誤: {e}")
            print(f"⚠ 最新資料快照: {latest_snapshot}")
            result = {}

    # 4️⃣ 印出結果
    print_analysis(stock_id, df, result)

    # 5️⃣ 儲存分析紀錄
    save_analysis_log(stock_id=stock_id, df=df, result=result)


def print_analysis(stock_id, df, result):
    print("========================================📊 股票分析結果")
    print(f"股票代號：{stock_id}")
    close_price = df['Close'].iloc[-1] if 'Close' in df.columns else "N/A"
    print(f"現價：{close_price}")

    def safe_get(key, default="N/A"):
        if not result:
            return default
        value = result.get(key, default)
        return default if value is None else value


    # 其他決策結果
    print(f"趨勢：{safe_get('trend')}")
    print(f"價格位置：{safe_get('position')}")
    print(f"五日線狀態：{safe_get('ma5_status')}")
    print(f"市場溫度：{safe_get('market_temp')}（分數 {safe_get('heat_score')}）")
    print(f"行為判斷：{safe_get('behavior')}")
    print(f"行為理由：{safe_get('behavior_reasons')}")
    print(f"量能狀態：{safe_get('volume_state')}")
    print(f"量價訊號：{safe_get('price_volume_signal')}")
    print(f"20 日均量：{safe_get('avg_volume_20')}")
    print(f"量比（當日量/20 日均量）：{safe_get('volume_ratio')}")
    print(f"持有者策略：{safe_get('hold_advice')}")
    print(f"空手者策略：{safe_get('entry_advice')}")
    print(f"停損參考價：{safe_get('stop_loss')}")
    print(f"停利參考價：{safe_get('take_profit')}")
    print(f"支撐價：{safe_get('support_level')}")
    print(f"壓力價：{safe_get('resistance_level')}")
    patterns = safe_get('patterns', {})
    print(f"K 線結構：{patterns.get('overall_bias','N/A')} - {patterns.get('meaning','')}")
        # 多空層級支撐/壓力
    """
    multi_zones = safe_get("multi_zones", {})
    market_zone_status = safe_get("market_zone_status", "N/A")  # 直接取字串
  
    for level, zones in multi_zones.items():
        supports = zones.get("support", [])
        resistances = zones.get("resistance", [])
        print(f"{level} 支撐區：{supports}")
        print(f"{level} 壓力區：{resistances}")
        print(f"{level} 多空判斷：{market_zone_status}")  # 直接印字串
        print("-" * 50)
     """

    print("========================================")


if __name__ == "__main__":
    main()
