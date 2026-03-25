import argparse

from backtest import run_stock_backtest
from backtest.config import load_backtest_config


def parse_args():
    parser = argparse.ArgumentParser(description="回測入口")
    parser.add_argument("--stock-id", default="1504", help="股票代號")
    parser.add_argument("--years", type=int, default=5, help="回測年數")
    parser.add_argument("--strategy", default="basic", help="策略名稱（目前支援: basic）")
    parser.add_argument(
        "--config",
        default=None,
        help="回測設定檔(JSON)，可自訂進出場分數、風險比例、趨勢條件",
    )
    parser.add_argument(
        "--entry-rule",
        default=None,
        help="進場價格轉換規則，例如 first_tier / last_tier / mid_zone / support_level / resistance_breakout",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if args.strategy != "basic":
        raise ValueError(f"尚未支援策略: {args.strategy}，目前僅支援 basic")

    stock_id = args.stock_id
    config = load_backtest_config(args.config)
    if args.entry_rule:
        config.entry_price_rule = args.entry_rule
    export_path = f"logs/backtest_trades_{stock_id}_{args.strategy}.csv"
    result = run_stock_backtest(
        stock_id=stock_id,
        years=args.years,
        config=config,
        export_path=export_path,
    )

    print("策略回測")
    print(f"策略：{args.strategy}")
    print(f"股票：{stock_id}")
    print(f"設定檔：{args.config or '預設參數'}")
    print(f"初始資金：{config.initial_capital}")
    print(f"單筆風險比例：{config.risk_pct}")
    print(f"進場分數門檻：{config.min_score_entry}")
    print(f"出場分數門檻：{config.max_score_exit}")
    print(f"進場執行模式：{config.entry_execution_mode}")
    print(f"進場價格規則：{config.entry_price_rule}")
    print(f"拉回等待天數：{config.pullback_wait_days}")
    print(f"市價滑價(bps)：{config.market_slippage_bps}")
    print(f"限價滑價(bps)：{config.limit_slippage_bps}")
    print(f"勝率：{result['win_rate']}%")
    print(f"平均報酬：{result['avg_return']}%")
    print(f"最大回撤：{result['max_drawdown']}%")
    print(f"最終資金：{result['final_equity']}")
    print(f"交易紀錄輸出：{export_path}")

    for trade in result.get("trade_logs", [])[-10:]:
        date = trade.get("date")
        action = trade.get("action")
        price = trade.get("price")
        pnl_pct = trade.get("pnl_pct")
        if action == "BUY":
            print(
                f"{date} | {action} | 價格 {price} | 停損 {trade.get('stop_loss')} "
                f"| 部位金額 {round(trade.get('position_value', 0), 2)} "
                f"| 最大風險 {round(trade.get('estimated_max_loss', 0), 2)}"
            )
        elif pnl_pct is None:
            print(f"{date} | {action} | 價格 {price}")
        else:
            print(f"{date} | {action} | 價格 {price} | 報酬 {round(pnl_pct * 100, 2)}%")


if __name__ == "__main__":
    main()
