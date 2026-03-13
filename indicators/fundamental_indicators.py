from __future__ import annotations

from typing import Any, Iterable

import pandas as pd


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    num = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(num):
        return None
    return float(num)


def _pick_first_value(row: pd.Series, aliases: Iterable[str]) -> float | None:
    for key in aliases:
        if key in row.index:
            value = _to_float(row.get(key))
            if value is not None:
                return value
    return None


def calc_fundamental_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate common fundamental indicators from pivot income statement data."""
    if df is None or df.empty:
        return pd.DataFrame()

    local_df = df.copy()
    if "date" not in local_df.columns:
        return pd.DataFrame()

    local_df["date"] = pd.to_datetime(local_df["date"], errors="coerce")
    local_df = local_df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    revenue_aliases = ["Revenue", "營業收入合計", "營業收入", "營收", "TotalRevenue"]
    gross_profit_aliases = ["GrossProfit", "營業毛利（毛損）淨額", "營業毛利", "毛利"]
    operating_income_aliases = ["OperatingIncome", "營業利益（損失）", "營業利益", "OperatingIncomeLoss"]
    eps_aliases = ["EPS", "基本每股盈餘（元）", "每股盈餘", "每股盈餘(元)"]

    revenues = []
    gross_profits = []
    operating_incomes = []
    eps_values = []

    for _, row in local_df.iterrows():
        revenues.append(_pick_first_value(row, revenue_aliases))
        gross_profits.append(_pick_first_value(row, gross_profit_aliases))
        operating_incomes.append(_pick_first_value(row, operating_income_aliases))
        eps_values.append(_pick_first_value(row, eps_aliases))

    local_df["Revenue"] = revenues
    local_df["GrossProfit"] = gross_profits
    local_df["OperatingIncome"] = operating_incomes
    local_df["EPS"] = eps_values

    local_df["GrossMargin"] = local_df["GrossProfit"] / local_df["Revenue"]
    local_df["OperatingMargin"] = local_df["OperatingIncome"] / local_df["Revenue"]
    local_df["EPS_change"] = local_df["EPS"].pct_change()

    return local_df
