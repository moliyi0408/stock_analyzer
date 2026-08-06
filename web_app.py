from pathlib import Path
from numbers import Real
from urllib.parse import parse_qs
import json
from datetime import datetime

import pandas as pd

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
PRICE_DIR = BASE_DIR / "datas" / "price"
WATCHLIST_PATH = BASE_DIR / "watchlist.json"
DEFAULT_WATCHLIST = ["1504", "2330", "0050"]
STOCK_NAMES = {
    "006208": "富邦台50",
    "0050": "元大台灣50",
    "1504": "東元",
}

app = FastAPI(title="Stock Analyzer Dashboard")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def _round(value, digits=2):
    if pd.isna(value):
        return None
    return round(float(value), digits) if isinstance(value, Real) else value


def _load_log(stock_id):
    path = LOG_DIR / f"{stock_id}.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _latest_log_entry(stock_id):
    data = _load_log(stock_id)
    if not data:
        return None
    latest_date = sorted(data.keys(), reverse=True)[0]
    payload = data.get(latest_date) or {}
    if not isinstance(payload, dict):
        return None
    return latest_date, payload



def _parse_date(value):
    parsed = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(parsed) else parsed.normalize()


def _latest_price_cache_date(stock_id):
    # 延後 import，讓 UI 啟動時不必載入完整資料流程；需要判斷 freshness 時才更新/讀取價格快取。
    from data.data_manager import get_price

    price_df = get_price(stock_id)
    if price_df is None or price_df.empty or "Date" not in price_df.columns:
        return None
    latest = pd.to_datetime(price_df["Date"], errors="coerce").max()
    return None if pd.isna(latest) else latest.normalize()


def _is_log_stale(stock_id):
    latest = _latest_log_entry(stock_id)
    if latest is None:
        return True

    log_date, _payload = latest
    parsed_log_date = _parse_date(log_date)
    if parsed_log_date is None:
        return True

    latest_price_date = _latest_price_cache_date(stock_id)
    if latest_price_date is None:
        return True

    return parsed_log_date < latest_price_date


def _run_current_analysis(stock_id):
    # 延後 import，避免單純啟動 UI 時就載入完整分析依賴。
    from main import run_analysis

    analysis = run_analysis(stock_id=stock_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="無法取得最新分析資料，請確認股票代號或資料來源。")
    return analysis


def _load_history(stock_id, reverse=True):
    rows = []
    items = sorted(_load_log(stock_id).items(), reverse=reverse)
    for date, payload in items:
        decision = payload.get("decision", {}) if isinstance(payload, dict) else {}
        rr = decision.get("rr_metrics", {}) if isinstance(decision, dict) else {}
        rows.append({
            "date": date,
            "close": _round(payload.get("close_price")),
            "ai": _round(decision.get("ai_confidence_score")),
            "rr": _round(rr.get("rr")),
            "advice": decision.get("entry_advice"),
            "score": _round(payload.get("final_score") or decision.get("final_score")),
        })
    return rows


def _load_price_chart(stock_id, limit=120):
    path = PRICE_DIR / f"{stock_id}_price.csv"
    if not path.exists():
        return {"available": False, "reason": "尚未建立價格快取，無法顯示 K 線。", "rows": []}

    df = pd.read_csv(path)
    if "Date" not in df.columns:
        return {"available": False, "reason": "價格快取缺少 Date 欄位。", "rows": []}

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date")
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col not in df.columns:
            df[col] = pd.NA
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if df.empty or df["Close"].dropna().empty:
        return {"available": False, "reason": "價格快取沒有可用收盤價。", "rows": []}

    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA60"] = df["Close"].rolling(60).mean()
    rows = df.tail(limit).where(pd.notna(df), None).to_dict("records")
    return {
        "available": True,
        "reason": "",
        "rows": [
            {
                "date": r["Date"].strftime("%Y-%m-%d"),
                "open": _round(r.get("Open")),
                "high": _round(r.get("High")),
                "low": _round(r.get("Low")),
                "close": _round(r.get("Close")),
                "volume": _round(r.get("Volume"), 0),
                "ma20": _round(r.get("MA20")),
                "ma60": _round(r.get("MA60")),
            }
            for r in rows
        ],
    }


