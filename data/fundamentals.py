from __future__ import annotations

import re
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
    def _is_valid(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str) and value.strip() == "":
            return False
        try:
            if pd.isna(value):
                return False
        except TypeError:
            pass
        return True

    def _normalize_key(key: Any) -> str:
        text = str(key or "")
        text = text.strip().lower()
        text = text.replace("（", "(").replace("）", ")")
        return re.sub(r"[^\w\u4e00-\u9fff]", "", text)

    for key in aliases:
        if key not in data:
            continue

        value = data[key]
        if not _is_valid(value):
            continue

        return value

    normalized_map: Dict[str, Any] = {}
    for key, value in data.items():
        if not _is_valid(value):
            continue
        normalized = _normalize_key(key)
        if normalized and normalized not in normalized_map:
            normalized_map[normalized] = value

    normalized_aliases = [_normalize_key(alias) for alias in aliases if _normalize_key(alias)]

    # Match after normalizing punctuation / casing differences first.
    for alias in normalized_aliases:
        if alias in normalized_map:
            return normalized_map[alias]

    # Then allow containment matches for longer provider-specific labels.
    for alias in normalized_aliases:
        for key, value in normalized_map.items():
            if alias in key or key in alias:
                return value

    return None


def _normalize_ratio_value(value: Any) -> float | None:
    """Normalize ratio-like values into percentage points.

    Upstream providers may return the same metric either as a decimal ratio
    (e.g. 0.2329) or percentage points (e.g. 23.29). Values that are clearly
    out of range for ratios are treated as invalid and returned as None.
    """
    numeric = _to_float(value)
    if numeric is None:
        return None

    # Decimal ratio -> percentage points.
    if -1 <= numeric <= 1:
        return numeric * 100

    # Typical percentage points.
    if -100 <= numeric <= 100:
        return numeric

    # Ratios slightly above 100 can exist for edge cases, but very large values
    # almost always indicate we accidentally picked an amount field.
    if -1000 <= numeric <= 1000:
        return numeric

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


def load_income_statement_trend(stock_id: str) -> pd.DataFrame:
    """Load income statement records and convert them into a date/type pivot table."""
    raw_data = fetch_fundamentals(stock_id)
    income_df = raw_data.get("income_statement", pd.DataFrame())
    if income_df is None or income_df.empty:
        return pd.DataFrame()

    required = {"date", "type", "value"}
    if not required.issubset(set(income_df.columns)):
        return pd.DataFrame()

    local_df = income_df.copy()
    local_df["date"] = pd.to_datetime(local_df["date"], errors="coerce")
    local_df = local_df.dropna(subset=["date"])
    if local_df.empty:
        return pd.DataFrame()

    pivot_df = (
        local_df.pivot_table(index="date", columns="type", values="value", aggfunc="first")
        .sort_index()
        .reset_index()
    )
    return pivot_df


def _statement_rows_by_date(df: pd.DataFrame, aggfunc: str = "first") -> pd.DataFrame:
    """Normalize statement data into one row per date.

    Supports both long format (date/type/value) and wide format
    (date + metric columns).
    """
    if df is None or df.empty or "date" not in df.columns:
        return pd.DataFrame()

    local_df = df.copy()
    local_df["date"] = pd.to_datetime(local_df["date"], errors="coerce")
    local_df = local_df.dropna(subset=["date"])
    if local_df.empty:
        return pd.DataFrame()

    # Long format: one metric per row identified by `type`.
    if {"type", "value"}.issubset(set(local_df.columns)):
        return local_df.pivot_table(index="date", columns="type", values="value", aggfunc=aggfunc).sort_index().reset_index()

    # Wide format: each metric is already a standalone column.
    metric_cols = [col for col in local_df.columns if col != "date"]
    if not metric_cols:
        return pd.DataFrame()

    agg_map: Dict[str, str] = {}
    for col in metric_cols:
        if aggfunc == "sum" and pd.api.types.is_numeric_dtype(local_df[col]):
            agg_map[col] = "sum"
        else:
            agg_map[col] = "first"

    return local_df.groupby("date", as_index=False).agg(agg_map).sort_values("date").reset_index(drop=True)


