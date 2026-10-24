# Inference helpers use event dates as clusters.
"""Small-sample inference helpers used by main_analysis.py (numpy/scipy only)."""

import numpy as np
from scipy import stats


# IID intervals are diagnostic; the article emphasizes date-clustered and date-equal estimates.
def iid_ci(y, level=0.95):
    y = np.asarray(y, float)
    n = len(y)
    if n < 2:
        return (float(y.mean()) if n else None, None, None, None)
    m, se = y.mean(), y.std(ddof=1) / np.sqrt(n)
    t = stats.t.ppf(0.5 + level / 2, n - 1)
    return float(m), float(se), float(m - t * se), float(m + t * se)


# CR1 variance for an intercept model, using G-1 reference degrees of freedom.
def cluster_mean_ci(y, g, level=0.95):
    """Mean with CR1 cluster-robust SE; t with G-1 df."""
    y = np.asarray(y, float)
    g = np.asarray(g)
    n = len(y)
    groups = np.unique(g)
    G = len(groups)
    if n < 2 or G < 2:
        return (float(y.mean()) if n else None, None, None, None, G)
    m = y.mean()
    e = y - m
    s = np.array([e[g == k].sum() for k in groups])
    v = (G / (G - 1)) * (s**2).sum() / n**2
    se = np.sqrt(v)
    t = stats.t.ppf(0.5 + level / 2, G - 1)
    return float(m), float(se), float(m - t * se), float(m + t * se), G


# Equal-weight date means define a different estimand from equal-weight events.
def date_portfolio_ci(y, g, level=0.95):
    """Average within each event date first, then a t interval across date means."""
    y = np.asarray(y, float)
    g = np.asarray(g)
    means = np.array([y[g == k].mean() for k in np.unique(g)])
    G = len(means)
    if G < 2:
        return (float(means.mean()) if G else None, None, None, None, G)
    m, se = means.mean(), means.std(ddof=1) / np.sqrt(G)
    t = stats.t.ppf(0.5 + level / 2, G - 1)
    return float(m), float(se), float(m - t * se), float(m + t * se), G


# Estimate the group difference in an intercept-plus-indicator regression with pooled date clusters.
def cluster_diff_ci(y1, g1, y0, g0, level=0.95):
    """Difference in means (group1 - group0) from y = a + b*D with CR1 SE clustered on dates
    pooled across both groups; df = G - 1."""
    y = np.concatenate([np.asarray(y1, float), np.asarray(y0, float)])
    d = np.concatenate([np.ones(len(y1)), np.zeros(len(y0))])
    g = np.concatenate([np.asarray(g1), np.asarray(g0)])
    X = np.column_stack([np.ones(len(y)), d])
    XtX_inv = np.linalg.inv(X.T @ X)
    b = XtX_inv @ X.T @ y
    e = y - X @ b
    groups = np.unique(g)
    G = len(groups)
    meat = np.zeros((2, 2))
    for k in groups:
        idx = g == k
        s = X[idx].T @ e[idx]
        meat += np.outer(s, s)
    n, p = X.shape
    c = (G / (G - 1)) * ((n - 1) / (n - p))
    V = c * XtX_inv @ meat @ XtX_inv
    se = float(np.sqrt(V[1, 1]))
    t = stats.t.ppf(0.5 + level / 2, G - 1)
    return float(b[1]), se, float(b[1] - t * se), float(b[1] + t * se), G


# General CR1 OLS for descriptive adjustment; coefficients are not causal estimates.
def cluster_ols(y, X, g, names):
    """OLS with CR1 cluster SE; returns list of dicts. X must include a constant column."""
    y = np.asarray(y, float)
    X = np.asarray(X, float)
    g = np.asarray(g)
    XtX_inv = np.linalg.inv(X.T @ X)
    b = XtX_inv @ X.T @ y
    e = y - X @ b
    groups = np.unique(g)
    G = len(groups)
    meat = np.zeros((X.shape[1], X.shape[1]))
    for k in groups:
        idx = g == k
        s = X[idx].T @ e[idx]
        meat += np.outer(s, s)
    n, p = X.shape
    V = (G / (G - 1)) * ((n - 1) / (n - p)) * XtX_inv @ meat @ XtX_inv
    t = stats.t.ppf(0.975, G - 1)
    return [
        {
            "term": nm,
            "coef": float(b[i]),
            "se": float(np.sqrt(V[i, i])),
            "ci_low": float(b[i] - t * np.sqrt(V[i, i])),
            "ci_high": float(b[i] + t * np.sqrt(V[i, i])),
            "clusters": G,
            "n": n,
        }
        for i, nm in enumerate(names)
    ]


def _weights(G, B, rng):
    """Enumerate all signs for up to 16 clusters; otherwise draw reproducible Rademacher signs."""
    if G <= 16:  # enumerate all Rademacher sign patterns exactly
        grid = np.array(np.meshgrid(*[[-1.0, 1.0]] * G, indexing="ij")).reshape(G, -1).T
        return grid
    return rng.choice([-1.0, 1.0], size=(B, G))


