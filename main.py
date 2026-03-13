import pandas as pd
from data.data_manager import get_feature_data
from data.data_manager import get_fundamental
from data.fundamentals import prepare_fundamental_snapshot, load_income_statement_trend
from indicators import calculate_ma
from decision_engine import decision_engine
from analysis.fundamental_analysis import analyze_fundamentals
from strategy.basic_strategy import fundamental_strategy
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

    # 1️⃣ 先確保基本面快取存在（函式內會自動處理 cache -> API -> cache）
    fundamental_payload = get_fundamental(stock_id)
    if fundamental_payload is None or not any(
        fundamental_payload.get(section)
        for section in ["income_statement", "balance_sheet", "cashflow_statement"]
    ):
        print(f"⚠ {stock_id} 基本面資料空，請檢查 API 或 cache")

    fundamental_snapshot = prepare_fundamental_snapshot(stock_id)

    income_trend_df = load_income_statement_trend(stock_id)
    fundamental_analysis = analyze_fundamentals(income_trend_df)
    fundamental_advice = fundamental_strategy(fundamental_analysis)

    # 2️⃣ 下載價量/籌碼資料（函式內會自動處理 cache）
    df = get_feature_data(stock_id, lookback_months=6, include_chip=True)
    if df is None or df.empty:
        print("⚠ 無法取得資料，程式終止")
        return

    # 3️⃣ 計算均線 
    df = calculate_ma(df, handler=lambda df, ma: pd.concat([df, pd.DataFrame(ma)], axis=1))

    # 4️⃣ 呼叫決策引擎
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

    # 5️⃣ 印出結果
    print_analysis(stock_id, df, result, fundamental_snapshot, fundamental_analysis, fundamental_advice)

    # 6️⃣ 儲存分析紀錄
    save_analysis_log(stock_id=stock_id, df=df, result=result)


