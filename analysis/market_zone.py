# analysis/market_zone.py
def classify_market_zone(close_price, multi_zones):
    """
    判斷目前股價所在的「多空大本營」區域
    
    參數：
    - close_price: float，最新收盤價
    - multi_zones: dict，多層支撐/壓力，格式為：
        {
            "short_term": {"support": [(low1, high1), ...], "resistance": [...]},
            "swing": {"support": [...], "resistance": [...]},
            "long_term": {"support": [...], "resistance": [...]}
        }
    
    回傳：
    - "多頭大本營"
    - "空頭大本營"
    - "中性區"
    """

    bull_count = 0
    bear_count = 0

    for level, zones in multi_zones.items():
        # 短線、波段、長線的支撐壓力
        supports = zones.get("support", [])
        resistances = zones.get("resistance", [])

        # 判斷收盤價落在哪個層級
        in_support = any(low <= close_price <= high for (low, high) in supports)
        in_resistance = any(low <= close_price <= high for (low, high) in resistances)

        # 計分：如果在支撐區 +1，壓力區 -1
        if in_support:
            bull_count += 1
        elif in_resistance:
            bear_count += 1

    # 🔹 最終判斷
    if bull_count >= 2:
        return "多頭大本營"
    elif bear_count >= 2:
        return "空頭大本營"
    else:
        return "中性區"