def _normalize_stock_id(stock_id):
    return str(stock_id or "").strip().upper()


def _available_stocks():
    ids = {p.stem for p in LOG_DIR.glob("*.json")} if LOG_DIR.exists() else set()
    return sorted(ids)


def _load_watchlist():
    if not WATCHLIST_PATH.exists():
        return [stock_id for stock_id in DEFAULT_WATCHLIST if (LOG_DIR / f"{stock_id}.json").exists()]
    try:
        data = json.loads(WATCHLIST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    seen = set()
    stocks = []
    for stock_id in data:
        normalized = _normalize_stock_id(stock_id)
        if normalized and normalized not in seen:
            seen.add(normalized)
            stocks.append(normalized)
    return stocks


def _save_watchlist(stock_ids):
    normalized = []
    seen = set()
    for stock_id in stock_ids:
        stock_id = _normalize_stock_id(stock_id)
        if stock_id and stock_id not in seen:
            seen.add(stock_id)
            normalized.append(stock_id)
    WATCHLIST_PATH.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _watchlist_stocks():
    available = set(_available_stocks())
    return [stock_id for stock_id in _load_watchlist() if stock_id in available]


def _stars(score):
    if not isinstance(score, (int, float)):
        return "☆☆☆☆☆"
    filled = max(0, min(5, round(score / 20)))
    return "★" * filled + "☆" * (5 - filled)


def _tone(score):
    if not isinstance(score, (int, float)):
        return "muted"
    if score >= 70:
        return "good"
    if score >= 45:
        return "warn"
    return "bad"



def _score_label(score):
    if not isinstance(score, (int, float)):
        return "資料不足"
    if score >= 70:
        return "偏多"
    if score >= 45:
        return "中性觀察"
    return "偏弱"


def _rr_label(rr):
    if not isinstance(rr, (int, float)):
        return {"icon": "⚪", "label": "資料不足", "class": "neutral"}
    if rr >= 2:
        return {"icon": "🟢", "label": "良好", "class": "good"}
    if rr >= 1:
        return {"icon": "🟡", "label": "普通", "class": "warn"}
    return {"icon": "🔴", "label": "不佳", "class": "bad"}


def _support_distance(price, support):
    if not all(isinstance(v, (int, float)) for v in [price, support]) or price == 0:
        return None
    return _round((price - support) / price * 100, 2)


def _action_label(advice):
    text = str(advice or "資料不足")
    if any(k in text for k in ["略過", "暫不承接", "失守"]):
        return "暫避"
    if any(k in text for k in ["等待", "不追高", "拉回", "修正"]):
        return "等待"
    if any(k in text for k in ["分批", "布局", "承接"]):
        return "分批布局"
    return text[:12]


def _action_icon(action):
    if action == "暫避":
        return "🔴"
    if action == "分批布局":
        return "🟢"
    if action == "資料不足":
        return "⚪"
    return "🟡"


def _build_reasons(payload, decision):
    rr = decision.get("rr_metrics", {}) if isinstance(decision, dict) else {}
    mup = decision.get("mup_scorecard", {}) if isinstance(decision, dict) else {}
    chip_score = payload.get("chip_score") or decision.get("chip_score")
    support_level = decision.get("support_level")
    good = [
        "接近支撐" if support_level else None,
        "RR 合格" if rr.get("rr_pass") else None,
        f"AI 信心 {decision.get('ai_confidence_score')}" if decision.get("ai_confidence_score") is not None else None,
    ]
    bad = [
        "MUP 未成立" if mup.get("status_code") in (None, "IGNORE", "WATCHLIST") else None,
        "RR 未達標" if rr and not rr.get("rr_pass") else None,
        "籌碼沒有增強" if isinstance(chip_score, (int, float)) and chip_score < 50 else None,
    ]
    return [r for r in good if r], [r for r in bad if r]



def _traffic_light(action):
    if action == "分批布局":
        return {"icon": "🟢", "label": "可以布局", "class": "go"}
    if action == "暫避":
        return {"icon": "🔴", "label": "避開", "class": "avoid"}
    if action == "資料不足":
        return {"icon": "⚪", "label": "資料不足", "class": "neutral"}
    return {"icon": "🟡", "label": "等待", "class": "wait"}


def _plain_summary(stock_id, action, decision):
    rr = decision.get("rr_metrics", {}) if isinstance(decision, dict) else {}
    mup = decision.get("mup_scorecard", {}) if isinstance(decision, dict) else {}
    buy = decision.get("buy_recommendation", {}) if isinstance(decision, dict) else {}
    tiers = [t.get("price") for t in buy.get("tiers", []) if isinstance(t, dict) and t.get("price") is not None]
    support = decision.get("support_level")
    parts = [f"{stock_id} {action}。"]
    if support:
        parts.append("接近支撐，")
    parts.append("RR 合格，" if rr.get("rr_pass") else "RR 尚未合格，")
    if mup.get("status_code") in (None, "IGNORE", "WATCHLIST"):
        parts.append("但 MUP 尚未成立。")
    else:
        parts.append("且 MUP 已轉強。")
    if tiers:
        parts.append(f"建議：{_round(tiers[-1])} 附近承接。")
    else:
        parts.append(f"建議：{decision.get('entry_advice') or action}。")
    return "".join(parts)

def _analysis_payload(stock_id, payload, date=None):
    date = date or datetime.today().strftime("%Y-%m-%d")
    decision = payload.get("decision", {}) if isinstance(payload, dict) else {}
    rr = decision.get("rr_metrics", {}) if isinstance(decision, dict) else {}
    buy = decision.get("buy_recommendation", {}) if isinstance(decision, dict) else {}
    mup = decision.get("mup_scorecard", {}) if isinstance(decision, dict) else {}
    score = payload.get("final_score") or decision.get("final_score")
    ai = decision.get("ai_confidence_score")
    action = _action_label(decision.get("entry_advice"))
    reasons_good, reasons_bad = _build_reasons(payload, decision)
    history = _load_history(stock_id)
    trend_history = _load_history(stock_id, reverse=False)
    price = _round(payload.get("close_price") or decision.get("current_price"))
    prev_close = next((h.get("close") for h in history[1:] if h.get("close") is not None), None)
    price_change = _round(price - prev_close) if isinstance(price, (int, float)) and isinstance(prev_close, (int, float)) else None
    price_change_pct = _round(price_change / prev_close * 100) if isinstance(price_change, (int, float)) and prev_close else None
    support = decision.get("support_level")
    resistance_zone = decision.get("resistance_zone") if isinstance(decision.get("resistance_zone"), list) else []
    resistance = resistance_zone[-1] if resistance_zone else decision.get("take_profit")
    return {
        "stock_id": stock_id,
        "stock_name": STOCK_NAMES.get(stock_id, ""),
        "date": date,
        "generated_at": payload.get("generated_at"),
        "data_source": payload.get("data_source") or "TWSE",
        "price": price,
        "price_change": price_change,
        "price_change_pct": price_change_pct,
        "action": action,
        "action_icon": _action_icon(action),
        "traffic_light": _traffic_light(action),
        "plain_summary": _plain_summary(stock_id, action, decision),
        "stars": _stars(score),
        "score": _round(score),
        "score_grade": payload.get("score_grade") or decision.get("score_grade"),
        "technical_score": (decision.get("scorecard") or {}).get("trend_score"),
        "chip_score": payload.get("chip_score") or decision.get("chip_score"),
        "ai_score": ai,
        "ai_tone": _tone(ai),
        "score_label": _score_label(ai),
        "ai_bar_width": max(0, min(100, ai)) if isinstance(ai, (int, float)) else 0,
        "rr": rr.get("rr"),
        "rr_status": _rr_label(rr.get("rr")),
        "rr_pass": rr.get("rr_pass"),
        "support_level": support,
        "support_distance_pct": _support_distance(price, support),
        "resistance": _round(resistance),
        "mup_status": mup.get("status_code"),
        "mup_text": mup.get("status"),
        "buy_prices": [t.get("price") for t in buy.get("tiers", []) if isinstance(t, dict)],
        "stop_loss": decision.get("stop_loss"),
        "take_profit": [decision.get("take_profit"), *resistance_zone],
        "reasons_good": reasons_good,
        "reasons_bad": reasons_bad,
        "result": decision,
        "history": history,
        "trend_history": trend_history,
        "price_chart": _load_price_chart(stock_id),
    }


def _analysis_from_log(stock_id):
    latest = _latest_log_entry(stock_id)
    if latest is None:
        raise HTTPException(status_code=404, detail="尚未有歷史分析紀錄。")
    date, payload = latest
    return _analysis_payload(stock_id, payload, date=date)


def _analysis_from_result(stock_id, analysis):
    df = analysis.get("df")
    decision = analysis.get("decision") or {}
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail="最新分析沒有可顯示的價格資料。")

    latest_data_date = pd.to_datetime(df["Date"], errors="coerce").max() if "Date" in df.columns else pd.NaT
    date = latest_data_date.strftime("%Y-%m-%d") if not pd.isna(latest_data_date) else datetime.today().strftime("%Y-%m-%d")
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "data_source": "TWSE",
        "close_price": float(df["Close"].iloc[-1]) if "Close" in df.columns else None,
        "chip_score": decision.get("chip_score") if isinstance(decision, dict) else None,
        "chip_signals": decision.get("chip_signals") if isinstance(decision, dict) else None,
        "scorecard": decision.get("scorecard") if isinstance(decision, dict) else None,
        "final_score": decision.get("final_score") if isinstance(decision, dict) else None,
        "score_grade": decision.get("score_grade") if isinstance(decision, dict) else None,
        "score_strength": decision.get("score_strength") if isinstance(decision, dict) else None,
        "decision": decision,
    }
    return _analysis_payload(stock_id, payload, date=date)


