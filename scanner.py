import argparse
import pandas as pd

from data.loaders import prepare_full_feature_df
from indicators import calculate_ma
from decision_engine import decision_engine


def scan_market(stock_ids, lookback_months=6, min_confidence=60, min_rr=1.5):
    results = []

    for stock_id in stock_ids:
        try:
            df = prepare_full_feature_df(stock_id, lookback_months=lookback_months, include_chip=True)
            if df is None or df.empty:
                continue
            df = calculate_ma(df, handler=lambda x, ma: pd.concat([x, pd.DataFrame(ma)], axis=1))
            signal = decision_engine(df=df)
            rr = (signal.get("rr_metrics") or {}).get("rr")
            rr_pass = (signal.get("rr_metrics") or {}).get("rr_pass", False)
            confidence = signal.get("ai_confidence_score", 0)

            if confidence >= min_confidence and rr_pass and (rr is not None and rr >= min_rr):
                results.append(
                    {
                        "stock_id": stock_id,
                        "confidence": confidence,
                        "rr": rr,
                        "trend": signal.get("trend"),
                        "market_structure": (signal.get("market_structure") or {}).get("structure"),
                    }
                )
        except Exception as exc:
            print(f"⚠ 掃描 {stock_id} 失敗：{exc}")

    return sorted(results, key=lambda x: (x["confidence"], x["rr"]), reverse=True)


def main():
    parser = argparse.ArgumentParser(description="掃描今日潛力股")
    parser.add_argument("--stocks", default="2330,2317,2454,2303,3017,2453,1504")
    parser.add_argument("--lookback-months", type=int, default=6)
    parser.add_argument("--min-confidence", type=float, default=60)
    parser.add_argument("--min-rr", type=float, default=1.5)
    args = parser.parse_args()

    stock_ids = [s.strip() for s in args.stocks.split(",") if s.strip()]
    ranked = scan_market(
        stock_ids,
        lookback_months=args.lookback_months,
        min_confidence=args.min_confidence,
        min_rr=args.min_rr,
    )

    print("今日潛力股")
    if not ranked:
        print("無符合條件標的")
        return

    for idx, item in enumerate(ranked, start=1):
        print(f"{idx}️⃣ {item['stock_id']} | 信心：{item['confidence']} | RR：{item['rr']} | 趨勢：{item['trend']} | 結構：{item['market_structure']}")


if __name__ == "__main__":
    main()
