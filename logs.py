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
def save_analysis_log(stock_id, df, result, base_dir="logs"):
    """
    儲存單次股票分析紀錄
    logs/{stock_id}_{YYYY-MM-DD_HHMMSS}.json
    """
    if df is None or df.empty or not result:
        return

    today = datetime.now().strftime("%Y-%m-%d")
    Path(base_dir).mkdir(exist_ok=True)
    log_path = Path(base_dir) / f"{stock_id}.json"

    # 讀舊檔
    if log_path.exists():
        with open(log_path, "r", encoding="utf-8") as f:
            try:
                log_data = json.load(f)
            except json.JSONDecodeError:
                log_data = {}
    else:
        log_data = {}

    # 今天已有就不寫
    if today in log_data:
        print(f"ℹ️ {stock_id} {today} 已有紀錄，略過")
        return

    # 使用 _to_json_safe 套用整個 result
    safe_result = _to_json_safe(result)

    log_data[today] = {
        "close_price": float(df['Close'].iloc[-1]) if 'Close' in df.columns else None,
        "chip_score": safe_result.get("chip_score") if isinstance(safe_result, dict) else None,
        "chip_signals": safe_result.get("chip_signals") if isinstance(safe_result, dict) else None,
        "decision": safe_result
    }

    try:
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)
        print(f"✅ {stock_id} 分析紀錄已儲存")
    except Exception as e:
        print(f"⚠ log 儲存失敗: {e}")
