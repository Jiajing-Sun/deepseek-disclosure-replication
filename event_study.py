# Return estimates are fractions; article tables convert them to percent.
"""Estimate event returns from adjacent exchange-day closes.
The market-model estimation window is [-140,-21], with at least 90 pairs.
Returns are fractions internally and are multiplied by 100 for article tables."""

import numpy as np, pandas as pd
from common import *

WINDOWS = {
    "ar_0": (0, 0),
    "car_0_1": (0, 1),
    "car_0_2": (0, 2),
    "car_1_2": (1, 2),
    "car_3_20": (3, 20),
    "car_0_20": (0, 20),
    "precar_m20_m1": (-20, -1),
    "precar_m5_m1": (-5, -1),
    "car_m1_1": (-1, 1),
    "car_0_5": (0, 5),
}
EST = (-140, -21)
MIN_OBS = 90


class Prices:
    """Wide close-price matrix on the index calendar, one frame per adjustment series."""

    def __init__(self, rows, calendar):
        """Align available closing prices to the exchange calendar without forward filling."""
        self.cal = list(calendar)
        self.pos = {d: i for i, d in enumerate(self.cal)}
        df = pd.DataFrame(rows)
        self.close = {}
        self.turnover = {}
        for (adj), g in df.groupby("adjustment_requested"):
            if adj != "raw":
                # a qfq/hfq request that came back as the raw 'day' series is not adjusted data
                g = g[g["series_returned"] == adj + "day"]
            w = g.pivot(index="date", columns="symbol", values="close").reindex(
                self.cal
            )
            self.close[adj] = w
            if "turnover_pct" in g:
                self.turnover[adj] = g.pivot(
                    index="date", columns="symbol", values="turnover_pct"
                ).reindex(self.cal)

    # Require both adjacent exchange-day closes; do not bridge suspended days.
    def returns(self, symbol, series="raw"):
        w = self.close.get(series)
        if w is None or symbol not in w:
            return None
        p = w[symbol].to_numpy(dtype=float)
        r = np.full(len(p), np.nan)
        ok = np.isfinite(p[1:]) & np.isfinite(p[:-1]) & (p[1:] > 0) & (p[:-1] > 0)
        r[1:][ok] = p[1:][ok] / p[:-1][ok] - 1
        return r


# Fit OLS on [-140,-21] with at least 90 pairs; never replace missing windows by zero.
def market_model(stock, market, t0, est=EST, min_obs=MIN_OBS, windows=WINDOWS):
    """OLS market model on the estimation window; abnormal returns elsewhere.

    Returns a dict. CAR for a window is None unless every day in the window has a return
    (a suspended/missing day is reported, not imputed)."""
    n = len(market)
    lo_needed = min(est[0], min(a for a, _ in windows.values()))
    hi_needed = max(b for _, b in windows.values())
    if t0 is None or t0 + lo_needed < 0 or t0 + hi_needed >= n:
        return {"status": "insufficient_calendar"}
    e0, e1 = t0 + est[0], t0 + est[1]
    x, y = market[e0 : e1 + 1], stock[e0 : e1 + 1]
    valid = np.isfinite(x) & np.isfinite(y)
    nv = int(valid.sum())
    if nv < min_obs:
        return {"status": "insufficient_estimation", "n_estimation": nv}
    X = np.column_stack([np.ones(nv), x[valid]])
    coef, *_ = np.linalg.lstsq(X, y[valid], rcond=None)
    alpha, beta = float(coef[0]), float(coef[1])
    resid = y[valid] - X @ coef
    sigma = float(np.sqrt(resid @ resid / (nv - 2)))
    ar = stock - (alpha + beta * market)
    out = {
        "status": "ok",
        "n_estimation": nv,
        "alpha": alpha,
        "beta": beta,
        "sigma_resid": sigma,
        "market_mean_est": float(x[valid].mean()),
        "market_ss_est": float(((x[valid] - x[valid].mean()) ** 2).sum()),
    }
    for k, (a, b) in windows.items():
        v = ar[t0 + a : t0 + b + 1]
        out[k] = float(v.sum()) if np.all(np.isfinite(v)) else None
        out[k + "_missing_days"] = int((~np.isfinite(v)).sum())
    s3 = stock[t0 : t0 + 3]
    out["raw_return_0_2"] = (
        float(np.prod(1 + s3) - 1) if np.all(np.isfinite(s3)) else None
    )
    out["market_adjusted_0_2"] = (
        float(np.sum(stock[t0 : t0 + 3] - market[t0 : t0 + 3]))
        if np.all(np.isfinite(s3))
        else None
    )
    pre = stock[t0 - 20 : t0]
    out["prevolatility"] = (
        float(np.std(pre, ddof=1)) if np.all(np.isfinite(pre)) else None
    )
    out["daily_ar_m20_p20"] = [
        float(v) if np.isfinite(v) else None for v in ar[t0 - 20 : t0 + 21]
    ]
    return out


def market_adjusted(stock, market, t0, a, b):
    """Sum stock-minus-market returns only when the entire window is observed."""
    v = stock[t0 + a : t0 + b + 1] - market[t0 + a : t0 + b + 1]
    return float(v.sum()) if np.all(np.isfinite(v)) else None


def load_candidate_prices():
    """Read the candidate-firm price observations supplied as an external input."""
    return read_jsonl(DATA / "daily_prices.jsonl")


def market_returns(prices, series="raw"):
    """Read the benchmark return series used for market adjustment."""
    return prices.returns("sh000985", "raw")
