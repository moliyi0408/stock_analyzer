from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from data.data_manager import get_feature_data
from data.fundamentals import prepare_fundamental_snapshot
from data.storage_paths import FEATURE_CACHE_DIR
from indicators.momentum import calc_rsi

TECHNICAL_FEATURE_CACHE_DIR = FEATURE_CACHE_DIR / "technical"
FUNDAMENTAL_GATE_CACHE_DIR = FEATURE_CACHE_DIR / "fundamental_gate"
FUNDAMENTAL_GATE_TTL_DAYS = 30


def evaluate_fundamental_gate(
    snapshot: dict,
    min_roe: float = 8,
    max_debt_ratio: float = 60,
    min_gross_margin: float = 20,
    require_positive_fcf: bool = True,
) -> dict:
    """Evaluate whether latest fundamental snapshot passes configured thresholds."""
    checks = {
        "roe": snapshot.get("roe") is not None and snapshot["roe"] >= min_roe,
        "debt_ratio": snapshot.get("debt_ratio") is not None and snapshot["debt_ratio"] <= max_debt_ratio,
        "gross_margin": snapshot.get("gross_margin") is not None and snapshot["gross_margin"] >= min_gross_margin,
        "free_cash_flow": (
            snapshot.get("free_cash_flow") is not None and snapshot["free_cash_flow"] > 0
            if require_positive_fcf
            else True
        ),
    }
    passed = all(checks.values())
    return {"passed": passed, "checks": checks}


def _indicator_cache_path(stock_id: str, years: int) -> Path:
    return TECHNICAL_FEATURE_CACHE_DIR / f"{stock_id}_{years}y_rsi_features.csv"


def _gate_cache_path(stock_id: str) -> Path:
    return FUNDAMENTAL_GATE_CACHE_DIR / f"{stock_id}_fundamental_gate.json"


def _is_gate_cache_stale(payload: dict) -> bool:
    generated_at = payload.get("generated_at")
    if not generated_at:
        return True
    try:
        generated_date = datetime.strptime(generated_at, "%Y-%m-%d").date()
    except ValueError:
        return True
    return datetime.today().date() - generated_date >= timedelta(days=FUNDAMENTAL_GATE_TTL_DAYS)


def _load_or_build_indicator_data(stock_id: str, years: int, force_refresh: bool = False) -> pd.DataFrame:
    TECHNICAL_FEATURE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = _indicator_cache_path(stock_id, years)

    if cache_path.exists() and not force_refresh:
        cached = pd.read_csv(cache_path)
        if not cached.empty and {"Date", "Close", "RSI", "MA20"}.issubset(set(cached.columns)):
            cached["Date"] = pd.to_datetime(cached["Date"], errors="coerce")
            return cached.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    df = get_feature_data(stock_id=stock_id, lookback_months=years * 12, include_chip=False, force_refresh=force_refresh)
    if df is None or df.empty:
        raise ValueError("價格資料不足")

    data = df.copy().sort_values("Date").reset_index(drop=True)
    data["RSI"] = calc_rsi(data)
    data["MA20"] = data["Close"].rolling(20).mean()

    data.to_csv(cache_path, index=False, encoding="utf-8")
    return data


def _load_or_build_fundamental_gate(stock_id: str, force_refresh: bool = False) -> tuple[dict, dict]:
    FUNDAMENTAL_GATE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = _gate_cache_path(stock_id)

    if cache_path.exists() and not force_refresh:
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            if not _is_gate_cache_stale(payload):
                return payload.get("snapshot", {}), payload.get("gate", {"passed": False, "checks": {}})
        except json.JSONDecodeError:
            pass

    snapshot = prepare_fundamental_snapshot(stock_id)
    gate = evaluate_fundamental_gate(snapshot)
    payload = {
        "stock_id": stock_id,
        "generated_at": datetime.today().strftime("%Y-%m-%d"),
        "snapshot": snapshot,
        "gate": gate,
    }
    cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return snapshot, gate