def _ensure_current_analysis(stock_id):
    if _is_log_stale(stock_id):
        return _analysis_from_result(stock_id, _run_current_analysis(stock_id))
    return _latest_analysis(stock_id)


def _build_card(stock_id):
    analysis = _ensure_current_analysis(stock_id)
    summary_reasons = analysis["reasons_good"][:2] + analysis["reasons_bad"][:1]
    return {
        **analysis,
        "summary_reasons": summary_reasons,
    }


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    watchlist = _watchlist_stocks()
    cards = [_build_card(stock_id) for stock_id in watchlist]
    available = _available_stocks()
    return templates.TemplateResponse(
        request,
        "home.html",
        {"cards": cards, "available_stocks": available, "watchlist": watchlist},
    )


async def _form_stock_id(request):
    body = (await request.body()).decode("utf-8")
    return _normalize_stock_id((parse_qs(body).get("stock_id") or [""])[0])


@app.post("/watchlist/add")
async def add_to_watchlist(request: Request):
    stock_id = await _form_stock_id(request)
    if not stock_id:
        return RedirectResponse("/", status_code=303)
    _ensure_current_analysis(stock_id)
    watchlist = _load_watchlist()
    if stock_id not in watchlist:
        watchlist.append(stock_id)
        _save_watchlist(watchlist)
    return RedirectResponse(f"/stocks/{stock_id}", status_code=303)


@app.post("/watchlist/remove")
async def remove_from_watchlist(request: Request):
    stock_id = await _form_stock_id(request)
    watchlist = [item for item in _load_watchlist() if item != stock_id]
    _save_watchlist(watchlist)
    return RedirectResponse("/", status_code=303)


@app.get("/stocks/{stock_id}", response_class=HTMLResponse)
def stock_detail(request: Request, stock_id: str):
    stock_id = _normalize_stock_id(stock_id)
    analysis = _ensure_current_analysis(stock_id)
    return templates.TemplateResponse(request, "stock.html", {"a": analysis})
