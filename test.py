from data.fetch_fundamental import fetch_fundamental
payload = fetch_fundamental("5347")
print(payload["income_statement"][-5:])  # 看最近幾期 EPS / 現金流
print(payload["cashflow_statement"][-5:])