import pandas as pd

from data.data_manager import get_feature_data
from decision_engine import decision_engine
from strategy.exit import evaluate_exit_signal
from .config import BacktestConfig


class BacktestEngine:
    def __init__(self, df, config=None):
        self.df = df.sort_values('Date').reset_index(drop=True)
        self.config = config if isinstance(config, BacktestConfig) else BacktestConfig()
        self.initial_capital = float(self.config.initial_capital)
        self.risk_pct = float(self.config.risk_pct)
        self.cash = float(self.initial_capital)
        self.position_shares = 0.0
        self.initial_position_shares = 0.0
        self.entry_price = None
        self.stop_loss = None
        self.highest_price = None
        self.took_first_profit = False
        self.took_second_profit = False
        self.pending_entry = None
        self.trade_logs = []
        self.equity_curve = []

    def _buy(self, price, stop_loss, date, reason="entry_signal"):
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
        self.initial_position_shares = shares
        self.entry_price = price
        self.stop_loss = stop_loss
        self.highest_price = price
        self.took_first_profit = False
        self.took_second_profit = False
        self.pending_entry = None
        self.trade_logs.append({"date": date, "action": "BUY", "price": price, "shares": shares, "reason": reason})

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
        self.initial_position_shares = 0
        self.entry_price = None
        self.stop_loss = None
        self.highest_price = None
        self.took_first_profit = False
        self.took_second_profit = False

    def _sell_partial(self, price, date, fraction_of_initial, reason):
        if self.position_shares <= 0 or fraction_of_initial <= 0:
            return
        sell_shares = min(self.position_shares, self.initial_position_shares * fraction_of_initial)
        if sell_shares <= 0:
            return

        proceeds = sell_shares * price
        pnl_pct = (price - self.entry_price) / self.entry_price if self.entry_price else 0
        self.cash += proceeds
        self.position_shares -= sell_shares
        self.trade_logs.append(
            {
                "date": date,
                "action": "SELL_PARTIAL",
                "price": price,
                "shares": sell_shares,
                "remaining_shares": self.position_shares,
                "pnl_pct": pnl_pct,
                "reason": reason,
            }
        )
        if self.position_shares <= 0:
            self.position_shares = 0
            self.initial_position_shares = 0
            self.entry_price = None
            self.stop_loss = None
            self.highest_price = None
            self.took_first_profit = False
            self.took_second_profit = False

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

    def _schedule_entry(self, row, result):
        mode = getattr(self.config, "entry_execution_mode", "same_close")
        stop_loss = result.get("stop_loss")
        buy_reco = result.get("buy_recommendation") or {}
        preferred_zone = buy_reco.get("preferred_buy_zone")
        target_price = None
        if isinstance(preferred_zone, list) and len(preferred_zone) == 2:
            target_price = float(sorted(preferred_zone)[-1])
        elif isinstance(buy_reco.get("tiers"), list) and buy_reco.get("tiers"):
            target_price = float(buy_reco["tiers"][0]["price"])

        if mode == "same_close":
            close = float(row["Close"])
            self._buy(close, stop_loss, row["Date"], reason="same_close_signal")
            return

        if mode == "support_pullback" and target_price is not None:
            self.pending_entry = {
                "mode": mode,
                "signal_date": row["Date"],
                "stop_loss": stop_loss,
                "target_price": target_price,
                "days_waited": 0,
            }
            return

        self.pending_entry = {
            "mode": "next_open",
            "signal_date": row["Date"],
            "stop_loss": stop_loss,
            "days_waited": 0,
        }

    def _process_pending_entry(self, row):
        if self.pending_entry is None or self.position_shares > 0:
            return

        pending = self.pending_entry
        mode = pending.get("mode", "next_open")
        close = float(row["Close"])
        open_price = float(row["Open"]) if "Open" in row and pd.notna(row["Open"]) else close
        low = float(row["Low"]) if "Low" in row and pd.notna(row["Low"]) else min(open_price, close)
        date = row["Date"]

        if mode == "next_open":
            self._buy(open_price, pending.get("stop_loss"), date, reason="next_open_entry")
            return

        if mode == "support_pullback":
            pending["days_waited"] = pending.get("days_waited", 0) + 1
            target_price = pending.get("target_price")
            if target_price is not None and low <= target_price:
                fill_price = open_price if open_price <= target_price else target_price
                self._buy(fill_price, pending.get("stop_loss"), date, reason="support_pullback_entry")
                return
            if pending["days_waited"] >= max(1, int(getattr(self.config, "pullback_wait_days", 5))):
                self.trade_logs.append(
                    {
                        "date": date,
                        "action": "ENTRY_CANCELLED",
                        "price": target_price,
                        "reason": "pullback_not_filled",
                    }
                )
                self.pending_entry = None

    def run(self):
        for i in range(60, len(self.df)):
            current_data = self.df.iloc[: i + 1].copy()
            row = current_data.iloc[-1]
            self._process_pending_entry(row)
            result = decision_engine(
                current_data,
                entry_price=self.entry_price,
                holding_mode="holding" if self.position_shares > 0 else "analysis",
            )

            close = float(row['Close'])
            date = row['Date']

            if self.position_shares > 0:
                high = float(row['High']) if 'High' in row and pd.notna(row['High']) else close
                self.highest_price = max(self.highest_price or close, high)

                exit_eval = evaluate_exit_signal(
                    current_price=close,
                    entry_price=self.entry_price,
                    stop_loss_price=self.stop_loss,
                    highest_price=self.highest_price,
                    atr=result.get('atr'),
                    ma5=current_data['MA5'].iloc[-1] if 'MA5' in current_data.columns else None,
                    ema20=current_data['MA20'].iloc[-1] if 'MA20' in current_data.columns else None,
                    trend=result.get('trend'),
                    final_score=result.get('final_score'),
                    has_taken_first_profit=self.took_first_profit,
                    has_taken_second_profit=self.took_second_profit,
                )

                for action in exit_eval.get("actions", []):
                    if action.get("type") == "partial_exit":
                        reason = action.get("reason", "partial_exit")
                        if reason == "t1_hit" and not self.took_first_profit:
                            self._sell_partial(
                                close,
                                date,
                                action.get("fraction_of_initial", 0.5),
                                reason,
                            )
                            self.took_first_profit = True
                        elif reason == "t2_hit" and not self.took_second_profit:
                            self._sell_partial(
                                close,
                                date,
                                action.get("fraction_of_initial", 0.3),
                                reason,
                            )
                            self.took_second_profit = True
                    elif action.get("type") == "update_stop_loss":
                        self.stop_loss = action.get("stop_loss", self.stop_loss)

                if self.position_shares > 0 and any(a.get("type") == "exit_all" for a in exit_eval.get("actions", [])):
                    reason = next(
                        (a.get("reason") for a in exit_eval.get("actions", []) if a.get("type") == "exit_all"),
                        "exit_signal",
                    )
                    self._sell(close, date, reason)
                elif self.position_shares > 0 and result.get('final_score', 0) < self.config.max_score_exit:
                    self._sell(close, date, "signal_exit")
            else:
                if self._allow_entry(result):
                    self._schedule_entry(row, result)

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