def print_analysis(stock_id, df, result, fundamental_snapshot=None, fundamental_analysis=None, fundamental_advice=None):
    print("========================================📊 股票分析結果")
    print(f"股票代號：{stock_id}")
    close_price = df['Close'].iloc[-1] if 'Close' in df.columns else "N/A"
    print(f"現價：{close_price}")
    printed_metric_values = {}

    def safe_get(key, default="N/A"):
        if not result:
            return default
        value = result.get(key, default)
        return default if value is None else value

    def with_explanation(label, value, explanation, explanation_prefix="白話"):
        # 同一指標若值相同，只印一次，避免重複輸出
        if printed_metric_values.get(label) == value:
            return
        printed_metric_values[label] = value
        print(f"{label}：{value}")
        if explanation:
            print(f"  ↳ {explanation_prefix}：{explanation}")

    def explain_confidence(score):
        if not isinstance(score, (int, float)):
            return "無法判斷信心強弱"
        if score >= 80:
            return "信心高，屬於偏強訊號"
        if score >= 60:
            return "信心中上，但仍需搭配風險控管"
        if score >= 40:
            return "信心普通，建議等待更明確訊號"
        return "信心偏弱，先以保守策略為主"

    def explain_atr(atr_value):
        if not isinstance(atr_value, (int, float)):
            return "代表平均波動幅度"
        return f"平均一天大約波動 {round(atr_value, 2)} 元"

    def explain_rr(rr):
        if not isinstance(rr, (int, float)):
            return "報酬風險比越高，交易效率通常越好"
        if rr >= 3:
            return "報酬風險比良好，屬於可考慮的交易"
        if rr >= 2:
            return "報酬風險比尚可，建議降低倉位"
        return "報酬風險比偏低，需更嚴格挑選進場"

    def explain_market_temp(temp):
        if temp == "過熱":
            return "短線追價風險高，容易震盪"
        if temp == "偏熱":
            return "市場偏熱，宜分批操作"
        if temp == "中性":
            return "市場情緒平衡，可依計畫交易"
        if temp == "偏冷":
            return "市場偏保守，觀察是否出現轉強"
        return "代表目前市場情緒狀態"

    def format_price(value):
        if isinstance(value, (int, float)):
            return f"{value:.2f}"
        return str(value)


    def format_percent_or_na(value):
        if isinstance(value, (int, float)):
            return f"{value:.2f}%"
        return "N/A"

    def format_number_or_na(value):
        if isinstance(value, (int, float)):
            return f"{value:,.0f}"
        return "N/A"

    def fundamental_payload_date(payload):
        if isinstance(payload, dict):
            return payload.get("fundamental_as_of")
        return None

    def confidence_grade_and_action(score):
        if not isinstance(score, (int, float)):
            return "未知", "資料不足，先觀察"
        if score >= 70:
            return "高", "可積極操作（仍需遵守停損）"
        if score >= 50:
            return "中", "可小額試單，等待訊號確認"
        return "低", "等待訊號，不急著進場"

    def explain_multi_timeframe(signal):
        signal_text = str(signal)
        if "週K空頭" in signal_text and "日K:空頭" in signal_text:
            return "短線觀望，等待反彈確認；長線偏空，僅在支撐區考慮小量分批"
        if "週K空頭" in signal_text and "日K:多頭" in signal_text:
            return "短線有反彈，但中長線仍偏空，宜快進快出"
        if "週K多頭" in signal_text and "日K:空頭" in signal_text:
            return "長線趨勢仍在，但短線回檔中，可等止跌再承接"
        if "週K多頭" in signal_text and "日K:多頭" in signal_text:
            return "多週期同向偏多，可依拉回分批佈局"
        return "多時間框架訊號不一致，建議先等方向更清楚"

    def build_stop_loss_hint(close, stop_loss, atr_value):
        if not all(isinstance(v, (int, float)) for v in [close, stop_loss]):
            return "資料不足，無法估算建議停損區間"
        low = round(stop_loss * 0.99, 2)
        high = round(stop_loss * 1.01, 2)
        hint = f"建議停損區間：約 {low} ~ {high}（可依波動調整 ±1%）"
        if isinstance(atr_value, (int, float)):
            trailing = round(max(stop_loss, close - atr_value * 0.8), 2)
            hint += f"；浮動停損參考：{trailing}"
        return hint

    def build_take_profit_targets(close, take_profit, resistance_zone):
        if not isinstance(take_profit, (int, float)):
            return "資料不足，無法建立分段停利"
        if isinstance(resistance_zone, list) and len(resistance_zone) == 2:
            zone_low, zone_high = sorted(resistance_zone)
            first_target = round(zone_low, 2)
            second_target = round(zone_high, 2)
        elif isinstance(close, (int, float)):
            first_target = round(close + (take_profit - close) * 0.6, 2)
            second_target = round(take_profit, 2)
        else:
            first_target = round(take_profit * 0.97, 2)
            second_target = round(take_profit, 2)
        return f"第一目標：{first_target}；第二目標：{second_target}（可分批獲利）"

    def build_zone_bar(label, zone, fill="█"):
        if isinstance(zone, list) and len(zone) == 2:
            low, high = sorted(zone)
            return f"{label}：{fill*5} {low:.2f} ~ {high:.2f}"
        return f"{label}：資料不足"




    print("\n--- 基本面摘要 ---")
    fundamental_snapshot = fundamental_snapshot if isinstance(fundamental_snapshot, dict) else {}
    fundamental_data_date = fundamental_snapshot.get("as_of") or fundamental_payload_date(result)
    print(f"資料日期：{fundamental_data_date or 'N/A'}")
    print(f"ROE：{format_percent_or_na(fundamental_snapshot.get('roe'))}")
    print(f"毛利率：{format_percent_or_na(fundamental_snapshot.get('gross_margin'))}")
    print(f"負債比率：{format_percent_or_na(fundamental_snapshot.get('debt_ratio'))}")
    print(f"自由現金流：{format_number_or_na(fundamental_snapshot.get('free_cash_flow'))}")

    if isinstance(fundamental_analysis, dict) and fundamental_analysis.get("has_data"):
        metrics = fundamental_analysis.get("metrics", {})

        def fmt_ratio(value):
            return f"{value * 100:.2f}%" if isinstance(value, (int, float)) else "N/A"

        print(f"毛利率（最新）：{fmt_ratio(metrics.get('gross_margin'))}")
        print(f"營業利益率（最新）：{fmt_ratio(metrics.get('operating_margin'))}")
        print(f"EPS 季增率（最新）：{fmt_ratio(metrics.get('eps_change'))}")
        print(f"EPS 季增率（近3期平均）：{fmt_ratio(metrics.get('eps_change_3p_avg'))}")
    else:
        print("基本面延伸指標：資料不足")

    if fundamental_advice:
        print(f"基本面策略建議：{fundamental_advice}")

    print("\n--- 市場摘要 ---")
    print(f"趨勢：{safe_get('trend')}")
    print(f"價格位置：{safe_get('position')}")
    print(f"五日線狀態：{safe_get('ma5_status')}")
    market_temp = safe_get('market_temp')
    with_explanation(
        "市場溫度",
        f"{market_temp}（分數 {safe_get('heat_score')}）",
        explain_market_temp(market_temp),
    )
    print(f"行為判斷：{safe_get('behavior')}")
    print(f"行為理由：{translate_text(safe_get('behavior_reasons'))}")

    print("\n--- 策略建議 ---")
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
        print("買入執行提醒：若跌入支撐區可分批買入，並依 ATR 與量價訊號動態調整掛單")
        print(f"風險提醒：{buy_reco.get('risk_note', 'N/A')}")
    atr_value = safe_get('atr')
    stop_loss = safe_get('stop_loss')
    with_explanation("停損參考價", stop_loss, "跌破此價位代表原先判斷可能失效")
    print(f"  ↳ 白話：{build_stop_loss_hint(close_price, stop_loss, atr_value)}")

    take_profit = safe_get('take_profit')
    with_explanation("停利參考價", take_profit, "接近此區可分批獲利了結，避免回吐")
    print(f"  ↳ 白話：{build_take_profit_targets(close_price, take_profit, safe_get('resistance_zone'))}")
    sizing = safe_get('position_sizing', {})
    if isinstance(sizing, dict) and sizing:
        suggested_value = sizing.get('suggested_position_value')
        print(
            f"建議倉位金額：{suggested_value} "
            f"(風險比例 {sizing.get('risk_pct', 'N/A')})"
        )
        if all(isinstance(v, (int, float)) for v in [suggested_value, close_price, stop_loss]):
            share_estimate = suggested_value / close_price if close_price else 0
            max_loss = share_estimate * (close_price - stop_loss)
            print(f"最大承受損失金額：約 {max_loss:.2f}（跌破停損時的估算虧損）")

    multi_signal = safe_get('multi_timeframe_signal')
    print(f"多時間框架：{multi_signal}")
    print(f"  ↳ 白話：{explain_multi_timeframe(multi_signal)}")

    print("\n--- 技術指標 ---")
    resonance = safe_get('indicator_resonance', {})
    if isinstance(resonance, dict):
        print(f"指標共振：{resonance.get('label', 'N/A')} / {resonance.get('signals', [])}")
    print(f"大盤濾網：{safe_get('market_filter', '中性')}")
    print("\n--- AI 分析 ---")
    ai_confidence_score = safe_get('ai_confidence_score', 'N/A')
    confidence_grade, confidence_action = confidence_grade_and_action(ai_confidence_score)
    with_explanation(
        "AI 信心分數",
        f"{ai_confidence_score} / 100（{confidence_grade}）",
        f"{explain_confidence(ai_confidence_score)}；建議：{confidence_action}",
    )
    confidence_breakdown = safe_get('ai_confidence_breakdown', {})
    if isinstance(confidence_breakdown, dict) and confidence_breakdown:
        print("AI 信心組成：")
        for key in ["趨勢權重", "量價結構", "K線結構", "市場溫度", "大盤濾網", "籌碼", "總分"]:
            if key in confidence_breakdown:
                print(f"  {key}：{confidence_breakdown.get(key)}")

    with_explanation("支撐價", safe_get('support_level'), "常見買盤防守價位，跌破要提高警覺")
    with_explanation("壓力價", safe_get('resistance_level'), "常見賣壓區，接近時容易震盪")
    with_explanation("支撐區", safe_get('support_zone'), "回檔至此區可觀察是否止跌")
    with_explanation("壓力區", safe_get('resistance_zone'), "反彈至此區可觀察是否遇到賣壓")
    with_explanation("ATR", atr_value, explain_atr(atr_value))

    print("\n--- 區間可視化（文字版）---")
    print(build_zone_bar("支撐區", safe_get('support_zone'), fill="█"))
    print(build_zone_bar("壓力區", safe_get('resistance_zone'), fill="█"))
    buy_tiers = buy_reco.get('tiers', []) if isinstance(buy_reco, dict) else []
    if isinstance(buy_tiers, list) and buy_tiers:
        tier_text = " ▓ ".join(format_price(tier.get('price')) for tier in buy_tiers if isinstance(tier, dict))
        if tier_text:
            print(f"分批買點：{tier_text}")

    market_structure = safe_get('market_structure', {})
    if isinstance(market_structure, dict):
        structure = market_structure.get('structure', 'N/A')
        interpretation = market_structure.get('interpretation', 'N/A')
        with_explanation("市場結構", structure, "例如 LH/LL 代表短線仍偏弱，HH/HL 代表轉強")
        with_explanation("結構判斷", interpretation, "描述目前多空是否延續或反轉")

    rr_metrics = safe_get('rr_metrics', {})
    if isinstance(rr_metrics, dict) and rr_metrics:
        rr_value = rr_metrics.get('rr')
        print(
            f"交易期望值 RR：{rr_value} "
            f"(reward={rr_metrics.get('reward')}, risk={rr_metrics.get('risk')}, "
            f"門檻={rr_metrics.get('rr_threshold')}, 通過={rr_metrics.get('rr_pass')})"
        )
        print(f"  ↳ 白話：{explain_rr(rr_value)}")
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
