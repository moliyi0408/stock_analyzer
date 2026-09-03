from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict

import pandas as pd
import requests

from data.storage_paths import FUNDAMENTAL_CACHE_DIR

FINMIND_API_URL = "https://api.finmindtrade.com/api/v4/data"
FUNDAMENTAL_TTL_DAYS = 90
LOGGER = logging.getLogger(__name__)

DATASETS = {
    "income_statement": "TaiwanStockFinancialStatements",
    "balance_sheet": "TaiwanStockBalanceSheet",
    "cashflow_statement": "TaiwanStockCashFlowsStatement",
}


def _request_finmind(dataset: str, stock_id: str, timeout: int = 10) -> tuple[pd.DataFrame, Dict[str, Any]]:
    """Request one FinMind dataset and retain diagnostic details on every outcome."""
    params = {
        "dataset": dataset,
        "data_id": stock_id,
        "start_date": "2018-01-01",
        "end_date": datetime.today().strftime("%Y-%m-%d"),
    }
    diagnostic: Dict[str, Any] = {"dataset": dataset, "status": "error", "record_count": 0}
    try:
        response = requests.get(FINMIND_API_URL, params=params, timeout=timeout)
        diagnostic["http_status"] = response.status_code
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        diagnostic["message"] = str(exc)
        LOGGER.warning("FinMind request failed for stock_id=%s dataset=%s: %s", stock_id, dataset, exc)
        return pd.DataFrame(), diagnostic

    if not isinstance(payload, dict):
        diagnostic["message"] = "FinMind returned a non-object JSON payload"
        LOGGER.warning("FinMind returned an invalid payload for stock_id=%s dataset=%s", stock_id, dataset)
        return pd.DataFrame(), diagnostic

    api_status = payload.get("status")
    api_message = payload.get("msg")
    records = payload.get("data")
    diagnostic.update({"api_status": api_status, "message": api_message})
    if api_status not in (None, 0, 200, "success"):
        diagnostic["message"] = api_message or f"FinMind API status {api_status}"
        LOGGER.warning("FinMind API rejected stock_id=%s dataset=%s: %s", stock_id, dataset, diagnostic["message"])
        return pd.DataFrame(), diagnostic
    if not isinstance(records, list):
        diagnostic["message"] = api_message or "FinMind response field 'data' is not a list"
        LOGGER.warning("FinMind returned malformed data for stock_id=%s dataset=%s", stock_id, dataset)
        return pd.DataFrame(), diagnostic

    diagnostic["record_count"] = len(records)
    diagnostic["status"] = "success" if records else "no_data"
    if not records:
        LOGGER.info("FinMind returned no records for stock_id=%s dataset=%s: %s", stock_id, dataset, api_message)
    return pd.DataFrame(records), diagnostic


def _latest_data_date(records: list[Dict[str, Any]]) -> str | None:
    date_values = pd.DataFrame(records).get("date") if records else None
    if date_values is None:
        return None
    dates = pd.to_datetime(date_values, errors="coerce")
    latest = dates.max() if not dates.empty else pd.NaT
    return latest.strftime("%Y-%m-%d") if pd.notna(latest) else None


def _fetch_from_api(stock_id: str) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "stock_id": stock_id,
        "source": "finmind",
        # fetched_at is intentionally separate from the financial statement date.
        "fetched_at": datetime.today().strftime("%Y-%m-%d"),
        "datasets": {},
    }
    for section, dataset in DATASETS.items():
        frame, diagnostic = _request_finmind(dataset, stock_id)
        records = frame.to_dict(orient="records")
        payload[section] = records
        payload["datasets"][section] = diagnostic

    payload["data_as_of"] = max(
        (_latest_data_date(payload[section]) for section in DATASETS),
        key=lambda value: value or "",
        default=None,
    )
    statuses = [details["status"] for details in payload["datasets"].values()]
    payload["fetch_status"] = "success" if any(status == "success" for status in statuses) else (
        "no_data" if all(status == "no_data" for status in statuses) else "error"
    )
    return payload


def _is_stale(payload: Dict[str, Any]) -> bool:
    if not _has_core_statements(payload):
        return True

    # `updated_at` remains supported for caches created by earlier versions.
    fetched_at = payload.get("fetched_at") or payload.get("updated_at")
    if not fetched_at:
        return True
    try:
        fetched = datetime.strptime(fetched_at, "%Y-%m-%d").date()
    except ValueError:
        return True
    return (datetime.today().date() - fetched).days >= FUNDAMENTAL_TTL_DAYS


def _has_core_statements(payload: Dict[str, Any]) -> bool:
    """Check whether at least one fundamental statement has usable records."""
    return isinstance(payload, dict) and any(
        isinstance(payload.get(section), list) and payload[section] for section in DATASETS
    )


def fetch_fundamental(stock_id: str, force_refresh: bool = False) -> Dict[str, Any]:
    """Get fundamental data from cache first and return API diagnostics when a refresh fails."""
    FUNDAMENTAL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = FUNDAMENTAL_CACHE_DIR / f"{stock_id}_fundamental.json"
    legacy_cache_file = FUNDAMENTAL_CACHE_DIR / f"{stock_id}.json"

    if not force_refresh:
        for candidate in (cache_file, legacy_cache_file):
            if not candidate.exists():
                continue
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8"))
                if not _is_stale(payload) and _has_core_statements(payload):
                    payload.setdefault("fetch_status", "success")
                    payload.setdefault("cache_hit", True)
                    return payload
            except (OSError, json.JSONDecodeError) as exc:
                LOGGER.warning("Unable to read fundamental cache %s: %s", candidate, exc)

    payload = _fetch_from_api(stock_id)
    payload["cache_hit"] = False
    if _has_core_statements(payload):
        cache_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload
