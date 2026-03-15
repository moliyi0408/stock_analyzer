import pandas as pd

from data.data_manager import get_feature_data
from decision_engine import decision_engine
from .config import BacktestConfig


class BacktestEngine:
    def __init__(self, df, config=None):
        self.df = df.sort_values('Date').reset_index(drop=True)
        self.config = config if isinstance(config, BacktestConfig) else BacktestConfig()
        self.initial_capital = float(self.config.initial_capital)
        self.risk_pct = float(self.config.risk_pct)
        self.cash = float(self.initial_capital)
        self.position_shares = 0.0
        self.entry_price = None
        self.stop_loss = None
        self.trade_logs = []
        self.equity_curve = []

    def _buy(self, price, stop_loss, date):
        if price is None or stop_loss is None or price <= stop_loss:
            return
        risk_budget = self.cash * self.risk_pct
        shares = risk_budget / (price - stop_loss)
        max_shares_by_cash = self.cash / price
        shares = min(shares, max_shares_by_cash)
        if shares <= 0:
            return

        cost = shares * price
        self.cash -= cost
        self.position_shares = shares
        self.entry_price = price
        self.stop_loss = stop_loss
        self.trade_logs.append({"date": date, "action": "BUY", "price": price, "shares": shares})

    def _sell(self, price, date, reason):
        if self.position_shares <= 0:
            return
        proceeds = self.position_shares * price
        pnl_pct = (price - self.entry_price) / self.entry_price if self.entry_price else 0
        self.cash += proceeds
        self.trade_logs.append(
            {
                "date": date,
                "action": "SELL",
                "price": price,
                "shares": self.position_shares,
                "pnl_pct": pnl_pct,
                "reason": reason,
            }
        )
        self.position_shares = 0
        self.entry_price = None
        self.stop_loss = None

    def _allow_entry(self, result):
        score = result.get('final_score', 0)
        trend = result.get('trend')
        rr_pass = (result.get('rr_metrics') or {}).get('rr_pass', False)

        if score < self.config.min_score_entry:
            return False
        if self.config.required_trend and trend != self.config.required_trend:
            return False
        if self.config.require_rr_pass and not rr_pass:
            return False
        return True

    def run(self):
        for i in range(60, len(self.df)):
            current_data = self.df.iloc[: i + 1].copy()
            row = current_data.iloc[-1]
            result = decision_engine(current_data)

            close = float(row['Close'])
            date = row['Date']

            if self.position_shares > 0:
                if self.stop_loss and close <= self.stop_loss:
                    self._sell(close, date, "stop_loss")
                elif result.get('take_profit') and close >= result['take_profit']:
                    self._sell(close, date, "take_profit")
                elif result.get('final_score', 0) < self.config.max_score_exit:
                    self._sell(close, date, "signal_exit")
            else:
                if self._allow_entry(result):
                    self._buy(close, result.get('stop_loss'), date)

            equity = self.cash + self.position_shares * close
            self.equity_curve.append({"date": date, "equity": equity})

        if self.position_shares > 0:
            last = self.df.iloc[-1]
            self._sell(float(last['Close']), last['Date'], "end_of_backtest")

        return self.summary()

    def summary(self):
        sells = [t for t in self.trade_logs if t['action'] == 'SELL']
        wins = [t for t in sells if t.get('pnl_pct', 0) > 0]
        win_rate = (len(wins) / len(sells) * 100) if sells else 0
        avg_return = (sum(t.get('pnl_pct', 0) for t in sells) / len(sells) * 100) if sells else 0

        eq = pd.DataFrame(self.equity_curve)
        max_drawdown = 0
        if not eq.empty:
            eq['peak'] = eq['equity'].cummax()
            eq['dd'] = (eq['equity'] - eq['peak']) / eq['peak']
            max_drawdown = eq['dd'].min() * 100

        final_equity = self.cash
        return {
            "initial_capital": self.initial_capital,
            "final_equity": round(final_equity, 2),
            "total_trades": len(sells),
            "win_rate": round(win_rate, 2),
            "avg_return": round(avg_return, 2),
            "max_drawdown": round(max_drawdown, 2),
            "trade_logs": self.trade_logs,
        }

    def export_trade_logs(self, output_path):
        if not self.trade_logs:
            return
        pd.DataFrame(self.trade_logs).to_csv(output_path, index=False, encoding='utf-8')


def run_stock_backtest(stock_id, years=5, config=None, export_path=None):
    df = get_feature_data(stock_id, lookback_months=years * 12, include_chip=True)
    if df is None or df.empty:
        raise ValueError("回測資料不足")

    engine = BacktestEngine(df=df, config=config)
    result = engine.run()
    if export_path:
        engine.export_trade_logs(export_path)
    return result
