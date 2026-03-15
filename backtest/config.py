from dataclasses import dataclass
import json


@dataclass
class BacktestConfig:
    initial_capital: float = 1_000_000
    risk_pct: float = 0.02
    min_score_entry: float = 70
    max_score_exit: float = 55
    required_trend: str = "多頭趨勢"
    require_rr_pass: bool = True


def load_backtest_config(config_path=None):
    config = BacktestConfig()
    if not config_path:
        return config

    with open(config_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    allowed_fields = set(BacktestConfig.__dataclass_fields__.keys())
    for key, value in raw.items():
        if key in allowed_fields:
            setattr(config, key, value)

    return config