def _latest_statement_row(df: pd.DataFrame, aggfunc: str = "first") -> Dict[str, Any]:
    statement_df = _statement_rows_by_date(df, aggfunc=aggfunc)
    if statement_df.empty:
        return {}

    latest = statement_df.iloc[-1].to_dict()
    latest["date"] = statement_df.iloc[-1]["date"]
    return latest


def _latest_non_null_from_statement(df: pd.DataFrame, aliases: Iterable[str], aggfunc: str = "first") -> Any:
    """Return the latest non-null metric value from a statement table.

    Some providers may omit specific fields on the newest disclosure date.
    This helper scans from newest to oldest and returns the first available
    value matching the alias list.
    """
    statement_df = _statement_rows_by_date(df, aggfunc=aggfunc)
    if statement_df.empty:
        return None

    for idx in range(len(statement_df) - 1, -1, -1):
        row = statement_df.iloc[idx].to_dict()
        value = _first_non_null(row, aliases)
        if value is not None:
            return value

    return None


def prepare_fundamental_snapshot(stock_id: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if payload is None:
        raw_data = fetch_fundamentals(stock_id)
    else:
        raw_data = {
            "stock_id": stock_id,
            "source": payload.get("source", "finmind") if isinstance(payload, dict) else "finmind",
            "income_statement": pd.DataFrame((payload or {}).get("income_statement", [])),
            "balance_sheet": pd.DataFrame((payload or {}).get("balance_sheet", [])),
            "cashflow_statement": pd.DataFrame((payload or {}).get("cashflow_statement", [])),
        }


    income_latest = _latest_statement_row(raw_data.get("income_statement", pd.DataFrame()))
    balance_latest = _latest_statement_row(raw_data.get("balance_sheet", pd.DataFrame()))
    cashflow_latest = _latest_statement_row(raw_data.get("cashflow_statement", pd.DataFrame()), aggfunc="sum")

    roe_value = _first_non_null(
        income_latest,
        ["ROE(%)", "權益報酬率(ROE)", "股東權益報酬率", "ROE", "ReturnOnEquity", "return_on_equity"],
    )
    gross_margin_value = _first_non_null(
        income_latest,
        [
            "營業毛利率(%)",
            "毛利率(%)",
            "gross_margin",
            "Gross Margin",
            "GrossMargin",
            "GrossProfitMargin",
            "grossProfitMargin",
        ],
    )

    debt_ratio_value = _first_non_null(
        balance_latest,
        [
            "負債比率",
            "負債比率(%)",
            "資產負債率",
            "負債佔資產比率",
            "Debt Ratio",
            "debt_ratio",
            "DebtRatio",
            "liability_ratio",
            "Liabilities to Assets Ratio",
            "Debt to Asset Ratio",
        ],
    )

    gross_margin_value = _normalize_ratio_value(gross_margin_value)

    if gross_margin_value is None:
        gross_profit_value = _to_float(
            _first_non_null(
                income_latest,
                ["GrossProfit", "營業毛利（毛損）淨額", "營業毛利", "毛利", "gross_profit"],
            )
        )
        revenue_value = _to_float(
            _first_non_null(income_latest, ["Revenue", "營業收入合計", "營業收入", "營收", "TotalRevenue", "total_revenue"])
        )
        if gross_profit_value is not None and revenue_value not in (None, 0):
            # Snapshot columns are displayed as percentage points (e.g., 23.29)
            gross_margin_value = gross_profit_value / revenue_value * 100

    total_liabilities = _to_float(
        _first_non_null(
            balance_latest,
            ["負債總額", "負債總計", "Total liabilities", "total_liabilities", "TotalLiabilities"],
        )
    )
    total_assets = _to_float(
        _first_non_null(balance_latest, ["資產總額", "資產總計", "Total assets", "total_assets", "TotalAssets"])
    )

    debt_ratio_value = _normalize_ratio_value(debt_ratio_value)

    if debt_ratio_value is None:
        if total_liabilities is not None and total_assets not in (None, 0):
            debt_ratio_value = total_liabilities / total_assets * 100

    if roe_value is None:
        net_income_after_tax = _to_float(
            _first_non_null(
                income_latest,
                [
                    "ProfitLoss",
                    "本期淨利（淨損）",
                    "本期淨利(淨損)",
                    "NetIncome",
                    "NetIncomeLoss",
                    "IncomeAfterTaxes",
                ],
            )
        )
        total_equity = _to_float(
            _first_non_null(
                balance_latest,
                ["權益總額", "權益總計", "TotalEquity", "Equity", "Total equity", "total_equity"],
            )
        )
        if net_income_after_tax is not None and total_equity not in (None, 0):
            roe_value = net_income_after_tax / total_equity * 100

    cashflow_df = raw_data.get("cashflow_statement", pd.DataFrame())
    operating_aliases = [
        "營業活動之淨現金流入（流出）",
        "營業活動之淨現金流入(流出)",
        "營業活動現金流量",
        "營運產生之現金流入(流出)",
        "營運活動之淨現金流入(流出)",
        "營運活動現金流量",
        "Net cash flows from operating activities",
        "CashFlowsFromOperatingActivities",
        "CashProvidedByOperatingActivities",
        "OperatingCashFlow",
        "NetCashFromOperatingActivities",
        "NetCashInflowFromOperatingActivities",
    ]
    investing_aliases = [
        "投資活動之淨現金流入（流出）",
        "投資活動之淨現金流入(流出)",
        "投資活動現金流量",
        "取得不動產、廠房及設備",
        "Net cash flows from investing activities",
        "CashFlowsFromInvestingActivities",
        "CashProvidedByInvestingActivities",
        "InvestingCashFlow",
        "NetCashFromInvestingActivities",
        "NetCashInflowFromInvestingActivities",
        "NetCashFlowsFromUsedInInvestingActivities",
        "NetCashFlowsUsedInInvestingActivities",
    ]

    operating_cf = _to_float(_first_non_null(cashflow_latest, operating_aliases))
    investing_cf = _to_float(_first_non_null(cashflow_latest, investing_aliases))

    # Fallback: If latest statement date misses these fields, look back to the
    # nearest prior period with available values.
    if operating_cf is None:
        operating_cf = _to_float(_latest_non_null_from_statement(cashflow_df, operating_aliases, aggfunc="sum"))
    if investing_cf is None:
        investing_cf = _to_float(_latest_non_null_from_statement(cashflow_df, investing_aliases, aggfunc="sum"))

    if investing_cf is None:
        capex_value = _to_float(
            _first_non_null(
                cashflow_latest,
                [
                    "取得不動產、廠房及設備",
                    "AcquisitionOfPropertyPlantAndEquipment",
                    "PurchaseOfPropertyPlantAndEquipment",
                ],
            )
        )
        # FCF = OCF + investing cash flow. If only CAPEX is available, convert
        # it to investing cash flow by negating CAPEX outflow.
        if capex_value is not None:
            investing_cf = -capex_value

    free_cash_flow = operating_cf + investing_cf if operating_cf is not None and investing_cf is not None else None

    candidate_dates = [income_latest.get("date"), balance_latest.get("date"), cashflow_latest.get("date")]
    as_of_dt = max([d for d in candidate_dates if pd.notna(d)], default=None)

    return {
        "roe": _normalize_ratio_value(roe_value),
        "debt_ratio": _to_float(debt_ratio_value),
        "free_cash_flow": free_cash_flow,
        "gross_margin": _to_float(gross_margin_value),
        "as_of": as_of_dt.strftime("%Y-%m-%d") if as_of_dt is not None else None,
        "source": raw_data.get("source", "unknown"),
    }
