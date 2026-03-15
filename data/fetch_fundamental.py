from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict

import pandas as pd
import requests

from data.storage_paths import FUNDAMENTAL_CACHE_DIR

FINMIND_API_URL = "https://api.finmindtrade.com/api/v4/data"
FUNDAMENTAL_TTL_DAYS = 90


def _request_finmind(dataset: str, stock_id: str, timeout: int = 10) -> pd.DataFrame:
    params = {
        "dataset": dataset,
        "data_id": stock_id,
        "start_date": "2018-01-01",
        "end_date": datetime.today().strftime("%Y-%m-%d"),
    }
    try:
        response = requests.get(FINMIND_API_URL, params=params, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        records = payload.get("data", []) if isinstance(payload, dict) else []
        return pd.DataFrame(records) if records else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _fetch_from_api(stock_id: str) -> Dict[str, Any]:
    return {
        "stock_id": stock_id,
        "source": "finmind",
        "updated_at": datetime.today().strftime("%Y-%m-%d"),
        "income_statement": _request_finmind("TaiwanStockFinancialStatements", stock_id).to_dict(orient="records"),
        "balance_sheet": _request_finmind("TaiwanStockBalanceSheet", stock_id).to_dict(orient="records"),
        "cashflow_statement": _request_finmind("TaiwanStockCashFlowsStatement", stock_id).to_dict(orient="records"),
    }


def _is_stale(payload: Dict[str, Any]) -> bool:
    updated_at = payload.get("updated_at")
    if not updated_at:
        return True
    try:
        updated = datetime.strptime(updated_at, "%Y-%m-%d").date()
    except ValueError:
        return True
    return (datetime.today().date() - updated).days >= FUNDAMENTAL_TTL_DAYS


def _has_core_statements(payload: Dict[str, Any]) -> bool:
    """Check whether at least one fundamental statement has usable records."""
    if not isinstance(payload, dict):
        return False

    return any(payload.get(section) for section in ["income_statement", "balance_sheet", "cashflow_statement"])


def fetch_fundamental(stock_id: str, force_refresh: bool = False) -> Dict[str, Any]:
    """Get fundamental data from cache first, refresh every 90 days."""
    FUNDAMENTAL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = FUNDAMENTAL_CACHE_DIR / f"{stock_id}_fundamental.json"
    legacy_cache_file = FUNDAMENTAL_CACHE_DIR / f"{stock_id}.json"

    if not force_refresh:
        for candidate in (cache_file, legacy_cache_file):
            if not candidate.exists():
                continue
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8"))
                # Empty payloads are often produced by transient API issues and
                # should not be trusted for the full TTL window.
                if not _is_stale(payload) and _has_core_statements(payload):
                    return payload
            except json.JSONDecodeError:
                continue

    payload = _fetch_from_api(stock_id)
    cache_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload
