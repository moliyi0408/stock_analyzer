from pathlib import Path
from typing import Optional

import pandas as pd

from data.storage_paths import CHIP_CACHE_DIR


STANDARD_CHIP_COLUMNS = [
    "Date",
    "foreign_net_buy",
    "investment_net_buy",
    "dealer_net_buy",
    "margin_balance",
    "short_balance",
    "margin_change_1d",
    "margin_change_5d",
    "holder_1000_up_ratio",
    "holder_retail_ratio",
]


CHIP_COLUMN_ALIASES = {
    "Date": ["Date", "date", "日期"],
    "foreign_net_buy": ["foreign_net_buy", "外資買賣超", "foreign"],
    "investment_net_buy": ["investment_net_buy", "投信買賣超", "investment"],
    "dealer_net_buy": ["dealer_net_buy", "自營商買賣超", "dealer"],
    "margin_balance": ["margin_balance", "融資餘額", "margin"],
    "short_balance": ["short_balance", "融券餘額", "short"],
    "holder_1000_up_ratio": ["holder_1000_up_ratio", "大戶持股比", "holder_large_ratio"],
    "holder_retail_ratio": ["holder_retail_ratio", "散戶持股比", "holder_retail"],
}


def _pick_first_existing(df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _resolve_chip_path(stock_id: str) -> Path:
    """先找新路徑 datas/chip/{stock_id}_chip.csv，再回退到舊檔名。"""
    new_path = CHIP_CACHE_DIR / f"{stock_id}_chip.csv"
    if new_path.exists():
        return new_path

    legacy_candidates = [
        CHIP_CACHE_DIR / f"chip_{stock_id}.csv",
        Path("datas") / f"chip_{stock_id}.csv",
        Path("data") / f"chip_{stock_id}.csv",
    ]
    for path in legacy_candidates:
        if path.exists():
            return path

    return new_path


def normalize_chip_dataframe(chip_df: pd.DataFrame) -> pd.DataFrame:
    """標準化籌碼欄位，輸出統一 schema。"""
    if chip_df is None or chip_df.empty:
        return pd.DataFrame(columns=STANDARD_CHIP_COLUMNS)

    output = pd.DataFrame(index=chip_df.index)
    for standard_col, aliases in CHIP_COLUMN_ALIASES.items():
        found_col = _pick_first_existing(chip_df, aliases)
        output[standard_col] = chip_df[found_col] if found_col else pd.NA

    output["Date"] = pd.to_datetime(output["Date"], errors="coerce")

    numeric_cols = [c for c in STANDARD_CHIP_COLUMNS if c != "Date"]
    for col in numeric_cols:
        output[col] = pd.to_numeric(output[col], errors="coerce")

    output = output.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    output["margin_change_1d"] = output["margin_balance"].diff(1)
    output["margin_change_5d"] = output["margin_balance"].diff(5)
    return output


def load_chip_csv(stock_id: str) -> pd.DataFrame:
    """讀取 datas/chip/{stock_id}_chip.csv 並標準化欄位。"""
    chip_path = _resolve_chip_path(stock_id)
    if not chip_path.exists():
        return pd.DataFrame(columns=STANDARD_CHIP_COLUMNS)

    chip_df = pd.read_csv(chip_path)
    return normalize_chip_dataframe(chip_df)
