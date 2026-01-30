# main.py
from data_layer import get_last_n_months, update_full_csv, merge_months_csv
from indicators import (
    add_moving_averages,
    get_starting_zone,
    get_selling_zone,
    get_support_resistance,
    calc_overheat_score
)
from decision_engine import decision_engine
import os

def update_and_analyze(stock_id, months_to_check=3, bin_size=5, top_n=3):
    full_file = f"full_stock_{stock_id}.csv"
    
    # ---------- 1️⃣ 建立完整 CSV ----------
    if not os.path.exists(full_file):
        # 如果 CSV 不存在 → 一次抓最近 N 個月全部合併
        months = get_last_n_months(months_to_check)
        full_df = merge_months_csv(stock_id, months)
    else:
        # CSV 已存在 → 只更新最新一個月
        months = get_last_n_months(1)
        full_df = update_full_csv(stock_id, months[0])

    if full_df.empty:
        print("⚠ 無資料可分析")
        return None
    
    # ---------- 2️⃣ 計算均線 ----------
    full_df = add_moving_averages(full_df)

    # ---------- 3️⃣ 計算各種區間與指標 ----------
    start_zone = get_starting_zone(full_df)
    sell_zone = get_selling_zone(*start_zone)
    support, resistance = get_support_resistance(full_df, bin_size, top_n)
    heat_score = calc_overheat_score(full_df, start_zone, resistance)['total']

    # ---------- 4️⃣ 決策引擎 ----------
    decision = decision_engine(
        full_df,
        start_zone,
        sell_zone,
        support,
        resistance,
        heat_score
    )

    # ---------- 5️⃣ 最終輸出 ----------
    print("\n" + "=" * 40)
    print(f"📊 股票 {stock_id} 專業決策摘要")
    print("=" * 40)
    print(f"📈 現價：{full_df['Close'].iloc[-1]}")
    print(f"📌 趨勢：{decision.get('trend','無')}")
    print(f"📍 位置：{decision.get('position','無')}")
    ma5 = full_df['MA5'].iloc[-1] if 'MA5' in full_df else 0
    print(f"📐 五日線：{decision.get('ma5_status','無')} ({ma5:.2f})")
    print(f"🔥 市場溫度：{decision.get('market_temp','無')}")
    print(f"⚠ 行為風險：{decision.get('behavior','無')}")
    print("-" * 40)

    # 策略文字
    print(f"▶ 持有者策略：{decision.get('hold_advice','無')}")
    print(f"▶ 空手者策略：{decision.get('entry_advice','無')}")

    # 分批加碼建議
    add_targets = decision.get("add_targets", [])
    if add_targets:
        print(f"▶ 分批加碼建議價位：{add_targets}")
    else:
        print(f"▶ 分批加碼建議價位：無")

    # 減碼參考價位
    reduce_target = decision.get("reduce_target", None)
    if reduce_target is not None:
        print(f"▶ 減碼參考價位：{reduce_target:.2f}")
    else:
        print(f"▶ 減碼參考價位：無")

    # 停損/停利
    stop_loss = decision.get("stop_loss", None)
    take_profit = decision.get("take_profit", None)
    if stop_loss is not None:
        print(f"▶ 停損參考價位：{stop_loss:.2f}")
    else:
        print(f"▶ 停損參考價位：無")
    if take_profit is not None:
        print(f"▶ 停利參考價位：{take_profit:.2f}")
    else:
        print(f"▶ 停利參考價位：無")

    print("=" * 40)
    return decision

if __name__ == "__main__":
    update_and_analyze("2453", months_to_check=12)
