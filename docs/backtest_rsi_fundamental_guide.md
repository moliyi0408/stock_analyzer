# 基本面 + RSI 回測與勝率計算指南

## 建議入口：`run_backtest.py`

現在 `run_backtest.py` 已整合兩種策略，不再是「沒用到」：

```bash
python run_backtest.py --strategy default --stock-id 1504 --years 5
python run_backtest.py --strategy rsi_fundamental --stock-id 1504 --years 5
```

> 若你習慣舊命令，也可用：
>
> ```bash
> python run_rsi_fundamental_backtest.py
> ```

## RSI + 基本面 回測邏輯（目前實作）

1. 讀取股價資料（5 年，可調整）。
2. 計算 RSI(14) 與 MA20。
3. 基本面閘門（最新一期）：
   - ROE >= 8
   - 負債比 <= 60
   - 毛利率 >= 20
   - 自由現金流 > 0
4. 只有在基本面通過時才允許進場。
5. 技術面進場條件：
   - RSI 從下往上穿越 30
   - 收盤價在 MA20 之上
6. 出場條件：
   - RSI >= 70，或
   - 觸發停損（預設 8%）

## 勝率與報酬計算

- 勝率：

```text
win_rate = 獲利交易筆數 / 總平倉交易筆數 * 100
```

- 單筆報酬：

```text
pnl_pct = (賣出價 - 買入價) / 買入價
```

- 平均報酬：

```text
avg_return = 所有平倉交易 pnl_pct 平均 * 100
```

## 快取機制（避免重複計算）

回測已加入「先算一次、後續重用」：

- 技術指標快取：`datas/feature_cache/technical/{stock_id}_{years}y_rsi_features.csv`
  - 保存 `Date/Close/RSI/MA20`。
- 基本面閘門快取：`datas/feature_cache/fundamental_gate/{stock_id}_fundamental_gate.json`
  - 保存最新基本面快照 + 閘門通過結果。
  - 預設 30 天有效。

若要強制重抓資料/重算：

```bash
python run_backtest.py --strategy rsi_fundamental --stock-id 1504 --force-refresh
```

## 你可以怎麼調整

- 想更保守：把 `rsi_entry` 降到 25、`stop_loss_pct` 降到 0.05。
- 想更積極：把 `rsi_entry` 提到 35，或把 `rsi_exit` 提到 75。
- 想提高基本面品質：提高 `min_roe`、`min_gross_margin`。

程式入口在 `backtest/rsi_fundamental_backtest.py`，可直接調整參數並重跑比較結果。
