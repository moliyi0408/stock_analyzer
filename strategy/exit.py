from __future__ import annotations

from typing import Any

import pandas as pd


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    num = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(num):
        return None
    return float(num)


def stop_loss(support):
    support = _to_float(support)
    if support is None:
        return None
    return round(support * 0.95, 2)


def take_profit(entry, ratio=1.2):
    entry = _to_float(entry)
    ratio = _to_float(ratio)
    if entry is None or ratio is None:
        return None
    return round(entry * ratio, 2)


def _build_exit_profile(trend, final_score=None):
    trend = str(trend or "盤整趨勢")
    final_score = _to_float(final_score)

    if "盤整" in trend:
        return {
            "mode": "range",
            "label": "盤整快收型",
            "t1_pct": 0.7,
            "t2_pct": 0.2,
            "atr_multiple": 1.0,
            "primary_trailing": "MA5",
        }

    if "多頭" in trend:
        return {
            "mode": "trend",
            "label": "多頭趨勢型",
            "t1_pct": 0.4,
            "t2_pct": 0.3,
            "atr_multiple": 2.0,
            "primary_trailing": "EMA20" if final_score is not None and final_score >= 75 else "MA5",
        }

    return {
        "mode": "balanced",
        "label": "平衡型",
        "t1_pct": 0.5,
        "t2_pct": 0.3,
        "atr_multiple": 1.5,
        "primary_trailing": "MA5",
    }


def build_exit_plan(
    entry_price,
    stop_loss_price,
    current_price,
    highest_price,
    atr,
    ma5,
    ema20,
    trend=None,
    final_score=None,
    first_take_profit_multiple=1.2,
    second_take_profit_multiple=2.0,
):
    """建立真正三段式 + 市場狀態切換的結構化出場計畫。"""
    entry_price = _to_float(entry_price)
    stop_loss_price = _to_float(stop_loss_price)
    current_price = _to_float(current_price)
    highest_price = _to_float(highest_price)
    atr = _to_float(atr)
    ma5 = _to_float(ma5)
    ema20 = _to_float(ema20)
    final_score = _to_float(final_score)

    if entry_price is None or stop_loss_price is None:
        return {
            "enabled": False,
            "summary": "資料不足，無法建立出場計畫",
            "actions": [],
        }

    risk = round(entry_price - stop_loss_price, 2)
    risk_warning = None
    if risk <= 0:
        fallback_risk = None
        if atr is not None and atr > 0:
            fallback_risk = round(atr, 2)
            risk_warning = "停損高於或等於成本，已改用 ATR 作為風險單位估算出場目標"
        elif entry_price > 0:
            fallback_risk = round(entry_price * 0.02, 2)
            risk_warning = "停損高於或等於成本，已改用成本 2% 作為風險單位估算出場目標"

        if fallback_risk is None or fallback_risk <= 0:
            return {
                "enabled": False,
                "summary": "停損高於或等於成本，且無可用替代風險單位",
                "actions": [],
            }

        risk = fallback_risk

    current_price = current_price if current_price is not None else entry_price
    highest_price = highest_price if highest_price is not None else current_price
    profile = _build_exit_profile(trend, final_score)

    t1_price = round(entry_price + risk * first_take_profit_multiple, 2)
    t2_price = round(entry_price + risk * second_take_profit_multiple, 2)
    break_even_stop = round(entry_price, 2)
    t1_hit = current_price >= t1_price
    t2_hit = current_price >= t2_price

    primary_trailing = profile["primary_trailing"]
    primary_trailing_value = ema20 if primary_trailing == "EMA20" else ma5

    atr_trailing_price = None
    atr_drawdown = None
    atr_trailing_multiple = profile["atr_multiple"]
    if atr is not None and atr > 0 and highest_price is not None:
        atr_trailing_price = round(highest_price - atr_trailing_multiple * atr, 2)
        atr_drawdown = round(highest_price - current_price, 2)

    actions = []
    active_stop = break_even_stop if t1_hit else round(stop_loss_price, 2)

    if not t1_hit:
        actions.append("hold_before_t1")
    else:
        actions.append(f"sell_{int(profile['t1_pct'] * 100)}%")
        actions.append("move_stop_to_break_even")

        if t2_hit:
            actions.append(f"sell_{int(profile['t2_pct'] * 100)}%")
            actions.append("leave_runner_for_trend")

        if primary_trailing_value is not None and current_price < primary_trailing_value:
            actions.append(f"exit_all ({primary_trailing} break)")
        if atr_drawdown is not None and atr is not None and atr_drawdown > atr_trailing_multiple * atr:
            actions.append("exit_all (ATR trailing)")

    if current_price <= active_stop:
        actions.append("exit_all (stop loss)")

    return {
        "enabled": True,
        "summary": risk_warning or "先鎖利潤，再用均線/ATR 追蹤趨勢",
        "mode": profile["mode"],
        "mode_label": profile["label"],
        "risk_per_share": risk,
        "risk_warning": risk_warning,
        "entry_price": round(entry_price, 2),
        "initial_stop_loss": round(stop_loss_price, 2),
        "active_stop_loss": active_stop,
        "t1_price": t1_price,
        "t2_price": t2_price,
        "t1_multiple": first_take_profit_multiple,
        "t2_multiple": second_take_profit_multiple,
        "first_take_profit_pct": profile["t1_pct"],
        "second_take_profit_pct": profile["t2_pct"],
        "runner_pct": round(max(0, 1 - profile["t1_pct"] - profile["t2_pct"]), 2),
        "t1_hit": t1_hit,
        "t2_hit": t2_hit,
        "break_even_stop": break_even_stop,
        "primary_trailing": {
            "mode": primary_trailing,
            "value": round(primary_trailing_value, 2) if primary_trailing_value is not None else None,
            "triggered": bool(primary_trailing_value is not None and current_price < primary_trailing_value) if t1_hit else False,
        },
        "atr_trailing": {
            "multiple": atr_trailing_multiple,
            "atr": round(atr, 2) if atr is not None else None,
            "highest_price": round(highest_price, 2) if highest_price is not None else None,
            "trail_price": atr_trailing_price,
            "drawdown": atr_drawdown,
            "triggered": bool(atr_drawdown is not None and atr is not None and atr_drawdown > atr_trailing_multiple * atr) if t1_hit else False,
        },
        "actions": actions,
        "rules": [
            f"模式：{profile['label']}（依市場狀態自動切換）",
            f"T1 = 成本 + {first_take_profit_multiple}R，先賣出 {int(profile['t1_pct'] * 100)}%",
            f"T2 = 成本 + {second_take_profit_multiple}R，再賣出 {int(profile['t2_pct'] * 100)}%",
            f"T3 = 保留 {int(max(0, 1 - profile['t1_pct'] - profile['t2_pct']) * 100)}% 給趨勢單",
            "第一段停利後，停損上移到成本價（Break Even）",
            f"第二段以 {primary_trailing} 跌破作為主要移動止盈",
            f"若自高點回撤超過 {atr_trailing_multiple} ATR，則全數出場",
        ],
    }


