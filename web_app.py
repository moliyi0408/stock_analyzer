from pathlib import Path
import json

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"

app = FastAPI(title="Stock Analyzer Dashboard")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def _round(value, digits=2):
    return round(value, digits) if isinstance(value, (int, float)) else value


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


def _load_history(stock_id):
    rows = []
    for date, payload in sorted(_load_log(stock_id).items(), reverse=True):
        decision = payload.get("decision", {}) if isinstance(payload, dict) else {}
        rr = decision.get("rr_metrics", {}) if isinstance(decision, dict) else {}
        rows.append({
            "date": date,
            "close": payload.get("close_price"),
            "ai": decision.get("ai_confidence_score"),
            "rr": rr.get("rr"),
            "advice": decision.get("entry_advice"),
            "score": payload.get("final_score") or decision.get("final_score"),
        })
    return rows


def _available_stocks():
    ids = {p.stem for p in LOG_DIR.glob("*.json")} if LOG_DIR.exists() else set()
    return sorted(ids)


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


def _analysis_from_log(stock_id):
    latest = _latest_log_entry(stock_id)
    if latest is None:
        raise HTTPException(status_code=404, detail="尚未有排程分析紀錄，請先執行分析流程寫入 logs。")
    date, payload = latest
    decision = payload.get("decision", {}) if isinstance(payload, dict) else {}
    rr = decision.get("rr_metrics", {}) if isinstance(decision, dict) else {}
    buy = decision.get("buy_recommendation", {}) if isinstance(decision, dict) else {}
    mup = decision.get("mup_scorecard", {}) if isinstance(decision, dict) else {}
    score = payload.get("final_score") or decision.get("final_score")
    ai = decision.get("ai_confidence_score")
    action = _action_label(decision.get("entry_advice"))
    reasons_good, reasons_bad = _build_reasons(payload, decision)
    return {
        "stock_id": stock_id,
        "date": date,
        "price": _round(payload.get("close_price") or decision.get("current_price")),
        "action": action,
        "action_icon": _action_icon(action),
        "stars": _stars(score),
        "score": _round(score),
        "score_grade": payload.get("score_grade") or decision.get("score_grade"),
        "technical_score": (decision.get("scorecard") or {}).get("trend_score"),
        "chip_score": payload.get("chip_score") or decision.get("chip_score"),
        "ai_score": ai,
        "ai_tone": _tone(ai),
        "rr": rr.get("rr"),
        "rr_pass": rr.get("rr_pass"),
        "mup_status": mup.get("status_code"),
        "mup_text": mup.get("status"),
        "buy_prices": [t.get("price") for t in buy.get("tiers", []) if isinstance(t, dict)],
        "stop_loss": decision.get("stop_loss"),
        "take_profit": [decision.get("take_profit"), *(((decision.get("resistance_zone") or []) if isinstance(decision.get("resistance_zone"), list) else []))],
        "reasons_good": reasons_good,
        "reasons_bad": reasons_bad,
        "result": decision,
        "history": _load_history(stock_id),
    }


def _build_card(stock_id):
    analysis = _analysis_from_log(stock_id)
    summary_reasons = analysis["reasons_good"][:2] + analysis["reasons_bad"][:1]
    return {
        **analysis,
        "summary_reasons": summary_reasons,
    }


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    cards = [_build_card(stock_id) for stock_id in _available_stocks()]
    return templates.TemplateResponse("home.html", {"request": request, "cards": cards})


@app.get("/stocks/{stock_id}", response_class=HTMLResponse)
def stock_detail(request: Request, stock_id: str):
    analysis = _analysis_from_log(stock_id)
    return templates.TemplateResponse("stock.html", {"request": request, "a": analysis})
