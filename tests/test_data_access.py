import unittest
from unittest.mock import patch

import pandas as pd

from data.data_manager import get_price
from web_app import _load_price_chart


class DataAccessTests(unittest.TestCase):
    def test_get_price_delegates_cache_freshness_to_price_fetcher(self):
        expected = pd.DataFrame({"Date": ["2026-09-01"], "Close": [68.3]})

        with patch("data.data_manager.fetch_price", return_value=expected) as fetch_price:
            result = get_price("1504", lookback_months=12)

        self.assertIs(result, expected)
        fetch_price.assert_called_once_with(stock_id="1504", lookback_months=12, force_refresh=False)

    def test_price_chart_uses_data_manager_instead_of_reading_price_csv(self):
        price_df = pd.DataFrame(
            {
                "Date": ["2026-08-31", "2026-09-01"],
                "Open": [67.0, 68.0],
                "High": [68.0, 69.0],
                "Low": [66.0, 67.0],
                "Close": [67.5, 68.3],
                "Volume": [1000, 1200],
            }
        )

        with patch("data.data_manager.get_price", return_value=price_df) as get_current_price:
            chart = _load_price_chart("1504")

        get_current_price.assert_called_once_with("1504")
        self.assertTrue(chart["available"])
        self.assertEqual(chart["rows"][-1]["close"], 68.3)


if __name__ == "__main__":
    unittest.main()
