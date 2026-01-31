def position_hint(trend, heat):
    if trend == "多頭趨勢" and "冷靜" in heat:
        return "可分批布局"
    return "保守操作"
