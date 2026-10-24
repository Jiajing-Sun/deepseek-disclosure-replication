"""Compute additional matching restrictions and later-period event listings.
Prior theme information requires a company answer displayed before event-date midnight.
Later-period events are listed separately and are not pooled into main inference."""

from pathlib import Path
import csv, json, collections
import numpy as np
from event_study import Prices, market_model
from stats_util import cluster_mean_ci, date_portfolio_ci

B = Path(__file__).resolve().parent
load = lambda name: [
    json.loads(s) for s in (B / name).read_text().splitlines() if s.strip()
]
readcsv = lambda name: list(csv.DictReader(open(B / name, encoding="utf-8-sig")))
# Prefer freshly estimated event returns; the standalone script can use archived results.
T = load(
    "result_event_returns_candidate_firms.jsonl"
    if (B / "result_event_returns_candidate_firms.jsonl").exists()
    else "baseline_event_returns_candidate_firms.jsonl"
)
T = [r for r in T if r["group"] == "T1" and r.get("status") == "ok"]
P = load(
    "result_event_returns_population.jsonl"
    if (B / "result_event_returns_population.jsonl").exists()
    else "baseline_event_returns_population.jsonl"
)
P = [
    r
    for r in P
    if r["group"] == "P"
    and r.get("status") == "ok"
    and r.get("direction_resolved") == "up"
    and r.get("car_0_2") is not None
]
hits = load("p_pool_qa_hits.jsonl")
streak = {r["event_key"]: r for r in readcsv("limit_streaks.csv")}


# Require a keyword in the company answer itself and a display time before event-date midnight.
def mentioned_before(p):
    """Check that a relevant company answer predates event-date midnight."""
    return any(
        h["code"] == p["code"]
        and h.get("answer_display_time")
        and h["answer_display_time"] < p["t0"] + " 00:00:00"
        and h["deepseek_in_answer"]
        for h in hits
    )


flag = {p["event_key"]: mentioned_before(p) for p in P}


def compare(mode, exclude_qa=False, match_limit=False):
    """Subtract each focal event pool mean, then equally weight the resulting differences.
    Do not average the union of reused benchmark observations."""
    y = []
    dates = []
    sizes = []
    for t in T:
        week = [
            p
            for p in P
            if p["week"] == t["week"] and p["board_group"] == t["board_group"]
        ]
        day = [p for p in week if p["t0"] == t["t0"]]
        pool = week if mode == "week" else (day or week)
        if exclude_qa:
            pool = [p for p in pool if not flag[p["event_key"]]]
        if match_limit:
            state = streak[t["event_key"]]["limit_up_m1_rule"]
            pool = [
                p
                for p in pool
                if p["event_key"] in streak
                and streak[p["event_key"]]["limit_up_m1_rule"] == state
            ]
        if not pool:
            continue  # Skip empty pools; never substitute a zero benchmark.
        y.append(t["car_0_2"] - np.mean([p["car_0_2"] for p in pool]))
        dates.append(t["t0"])
        sizes.append(len(pool))
    m, se, l, h, g = cluster_mean_ci(y, dates)
    dm, ds, dl, dh, dg = date_portfolio_ci(y, dates)
    return {
        "n": len(y),
        "dates": g,
        "mean_pp": 100 * m,
        "ci_pp": [100 * l, 100 * h],
        "date_mean_pp": 100 * dm,
        "date_ci_pp": [100 * dl, 100 * dh],
        "pool_sizes": sizes,
    }


out = {
    name: compare(*args, **kw)
    for name, args, kw in [
        ("week", ("week",), {}),
        ("day", ("day",), {}),
        ("week_exclude_prior_qa", ("week",), {"exclude_qa": True}),
        ("day_exclude_prior_qa", ("day",), {"exclude_qa": True}),
        ("week_match_limit", ("week",), {"match_limit": True}),
    ]
}
(B / "result_supplementary.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2)
)
# Apply the same market model to the later period without pooling inference.
# Use the generic-object flag to separate unspecified developers from developer-specific T1 events.
rows = load("extension_daily_prices_raw.jsonl")
cal = sorted({r["date"] for r in rows if r["symbol"] == "sh000985"})
px = Prices(rows, cal)
mr = px.returns("sh000985")
ext = []
for e in readcsv("extension_events.csv"):
    if e["group"] != "T1":
        continue
    generic = e["flag_generic_developer_object"].lower() in ("true", "1", "yes")
    symbol = ("sh" if e["code"].startswith("6") else "sz") + e["code"]
    z = market_model(px.returns(symbol), mr, px.pos[e["t0"]])
    ext.append(
        {
            "name": e["name"],
            "code": e["code"],
            "t0": e["t0"],
            "reported_group": "泛指开发商否认" if generic else "T1",
            "status": z["status"],
            **{
                k: z.get(k)
                for k in [
                    "n_estimation",
                    "ar_0",
                    "car_0_2",
                    "car_3_20",
                    "precar_m20_m1",
                ]
            },
        }
    )
assert sum(e["reported_group"] == "T1" for e in ext) == 1
(B / "result_extension_returns.json").write_text(
    json.dumps(ext, ensure_ascii=False, indent=2)
)
print(
    "Supplementary comparisons complete; later-period listings:",
    len(ext),
    "T1:",
    sum(e["reported_group"] == "T1" for e in ext),
)