def run_rsi_fundamental_backtest(
    stock_id: str,
    years: int = 5,
    initial_capital: float = 1_000_000,
    risk_pct: float = 0.02,
    rsi_entry: float = 30,
    rsi_exit: float = 70,
    stop_loss_pct: float = 0.08,
    force_refresh: bool = False,
):
    data = _load_or_build_indicator_data(stock_id=stock_id, years=years, force_refresh=force_refresh)
    fundamental, gate = _load_or_build_fundamental_gate(stock_id=stock_id, force_refresh=force_refresh)

    if not gate["passed"]:
        return {
            "stock_id": stock_id,
            "initial_capital": float(initial_capital),
            "final_equity": float(initial_capital),
            "total_trades": 0,
            "win_rate": 0,
            "avg_return": 0,
            "max_drawdown": 0,
            "fundamental_gate": gate,
            "fundamental_snapshot": fundamental,
            "trade_logs": [],
            "cache": {
                "indicator_cache": str(_indicator_cache_path(stock_id, years)),
                "fundamental_gate_cache": str(_gate_cache_path(stock_id)),
            },
        }

    cash = float(initial_capital)
    shares = 0.0
    entry_price = None
    stop_loss = None
    trade_logs = []
    equity_curve = []

    for i in range(21, len(data)):
        row = data.iloc[i]
        prev = data.iloc[i - 1]
        close = float(row["Close"])
        date = row["Date"]

        rsi = row["RSI"]
        prev_rsi = prev["RSI"]
        ma20 = row["MA20"]

        if pd.isna(rsi) or pd.isna(prev_rsi) or pd.isna(ma20):
            continue

        if shares > 0:
            should_exit = close <= stop_loss or rsi >= rsi_exit
            if should_exit:
                proceeds = shares * close
                pnl_pct = (close - entry_price) / entry_price
                cash += proceeds
                trade_logs.append(
                    {
                        "date": date,
                        "action": "SELL",
                        "price": close,
                        "shares": shares,
                        "pnl_pct": pnl_pct,
                        "reason": "stop_loss" if close <= stop_loss else "rsi_exit",
                    }
                )
                shares = 0
                entry_price = None
                stop_loss = None
        else:
            rsi_rebound = prev_rsi < rsi_entry and rsi >= rsi_entry
            trend_ok = close > ma20
            if rsi_rebound and trend_ok:
                risk_budget = cash * risk_pct
                stop_loss_candidate = close * (1 - stop_loss_pct)
                risk_per_share = close - stop_loss_candidate
                if risk_per_share <= 0:
                    continue
                buy_shares = min(risk_budget / risk_per_share, cash / close)
                if buy_shares <= 0:
                    continue

                cost = buy_shares * close
                cash -= cost
                shares = buy_shares
                entry_price = close
                stop_loss = stop_loss_candidate
                trade_logs.append(
                    {
                        "date": date,
                        "action": "BUY",
                        "price": close,
                        "shares": buy_shares,
                        "rsi": float(rsi),
                    }
                )

        equity = cash + shares * close
        equity_curve.append({"date": date, "equity": equity})

    if shares > 0:
        last_row = data.iloc[-1]
        close = float(last_row["Close"])
        proceeds = shares * close
        pnl_pct = (close - entry_price) / entry_price
        cash += proceeds
        trade_logs.append(
            {
                "date": last_row["Date"],
                "action": "SELL",
                "price": close,
                "shares": shares,
                "pnl_pct": pnl_pct,
                "reason": "end_of_backtest",
            }
        )

    sells = [t for t in trade_logs if t["action"] == "SELL"]
    wins = [t for t in sells if t.get("pnl_pct", 0) > 0]

    win_rate = (len(wins) / len(sells) * 100) if sells else 0
    avg_return = (sum(t.get("pnl_pct", 0) for t in sells) / len(sells) * 100) if sells else 0

    eq = pd.DataFrame(equity_curve)
    max_drawdown = 0
    if not eq.empty:
        eq["peak"] = eq["equity"].cummax()
        eq["dd"] = (eq["equity"] - eq["peak"]) / eq["peak"]
        max_drawdown = eq["dd"].min() * 100

    return {
        "stock_id": stock_id,
        "initial_capital": float(initial_capital),
        "final_equity": round(cash, 2),
        "total_trades": len(sells),
        "win_rate": round(win_rate, 2),
        "avg_return": round(avg_return, 2),
        "max_drawdown": round(max_drawdown, 2),
        "fundamental_gate": gate,
        "fundamental_snapshot": fundamental,
        "trade_logs": trade_logs,
        "cache": {
            "indicator_cache": str(_indicator_cache_path(stock_id, years)),
            "fundamental_gate_cache": str(_gate_cache_path(stock_id)),
        },
    }
