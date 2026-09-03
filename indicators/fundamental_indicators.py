from __future__ import annotations

from typing import Any, Iterable

import pandas as pd

from data.fundamentals import (
    EPS_ALIASES,
    GROSS_PROFIT_ALIASES,
    OPERATING_INCOME_ALIASES,
    REVENUE_ALIASES,
    _first_non_null,
)


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    num = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(num):
        return None
    return float(num)


def _pick_first_value(row: pd.Series, aliases: Iterable[str]) -> float | None:
    return _to_float(_first_non_null(row.to_dict(), aliases))


def calc_fundamental_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate common fundamental indicators from pivot income statement data."""
    if df is None or df.empty:
        return pd.DataFrame()

    local_df = df.copy()
    if "date" not in local_df.columns:
        return pd.DataFrame()

    local_df["date"] = pd.to_datetime(local_df["date"], errors="coerce")
    local_df = local_df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    revenues = []
    gross_profits = []
    operating_incomes = []
    eps_values = []

    for _, row in local_df.iterrows():
        revenues.append(_pick_first_value(row, REVENUE_ALIASES))
        gross_profits.append(_pick_first_value(row, GROSS_PROFIT_ALIASES))
        operating_incomes.append(_pick_first_value(row, OPERATING_INCOME_ALIASES))
        eps_values.append(_pick_first_value(row, EPS_ALIASES))

    local_df["Revenue"] = revenues
    local_df["GrossProfit"] = gross_profits
    local_df["OperatingIncome"] = operating_incomes
    local_df["EPS"] = eps_values

    local_df["GrossMargin"] = local_df["GrossProfit"] / local_df["Revenue"]
    local_df["OperatingMargin"] = local_df["OperatingIncome"] / local_df["Revenue"]
    local_df["EPS_change"] = local_df["EPS"].pct_change()

    return local_df
