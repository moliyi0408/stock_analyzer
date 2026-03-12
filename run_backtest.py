from backtest import run_stock_backtest


def main():
    stock_id = "1504"
    export_path = f"logs/backtest_trades_{stock_id}.csv"
    result = run_stock_backtest(stock_id=stock_id, years=5, initial_capital=1_000_000, export_path=export_path)

    print("策略回測")
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
