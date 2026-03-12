import pandas as pd
from data.loaders import prepare_full_feature_df
from indicators import calculate_ma
from decision_engine import decision_engine
from logs import save_analysis_log


TRANSLATIONS = {
    "bullish": "偏多",
    "bearish": "偏空",
    "neutral": "中性",
    "short_term": "短線",
    "swing": "波段",
    "long_term": "長線",
    "foreign_buy_streak": "外資連買天數",
    "foreign_buy_streak_signal": "外資連買訊號",
    "price_up_margin_down": "股價上漲融資下降",
    "holder_accumulation": "大戶增持籌碼",
}


def translate_text(value):
    if isinstance(value, str):
        for en, zh in TRANSLATIONS.items():
            value = value.replace(en, zh)
        return value
    if isinstance(value, dict):
        return {TRANSLATIONS.get(k, k): translate_text(v) for k, v in value.items()}
    if isinstance(value, list):
        return [translate_text(v) for v in value]
    return value

def main():
    stock_id = "1504"

    # 1️⃣ 下載資料
    df = prepare_full_feature_df(stock_id, lookback_months=6, include_chip=True)
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
    print(f"行為理由：{translate_text(safe_get('behavior_reasons'))}")
    print(f"量能狀態：{safe_get('volume_state')}")
    print(f"量價訊號：{safe_get('price_volume_signal')}")
    print(f"20 日均量：{safe_get('avg_volume_20')}")
    print(f"量比（當日量/20 日均量）：{safe_get('volume_ratio')}")
    print(f"籌碼分數：{safe_get('chip_score', 0)}")
    print(f"籌碼訊號：{translate_text(safe_get('chip_signals', {}))}")
    print(f"持有者策略：{safe_get('hold_advice')}")
    print(f"空手者策略：{safe_get('entry_advice')}")
    buy_reco = safe_get('buy_recommendation', {})
    if isinstance(buy_reco, dict) and buy_reco:
        def _format_buy_zone_and_tiers(zone, tiers):
            zone_display = zone
            tiers_display = tiers

            if isinstance(tiers, list):
                dedup_tiers = []
                seen_prices = set()
                for tier in tiers:
                    if not isinstance(tier, dict):
                        continue
                    price = tier.get('price')
                    if price in seen_prices:
                        continue
                    seen_prices.add(price)
                    dedup_tiers.append({'batch': len(dedup_tiers) + 1, 'price': price})

                if dedup_tiers:
                    tiers_display = "、".join(
                        f"第{tier.get('batch')}批 {tier.get('price')}" for tier in dedup_tiers
                    )

                    if isinstance(zone, list) and len(zone) == 2:
                        zone_low, zone_high = sorted(zone)
                        tier_prices = sorted(tier.get('price') for tier in dedup_tiers)
                        if tier_prices and tier_prices[0] == zone_low and tier_prices[-1] == zone_high:
                            zone_display = f"{zone_low} ~ {zone_high}（已由分批買點覆蓋）"

            return zone_display, tiers_display

        zone_display, tiers_display = _format_buy_zone_and_tiers(
            buy_reco.get('preferred_buy_zone', 'N/A'),
            buy_reco.get('tiers', 'N/A'),
        )

        print(f"買入策略：{buy_reco.get('strategy', 'N/A')}")
        print(f"建議買入區間：{zone_display}")
        print(f"分批買點：{tiers_display}")
        print(f"風險提醒：{buy_reco.get('risk_note', 'N/A')}")
    print(f"停損參考價：{safe_get('stop_loss')}")
    print(f"停利參考價：{safe_get('take_profit')}")
    sizing = safe_get('position_sizing', {})
    if isinstance(sizing, dict) and sizing:
        print(
            f"建議倉位金額：{sizing.get('suggested_position_value', 'N/A')} "
            f"(風險比例 {sizing.get('risk_pct', 'N/A')})"
        )
    print(f"多時間框架：{safe_get('multi_timeframe_signal')}")
    resonance = safe_get('indicator_resonance', {})
    if isinstance(resonance, dict):
        print(f"指標共振：{resonance.get('label', 'N/A')} / {resonance.get('signals', [])}")
    print(f"大盤濾網：{safe_get('market_filter', '中性')}")
    print(f"AI 信心分數：{safe_get('ai_confidence_score', 'N/A')} / 100")
    confidence_breakdown = safe_get('ai_confidence_breakdown', {})
    if isinstance(confidence_breakdown, dict) and confidence_breakdown:
        print("AI 信心組成：")
        for key in ["趨勢權重", "量價結構", "K線結構", "市場溫度", "大盤濾網", "籌碼", "總分"]:
            if key in confidence_breakdown:
                print(f"  {key}：{confidence_breakdown.get(key)}")

    print(f"支撐價：{safe_get('support_level')}")
    print(f"壓力價：{safe_get('resistance_level')}")
    print(f"支撐區：{safe_get('support_zone')}")
    print(f"壓力區：{safe_get('resistance_zone')}")
    print(f"ATR：{safe_get('atr')}")
    market_structure = safe_get('market_structure', {})
    if isinstance(market_structure, dict):
        print(f"市場結構：{market_structure.get('structure', 'N/A')}")
        print(f"結構判斷：{market_structure.get('interpretation', 'N/A')}")

    rr_metrics = safe_get('rr_metrics', {})
    if isinstance(rr_metrics, dict) and rr_metrics:
        print(
            f"交易期望值 RR：{rr_metrics.get('rr')} "
            f"(reward={rr_metrics.get('reward')}, risk={rr_metrics.get('risk')}, "
            f"門檻={rr_metrics.get('rr_threshold')}, 通過={rr_metrics.get('rr_pass')})"
        )
    patterns = safe_get('patterns', {})
    print(f"K 線結構：{translate_text(patterns.get('overall_bias','N/A'))} - {patterns.get('meaning','')}")
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