def _invert(pval, est, se, level):
    """Confidence set {theta: p(theta) >= 1-level} found by bisection on each side of the
    point estimate (p is 1 at the estimate and falls towards the tails)."""
    alpha = 1 - level

    def bound(direction):
        """Expand and bisect one endpoint of the inverted confidence set."""
        lo, hi = est, est + direction * se
        k = 0
        while pval(hi) >= alpha and k < 30:  # expand until outside the set
            lo, hi = hi, est + direction * se * 2 ** (k + 1)
            k += 1
        for _ in range(40):  # bisection
            mid = (lo + hi) / 2
            if pval(mid) >= alpha:
                lo = mid
            else:
                hi = mid
        return lo

    return [float(bound(-1)), float(bound(1))]


def _cluster_matrix(g):
    """Return cluster labels and the observation-by-cluster indicator matrix."""
    labels = np.unique(g)
    M = (np.asarray(g)[:, None] == labels[None, :]).astype(float)  # n x G
    return labels, M


# Apply null-imposed Rademacher cluster signs and invert the resulting tests.
def wild_cluster_mean(y, g, level=0.95, B=9999, seed=20260919):
    """Wild cluster bootstrap-t (Rademacher, null imposed) for a mean; all 2^G sign patterns are
    enumerated when G <= 16. Returns the p-value for H0: mean = 0 and the CI from test inversion.
    """
    y = np.asarray(y, float)
    labels, M = _cluster_matrix(g)
    G, n = M.shape[1], len(y)
    W = _weights(G, B, np.random.default_rng(seed))  # draws x G

    def t_stat(Y, theta):  # Y: draws x n
        """Studentize each simulated mean using its CR1 cluster standard error."""
        m = Y.mean(axis=1)
        S = (Y - m[:, None]) @ M  # cluster sums of residuals
        se = np.sqrt((G / (G - 1)) * (S**2).sum(axis=1) / n**2)
        return (m - theta) / se

    t_obs_at = lambda theta: t_stat(y[None, :], theta)[0]

    def pval(theta):
        """Calculate the two-sided null-imposed bootstrap p-value for a candidate parameter."""
        Ystar = theta + (W @ M.T) * (y - theta)[None, :]
        return float(
            np.mean(np.abs(t_stat(Ystar, theta)) >= abs(t_obs_at(theta)) - 1e-12)
        )

    m = y.mean()
    S = (y - m) @ M
    se = np.sqrt((G / (G - 1)) * (S**2).sum() / n**2)
    return {
        "p_value_H0_zero": pval(0.0),
        "ci": _invert(pval, m, se, level),
        "clusters": int(G),
        "draws": int(W.shape[0]),
        "enumerated": G <= 16,
    }


# Use null-imposed wild cluster inference for a two-group mean difference.
def wild_cluster_diff(y1, g1, y0, g0, level=0.95, B=9999, seed=20260919):
    """Wild cluster bootstrap-t for b in y = a + b*D (D=1 for group 1); clusters are event dates
    pooled across both groups; null imposed; Rademacher weights; CI by test inversion.
    For this design the cluster score of b is sum_i (D_i/n1 - (1-D_i)/n0) e_i."""
    y = np.concatenate([np.asarray(y1, float), np.asarray(y0, float)])
    D = np.concatenate([np.ones(len(y1)), np.zeros(len(y0))])
    g = np.concatenate([np.asarray(g1), np.asarray(g0)])
    labels, M = _cluster_matrix(g)
    G, n = M.shape[1], len(y)
    n1, n0 = D.sum(), n - D.sum()
    h = D / n1 - (1 - D) / n0
    c = (G / (G - 1)) * ((n - 1) / (n - 2))
    W = _weights(G, B, np.random.default_rng(seed))
    Wn = W @ M.T  # draws x n

    def b_se(Y):
        """Compute simulated group differences and corresponding CR1 standard errors."""
        m1 = (Y * D).sum(axis=1) / n1
        m0 = (Y * (1 - D)).sum(axis=1) / n0
        b = m1 - m0
        E = Y - (m0[:, None] + b[:, None] * D[None, :])
        U = (E * h[None, :]) @ M
        return b, np.sqrt(c * (U**2).sum(axis=1))

    b_obs, se_obs = (x[0] for x in b_se(y[None, :]))

    def pval(theta):
        """Calculate the two-sided null-imposed bootstrap p-value for a candidate parameter."""
        yr = y - theta * D
        e_r = yr - yr.mean()
        Ystar = (yr.mean() + theta * D)[None, :] + Wn * e_r[None, :]
        bb, ss = b_se(Ystar)
        return float(
            np.mean(np.abs((bb - theta) / ss) >= abs((b_obs - theta) / se_obs) - 1e-12)
        )

    return {
        "diff": float(b_obs),
        "p_value_H0_zero": pval(0.0),
        "ci": _invert(pval, b_obs, se_obs, level),
        "clusters": int(G),
        "draws": int(W.shape[0]),
        "enumerated": G <= 16,
    }


# Approximate detectable magnitude for a two-sided 5% test with 80% power.
def mde(se, clusters, alpha=0.05, power=0.80):
    """Minimum detectable effect for a two-sided test using t with clusters-1 df."""
    if se is None or clusters is None or clusters < 2:
        return None
    df = clusters - 1
    return float((stats.t.ppf(1 - alpha / 2, df) + stats.t.ppf(power, df)) * se)
