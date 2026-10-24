"""Small deterministic checks of missing-price and event-window behavior."""

import unittest
import numpy as np
from event_study import Prices, market_model
from stats_util import cluster_mean_ci, date_portfolio_ci


class MethodChecks(unittest.TestCase):
    """Exercise cases where silent imputation or weighting changes would alter inference."""

    def test_suspension_is_not_bridged(self):
        """A missing middle close prevents returns on both adjacent exchange dates."""
        calendar = ["2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07"]
        rows = [
            dict(
                symbol="sz000001",
                date=calendar[i],
                close=p,
                adjustment_requested="raw",
                series_returned="day",
            )
            for i, p in [(0, 100), (2, 121), (3, 133.1)]
        ]
        returns = Prices(rows, calendar).returns("sz000001")
        self.assertTrue(np.isnan(returns[:3]).all())
        self.assertAlmostEqual(returns[3], 0.1)

    def test_known_market_model_and_missing_window(self):
        """Recover a known model and preserve missing CAR instead of filling with zero."""
        market = np.linspace(-0.03, 0.04, 200)
        stock = 0.001 + 1.2 * market
        stock[150:153] += [0.01, 0.02, -0.005]
        result = market_model(stock, market, 150)
        self.assertAlmostEqual(result["alpha"], 0.001)
        self.assertAlmostEqual(result["beta"], 1.2)
        self.assertAlmostEqual(result["car_0_2"], 0.025)
        self.assertAlmostEqual(result["ar_0"] + result["car_1_2"], result["car_0_2"])
        stock[151] = np.nan
        result = market_model(stock, market, 150)
        self.assertIsNone(result["car_0_2"])
        self.assertEqual(result["car_0_2_missing_days"], 1)
        self.assertAlmostEqual(result["ar_0"], 0.01)

    def test_event_and_date_weights_are_distinct(self):
        """Unequal daily event counts must not silently produce identical estimands."""
        values, dates = [0.0, 0.0, 9.0], ["a", "a", "b"]
        self.assertAlmostEqual(cluster_mean_ci(values, dates)[0], 3.0)
        self.assertAlmostEqual(date_portfolio_ci(values, dates)[0], 4.5)


if __name__ == "__main__":
    unittest.main()