def evaluate_exit_signal(
    current_price,
    entry_price,
    stop_loss_price,
    highest_price,
    atr,
    ma5,
    ema20,
    trend=None,
    final_score=None,
    has_taken_first_profit=False,
    has_taken_second_profit=False,
):
    """回傳回測/即時監控可直接使用的出場事件。"""
    plan = build_exit_plan(
        entry_price=entry_price,
        stop_loss_price=stop_loss_price,
        current_price=current_price,
        highest_price=highest_price,
        atr=atr,
        ma5=ma5,
        ema20=ema20,
        trend=trend,
        final_score=final_score,
    )
    if not plan.get("enabled"):
        return {"actions": [], "plan": plan}

    actions = []
    t1_hit = bool(plan.get("t1_hit"))

    if t1_hit and not has_taken_first_profit:
        actions.append(
            {
                "type": "partial_exit",
                "fraction_of_initial": plan.get("first_take_profit_pct", 0.5),
                "reason": "t1_hit",
            }
        )
        actions.append(
            {
                "type": "update_stop_loss",
                "stop_loss": plan.get("break_even_stop"),
                "reason": "move_stop_to_break_even",
            }
        )

    if plan.get("t2_hit") and not has_taken_second_profit:
        actions.append(
            {
                "type": "partial_exit",
                "fraction_of_initial": plan.get("second_take_profit_pct", 0.3),
                "reason": "t2_hit",
            }
        )

    if "exit_all (stop loss)" in plan.get("actions", []):
        actions.append({"type": "exit_all", "reason": "stop_loss"})

    if t1_hit and plan.get("primary_trailing", {}).get("triggered"):
        trailing_mode = plan.get("primary_trailing", {}).get("mode", "MA5")
        actions.append({"type": "exit_all", "reason": f"{trailing_mode.lower()}_break"})

    if t1_hit and plan.get("atr_trailing", {}).get("triggered"):
        actions.append({"type": "exit_all", "reason": "atr_trailing"})

    return {"actions": actions, "plan": plan}
