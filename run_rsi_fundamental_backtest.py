from backtest import run_rsi_fundamental_backtest


def main():
    stock_id = "1504"
    result = run_rsi_fundamental_backtest(stock_id=stock_id, years=5)

    print("RSI + 基本面回測")
    print(f"股票：{result['stock_id']}")
    print(f"總交易數：{result['total_trades']}")
    print(f"勝率：{result['win_rate']}%")
    print(f"平均報酬：{result['avg_return']}%")
    print(f"最大回撤：{result['max_drawdown']}%")
    print(f"最終資金：{result['final_equity']}")

    print("\n基本面條件檢查：")
    for key, passed in result["fundamental_gate"]["checks"].items():
        print(f"- {key}: {'PASS' if passed else 'FAIL'}")

    cache = result.get("cache", {})
    if cache:
        print(f"\n特徵快取：{cache.get('indicator_cache')}")
        print(f"基本面快取：{cache.get('fundamental_gate_cache')}")


if __name__ == "__main__":
    main()
