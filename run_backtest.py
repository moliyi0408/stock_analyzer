import argparse

import pandas as pd

from backtest import run_rsi_fundamental_backtest, run_stock_backtest


def _print_common_result(title: str, stock_id: str, result: dict):
    print(title)
    print(f"股票：{stock_id}")
    print(f"總交易數：{result['total_trades']}")
    print(f"勝率：{result['win_rate']}%")
    print(f"平均報酬：{result['avg_return']}%")
    print(f"最大回撤：{result['max_drawdown']}%")
    print(f"最終資金：{result['final_equity']}")


def _export_trade_logs(path: str | None, trade_logs: list[dict]):
    if not path or not trade_logs:
        return
    pd.DataFrame(trade_logs).to_csv(path, index=False, encoding="utf-8")
    print(f"交易紀錄輸出：{path}")


def main():
    parser = argparse.ArgumentParser(description="Run strategy backtest.")
    parser.add_argument("--stock-id", default="1504", help="Stock ID")
    parser.add_argument("--years", type=int, default=5, help="Backtest years")
    parser.add_argument(
        "--strategy",
        choices=["default", "rsi_fundamental"],
        default="default",
        help="Backtest strategy.",
    )
    parser.add_argument("--initial-capital", type=float, default=1_000_000)
    parser.add_argument("--export-path", default=None, help="Export trade logs csv path")
    parser.add_argument("--force-refresh", action="store_true", help="Refresh cached data")

    args = parser.parse_args()

    export_path = args.export_path or f"logs/backtest_trades_{args.stock_id}_{args.strategy}.csv"

    if args.strategy == "rsi_fundamental":
        result = run_rsi_fundamental_backtest(
            stock_id=args.stock_id,
            years=args.years,
            initial_capital=args.initial_capital,
            force_refresh=args.force_refresh,
        )
        _print_common_result("RSI + 基本面回測", args.stock_id, result)
        print("\n基本面條件檢查：")
        for key, passed in result["fundamental_gate"]["checks"].items():
            print(f"- {key}: {'PASS' if passed else 'FAIL'}")
        cache = result.get("cache", {})
        if cache:
            print(f"\n特徵快取：{cache.get('indicator_cache')}")
            print(f"基本面快取：{cache.get('fundamental_gate_cache')}")
        _export_trade_logs(export_path, result.get("trade_logs", []))
        return

    result = run_stock_backtest(
        stock_id=args.stock_id,
        years=args.years,
        initial_capital=args.initial_capital,
        export_path=export_path,
    )
    _print_common_result("策略回測（原始 decision_engine）", args.stock_id, result)
    _export_trade_logs(export_path, result.get("trade_logs", []))


if __name__ == "__main__":
    main()
