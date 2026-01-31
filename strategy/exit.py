def stop_loss(support):
    return round(support * 0.95, 2)

def take_profit(entry, ratio=1.2):
    return round(entry * ratio, 2)
