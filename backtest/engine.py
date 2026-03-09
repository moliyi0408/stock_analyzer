# backtest/engine.py 實作方向
class BacktestEngine:
    def __init__(self, df, initial_capital=100000):
        self.df = df
        self.capital = initial_capital
        self.position = 0
        self.logs = []

    def run(self, strategy_logic):
        for i in range(len(self.df)):
            current_data = self.df.iloc[:i+1]
            # 呼叫你原本的 decision_engine.py 判斷邏輯
            signal = strategy_logic(current_data) 
            
            # 執行買賣邏輯並計算損益...
            # 這裡可以整合你的 strategy/position.py 來決定下幾張