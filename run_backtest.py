import argparse

from backtest import run_stock_backtest


def parse_args():
    parser = argparse.ArgumentParser(description="回測入口")
    parser.add_argument("--stock-id", default="1504", help="股票代號")
    parser.add_argument("--years", type=int, default=5, help="回測年數")
    parser.add_argument("--initial-capital", type=float, default=1_000_000, help="初始資金")
    parser.add_argument("--strategy", default="basic", help="策略名稱（目前支援: basic）")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.strategy != "basic":
        raise ValueError(f"尚未支援策略: {args.strategy}，目前僅支援 basic")

    stock_id = args.stock_id
    export_path = f"logs/backtest_trades_{stock_id}_{args.strategy}.csv"
    result = run_stock_backtest(
        stock_id=stock_id,
        years=args.years,
        initial_capital=args.initial_capital,
        export_path=export_path,
    )

    print("策略回測")
    print(f"策略：{args.strategy}")
    print(f"股票：{stock_id}")
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
        if pnl_pct is None:
            print(f"{date} | {action} | 價格 {price}")
        else:
            print(f"{date} | {action} | 價格 {price} | 報酬 {round(pnl_pct * 100, 2)}%")


if __name__ == "__main__":
    main()
