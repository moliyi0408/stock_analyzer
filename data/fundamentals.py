from __future__ import annotations

from typing import Any, Dict, Iterable

import pandas as pd

from data.fetch_fundamental import fetch_fundamental


def _to_float(value: Any) -> float | None:
    if value is None or value is pd.NA:
        return None

    if isinstance(value, (int, float)):
        if pd.isna(value):
            return None
        return float(value)

    text = str(value).strip()
    if not text or text.lower() in {"none", "nan", "na", "n/a", "--"}:
        return None

    text = text.replace(",", "")
    if text.endswith("%"):
        text = text[:-1].strip()

    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _first_non_null(data: Dict[str, Any], aliases: Iterable[str]) -> Any:
    for key in aliases:
        if key in data and data[key] not in (None, "", pd.NA):
            return data[key]
    return None


def fetch_fundamentals(stock_id: str) -> Dict[str, Any]:
    """Fetch raw fundamentals with cache-first strategy."""
    raw = fetch_fundamental(stock_id)
    return {
        "stock_id": stock_id,
        "source": raw.get("source", "finmind"),
        "income_statement": pd.DataFrame(raw.get("income_statement", [])),
        "balance_sheet": pd.DataFrame(raw.get("balance_sheet", [])),
        "cashflow_statement": pd.DataFrame(raw.get("cashflow_statement", [])),
    }


def _latest_statement_row(df: pd.DataFrame) -> Dict[str, Any]:
    if df is None or df.empty:
        return {}

    local_df = df.copy()
    if "date" not in local_df.columns or "type" not in local_df.columns or "value" not in local_df.columns:
        return {}

    local_df["date"] = pd.to_datetime(local_df["date"], errors="coerce")
    local_df = local_df.dropna(subset=["date"])
    if local_df.empty:
        return {}

    pivot_df = local_df.pivot_table(index="date", columns="type", values="value", aggfunc="first").sort_index().reset_index()
    if pivot_df.empty:
        return {}

    latest = pivot_df.iloc[-1].to_dict()
    latest["date"] = pivot_df.iloc[-1]["date"]
    return latest


def prepare_fundamental_snapshot(stock_id: str) -> Dict[str, Any]:
    raw_data = fetch_fundamentals(stock_id)

    income_latest = _latest_statement_row(raw_data.get("income_statement", pd.DataFrame()))
    balance_latest = _latest_statement_row(raw_data.get("balance_sheet", pd.DataFrame()))
    cashflow_latest = _latest_statement_row(raw_data.get("cashflow_statement", pd.DataFrame()))

    roe_value = _first_non_null(income_latest, ["ROE(%)", "權益報酬率(ROE)", "股東權益報酬率", "ROE"])
    gross_margin_value = _first_non_null(income_latest, ["營業毛利率(%)", "毛利率(%)", "gross_margin", "Gross Margin"])

    debt_ratio_value = _first_non_null(balance_latest, ["負債比率", "負債比率(%)", "Debt Ratio", "debt_ratio"])

    if debt_ratio_value is None:
        total_liabilities = _to_float(_first_non_null(balance_latest, ["負債總額", "負債總計", "Total liabilities", "total_liabilities"]))
        total_assets = _to_float(_first_non_null(balance_latest, ["資產總額", "資產總計", "Total assets", "total_assets"]))
        if total_liabilities is not None and total_assets not in (None, 0):
            debt_ratio_value = total_liabilities / total_assets * 100

    operating_cf = _to_float(
        _first_non_null(
            cashflow_latest,
            ["營業活動之淨現金流入（流出）", "營業活動之淨現金流入(流出)", "營業活動現金流量", "Net cash flows from operating activities"],
        )
    )
    investing_cf = _to_float(
        _first_non_null(
            cashflow_latest,
            ["投資活動之淨現金流入（流出）", "投資活動之淨現金流入(流出)", "投資活動現金流量", "Net cash flows from investing activities"],
        )
    )

    free_cash_flow = operating_cf + investing_cf if operating_cf is not None and investing_cf is not None else None

    candidate_dates = [income_latest.get("date"), balance_latest.get("date"), cashflow_latest.get("date")]
    as_of_dt = max([d for d in candidate_dates if pd.notna(d)], default=None)

    return {
        "roe": _to_float(roe_value),
        "debt_ratio": _to_float(debt_ratio_value),
        "free_cash_flow": free_cash_flow,
        "gross_margin": _to_float(gross_margin_value),
        "as_of": as_of_dt.strftime("%Y-%m-%d") if as_of_dt is not None else None,
        "source": raw_data.get("source", "unknown"),
    }
