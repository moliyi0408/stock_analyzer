from pathlib import Path
import json

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from data.data_manager import get_feature_data, get_fundamental
from data.fundamentals import prepare_fundamental_snapshot, load_income_statement_trend
from analysis.fundamental_analysis import analyze_fundamentals
from decision_engine import decision_engine
from strategy.basic_strategy import fundamental_strategy

BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"

app = FastAPI(title="Stock Analyzer Dashboard")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def _round(value, digits=2):
    return round(value, digits) if isinstance(value, (int, float)) else value


def _load_history(stock_id):
    path = LOG_DIR / f"{stock_id}.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    rows = []
    for date, payload in sorted(data.items(), reverse=True):
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
    ids.update(p.stem.replace("_fundamental", "") for p in (BASE_DIR / "datas" / "fundamental").glob("*_fundamental.json"))
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
        return "等待回檔"
    if any(k in text for k in ["分批", "布局", "承接"]):
        return "分批布局"
    return text[:12]


def build_analysis(stock_id, entry_price=None, holding_mode="auto"):
    fundamental_payload = get_fundamental(stock_id)
    snapshot = prepare_fundamental_snapshot(stock_id, payload=fundamental_payload)
    fundamental_analysis = analyze_fundamentals(load_income_statement_trend(stock_id))
    fundamental_advice = fundamental_strategy(fundamental_analysis, snapshot)
    df = get_feature_data(stock_id, lookback_months=6, include_chip=True)
    if df is None or df.empty:
        raise ValueError("無法取得價量資料")
    result = decision_engine(df=df, chip_strength=5, entry_price=entry_price, holding_mode=holding_mode)
    rr = result.get("rr_metrics", {})
    buy = result.get("buy_recommendation", {})
    mup = result.get("mup_scorecard", {})
    score = result.get("final_score")
    ai = result.get("ai_confidence_score")
    return {
        "stock_id": stock_id,
        "date": str(df["Date"].iloc[-1]) if "Date" in df.columns else "N/A",
        "price": _round(result.get("current_price")),
        "action": _action_label(result.get("entry_advice")),
        "stars": _stars(score),
        "score": _round(score),
        "score_grade": result.get("score_grade"),
        "fundamental_grade": (fundamental_advice or {}).get("rating", "N/A") if isinstance(fundamental_advice, dict) else "N/A",
        "technical_score": (result.get("scorecard") or {}).get("trend_score"),
        "chip_score": result.get("chip_score"),
        "ai_score": ai,
        "ai_tone": _tone(ai),
        "rr": rr.get("rr"),
        "rr_pass": rr.get("rr_pass"),
        "mup_status": mup.get("status_code"),
        "mup_text": mup.get("status"),
        "buy_prices": [t.get("price") for t in buy.get("tiers", []) if isinstance(t, dict)],
        "stop_loss": result.get("stop_loss"),
        "take_profit": [result.get("take_profit"), *(((result.get("resistance_zone") or []) if isinstance(result.get("resistance_zone"), list) else []))],
        "reasons_good": ["接近支撐" if result.get("support_level") else None, f"基本面 {((fundamental_advice or {}).get('rating') if isinstance(fundamental_advice, dict) else 'N/A')}", "RR 合格" if rr.get("rr_pass") else None],
        "reasons_bad": ["MUP 尚未成立" if mup.get("status_code") in (None, "IGNORE", "WATCHLIST") else None, "籌碼沒有增強" if (result.get("chip_score") or 0) < 50 else None],
        "result": result,
        "fundamental_snapshot": snapshot,
        "fundamental_analysis": fundamental_analysis,
        "fundamental_advice": fundamental_advice,
        "history": _load_history(stock_id),
    }


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    cards = []
    for stock_id in _available_stocks():
        history = _load_history(stock_id)
        latest = history[0] if history else {}
        cards.append({"stock_id": stock_id, "score": latest.get("score"), "stars": _stars(latest.get("score")), "advice": _action_label(latest.get("advice")), "price": latest.get("close")})
    return templates.TemplateResponse("home.html", {"request": request, "cards": cards})


@app.get("/stocks/{stock_id}", response_class=HTMLResponse)
def stock_detail(request: Request, stock_id: str, entry_price: float | None = Query(default=None), holding_mode: str = Query(default="auto")):
    analysis = build_analysis(stock_id, entry_price=entry_price, holding_mode=holding_mode)
    return templates.TemplateResponse("stock.html", {"request": request, "a": analysis})
