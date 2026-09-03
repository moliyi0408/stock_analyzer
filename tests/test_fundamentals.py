import unittest
from unittest.mock import Mock, patch

import pandas as pd
import requests

from data.fetch_fundamental import _request_finmind
from data.fundamentals import load_income_statement_trend, prepare_fundamental_snapshot
from indicators.fundamental_indicators import calc_fundamental_indicators


class FundamentalDataTests(unittest.TestCase):
    def test_api_message_is_preserved_when_response_has_no_records(self):
        response = Mock(status_code=200)
        response.json.return_value = {"status": 0, "msg": "no financial statements", "data": []}

        with patch("data.fetch_fundamental.requests.get", return_value=response):
            frame, diagnostic = _request_finmind("TaiwanStockFinancialStatements", "1504")

        self.assertTrue(frame.empty)
        self.assertEqual(diagnostic["status"], "no_data")
        self.assertEqual(diagnostic["message"], "no financial statements")
        self.assertEqual(diagnostic["record_count"], 0)

    def test_request_error_is_reported_instead_of_becoming_an_unexplained_empty_frame(self):
        with patch("data.fetch_fundamental.requests.get", side_effect=requests.ConnectionError("blocked")):
            frame, diagnostic = _request_finmind("TaiwanStockFinancialStatements", "1504")

        self.assertTrue(frame.empty)
        self.assertEqual(diagnostic["status"], "error")
        self.assertIn("blocked", diagnostic["message"])

    def test_payload_is_reused_for_income_trend_without_a_second_fetch(self):
        payload = {
            "income_statement": [
                {"date": "2026-03-31", "type": "營業收入合計", "value": 100},
                {"date": "2026-03-31", "type": "營業毛利（毛損）淨額", "value": 40},
            ]
        }
        with patch("data.fundamentals.fetch_fundamentals") as fetch_fundamentals:
            trend = load_income_statement_trend("1504", payload=payload)

        fetch_fundamentals.assert_not_called()
        self.assertEqual(trend.loc[0, "營業收入合計"], 100)

    def test_indicator_and_snapshot_share_normalized_metric_aliases(self):
        payload = {
            "source": "test",
            "fetch_status": "success",
            "income_statement": [
                {"date": "2026-03-31", "type": "營業收入合計", "value": 100},
                {"date": "2026-03-31", "type": "營業毛利(毛損)淨額", "value": 40},
                {"date": "2026-03-31", "type": "營業利益(損失)", "value": 20},
                {"date": "2026-03-31", "type": "基本每股盈餘(元)", "value": 2},
            ],
            "balance_sheet": [],
            "cashflow_statement": [],
        }
        trend = load_income_statement_trend("1504", payload=payload)
        indicators = calc_fundamental_indicators(trend)
        snapshot = prepare_fundamental_snapshot("1504", payload=payload)

        self.assertEqual(indicators.loc[0, "GrossMargin"], 0.4)
        self.assertEqual(indicators.loc[0, "OperatingMargin"], 0.2)
        self.assertEqual(indicators.loc[0, "EPS"], 2.0)
        self.assertEqual(snapshot["gross_margin"], 40.0)


if __name__ == "__main__":
    unittest.main()
