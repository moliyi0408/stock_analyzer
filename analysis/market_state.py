def detect_trend(df):
    if df["MA20"].iloc[-1] > df["MA60"].iloc[-1]:
        return "多頭趨勢"
    elif df["MA20"].iloc[-1] < df["MA60"].iloc[-1]:
        return "空頭趨勢"
    else:
        return "盤整趨勢"
