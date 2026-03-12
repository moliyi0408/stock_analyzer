from backtest import run_stock_backtest


def main():
    stock_id = "1504"
    result = run_stock_backtest(stock_id=stock_id, years=5, initial_capital=1_000_000)

    print("策略回測")
    print(f"股票：{stock_id}")
    print(f"勝率：{result['win_rate']}%")
    print(f"平均報酬：{result['avg_return']}%")
    print(f"最大回撤：{result['max_drawdown']}%")
    print(f"最終資金：{result['final_equity']}")


if __name__ == "__main__":
    main()
