import json
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd


def _to_json_safe(obj):
    """
    將 numpy / pandas 型別轉為 JSON 可序列化格式
    """
    if isinstance(obj, (np.bool_,)):
        return bool(obj)

    if isinstance(obj, (np.integer,)):
        return int(obj)

    if isinstance(obj, (np.floating,)):
        return float(obj)

    if isinstance(obj, (np.ndarray,)):
        return obj.tolist()

    if isinstance(obj, (pd.Series,)):
        return obj.to_dict()

    if isinstance(obj, dict):
        return {k: _to_json_safe(v) for k, v in obj.items()}

    if isinstance(obj, list):
        return [_to_json_safe(v) for v in obj]

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
            log_data = json.load(f)
    else:
        log_data = {}

    # 今天已有就不寫
    if today in log_data:
        print(f"ℹ️ {stock_id} {today} 已有紀錄，略過")
        return

    log_data[today] = {
        "close_price": float(df['Close'].iloc[-1]) if 'Close' in df.columns else None,
        "decision": _to_json_safe(result)
    }

    try:
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠ log 儲存失敗: {e}")
