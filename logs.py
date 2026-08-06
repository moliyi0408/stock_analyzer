import json
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd
import math

def _to_json_safe(obj):
    """
    將 numpy / pandas / NaN 型別轉為 JSON 可序列化格式
    """
    if obj is None:
        return None

    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)

    if isinstance(obj, (np.integer, int)):
        return int(obj)

    if isinstance(obj, (np.floating, float)):
        # 將 NaN / inf 轉為 None
        if math.isnan(obj) or math.isinf(obj):
            return None
        return float(obj)

    if isinstance(obj, (np.ndarray, list, tuple, pd.Series, pd.Index)):
        return [_to_json_safe(i) for i in (obj.tolist() if hasattr(obj, "tolist") else obj)]

    if isinstance(obj, dict):
        return {str(k): _to_json_safe(v) for k, v in obj.items()}

    return obj
def save_analysis_log(stock_id, df, result, base_dir=None):
    """
    儲存單次股票分析紀錄
    logs/{stock_id}_{YYYY-MM-DD_HHMMSS}.json
    """
    if df is None or df.empty or not result:
        return

    latest_data_date = pd.to_datetime(df["Date"], errors="coerce").max() if "Date" in df.columns else pd.NaT
    record_date = (
        latest_data_date.strftime("%Y-%m-%d")
        if not pd.isna(latest_data_date)
        else datetime.now().strftime("%Y-%m-%d")
    )
    # 預設固定寫入專案內的 logs 目錄，避免依執行位置變動
    if base_dir is None:
        base_dir = Path(__file__).resolve().parent / "logs"
    else:
        base_dir = Path(base_dir)

    base_dir.mkdir(parents=True, exist_ok=True)
    log_path = base_dir / f"{stock_id}.json"

    # 讀舊檔
    if log_path.exists():
        with open(log_path, "r", encoding="utf-8") as f:
            try:
                log_data = json.load(f)
            except json.JSONDecodeError:
                log_data = {}
    else:
        log_data = {}

    # 同一個交易資料日重新分析時直接覆寫，避免 UI 永遠停在第一次寫入的舊判斷。
    if record_date in log_data:
        print(f"ℹ️ {stock_id} {record_date} 已有紀錄，將以最新分析覆寫")

    # 使用 _to_json_safe 套用整個 result
    safe_result = _to_json_safe(result)

    log_data[record_date] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "data_source": "TWSE",
        "close_price": float(df['Close'].iloc[-1]) if 'Close' in df.columns else None,
        "chip_score": safe_result.get("chip_score") if isinstance(safe_result, dict) else None,
        "chip_signals": safe_result.get("chip_signals") if isinstance(safe_result, dict) else None,
        "scorecard": safe_result.get("scorecard") if isinstance(safe_result, dict) else None,
        "final_score": safe_result.get("final_score") if isinstance(safe_result, dict) else None,
        "score_grade": safe_result.get("score_grade") if isinstance(safe_result, dict) else None,
        "score_strength": safe_result.get("score_strength") if isinstance(safe_result, dict) else None,
        "decision": safe_result
    }

    try:
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)
        print(f"✅ {stock_id} 分析紀錄已儲存")
    except Exception as e:
        print(f"⚠ log 儲存失敗: {e}")
