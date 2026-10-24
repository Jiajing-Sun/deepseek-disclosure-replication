"""Independently reconstruct matched pools from archived event-level results.
Recheck question-and-answer timing at midnight before the event date;
verify window identities, control reuse and leave-one-date-out diagnostics.
run_all.py verifies newly estimated results against these archives before this audit."""

# Reconstruct independent numerical diagnostics and apply the corrected prior-information cutoff.
# Rebuild same-week and same-day pools directly from event records.
# An answer is prior information only if its display time precedes event-date midnight.
from pathlib import Path
import csv, json, collections, hashlib
import numpy as np
from scipy import stats

R = Path(__file__).resolve().parent
O = R
S = R
read = lambda f: list(csv.DictReader(open(f, encoding="utf-8-sig")))
T = [r for r in read(R / "baseline_event_level_returns.csv") if r["group"] == "T1"]
P = [json.loads(l) for l in open(R / "baseline_event_returns_population.jsonl")]
P = [
    r
    for r in P
    if r["group"] == "P"
    and r.get("direction_resolved") == "up"
    and r.get("status") == "ok"
    and r.get("car_0_2") is not None
]
C = [json.loads(l) for l in open(R / "baseline_event_returns_candidate_firms.jsonl")]
CT = {r["event_key"]: r for r in C}


def summary(y, g):
    """Independently compute event-equal CR1 intervals and equal-weight date intervals in percent."""
    y = np.array(y, float)
    g = np.array(g)
    ds = np.unique(g)
    n = len(y)
    G = len(ds)
    m = y.mean()
    se = np.sqrt(G / (G - 1) * sum((y[g == d] - m).sum() ** 2 for d in ds) / n**2)
    q = stats.t.ppf(0.975, G - 1)
    z = np.array([y[g == d].mean() for d in ds])
    s = z.std(ddof=1) / np.sqrt(G)
    return dict(
        n=n,
        dates=G,
        mean=100 * m,
        ci=[100 * (m - q * se), 100 * (m + q * se)],
        date_mean=100 * z.mean(),
        date_ci=[100 * (z.mean() - q * s), 100 * (z.mean() + q * s)],
    )


hits = [json.loads(l) for l in open(S / "p_pool_qa_hits.jsonl")]
flags = read(S / "p_pool_qa_flags.csv")
cor = {}
changes = []
for f in flags:
    h = [
        h
        for h in hits
        if h["code"] == f["code"]
        and h.get("answer_display_time")
        and h["answer_display_time"] < f["t0"] + " 00:00:00"
        and h["deepseek_in_answer"]
    ]
    cor[f["event_key"]] = bool(h)
    if int(f["ds_prior_answer"]) != bool(h):
        changes.append(
            {
                k: f[k]
                for k in ["event_key", "name", "t0", "evidence_answer_display_times"]
            }
        )
rows = []
pools = {}
use = collections.Counter()
fallback = []
for t in T:
    key = t["code"] + "|" + t["t0"]
    ct = CT[key]
    pw = [
        p for p in P if p["week"] == ct["week"] and p["board_group"] == t["board_group"]
    ]
    pd = [p for p in P if p["t0"] == t["t0"] and p["board_group"] == t["board_group"]]
    if not pd:
        fallback.append(key)
    pd = pd or pw
    assert (
        abs(
            float(t["diff_week_car_0_2"])
            - (float(t["car_0_2"]) - np.mean([p["car_0_2"] for p in pw]))
        )
        < 1e-12
    )
    assert (
        abs(
            float(t["diff_car_0_2"])
            - (float(t["car_0_2"]) - np.mean([p["car_0_2"] for p in pd]))
        )
        < 1e-12
    )
    for p in pw:
        use[p["event_key"]] += 1
    pools[key] = {"week": pw, "day": pd}
    row = {
        "name": t["name"],
        "code": t["code"],
        "t0": t["t0"],
        "week_n": len(pw),
        "day_n": len(pd),
        "car": float(t["car_0_2"]) * 100,
        "week_diff": float(t["diff_week_car_0_2"]) * 100,
        "day_diff": float(t["diff_car_0_2"]) * 100,
    }
    rows.append(row)
res = {
    "core": summary([float(t["car_0_2"]) for t in T], [t["t0"] for t in T]),
    "cutoff_changes": changes,
    "corrected_flag_events": sum(cor.values()),
    "same_day_fallback": fallback,
    "match_rows": rows,
    "pool_reuse_max": max(use.values()),
    "pool_reuse_counts": dict(collections.Counter(use.values())),
}
for typ in ["week", "day"]:
    y = []
    g = []
    for t in T:
        pool = [
            p
            for p in pools[t["code"] + "|" + t["t0"]][typ]
            if not cor.get(p["event_key"], False)
        ]
        if pool:
            y.append(float(t["car_0_2"]) - np.mean([p["car_0_2"] for p in pool]))
            g.append(t["t0"])
    res["corrected_qa_" + typ] = summary(y, g)
res["date_rows"] = []
for d in sorted({t["t0"] for t in T}):
    tt = [t for t in T if t["t0"] == d]
    res["date_rows"].append(
        {
            "date": d,
            "n": len(tt),
            "names": "、".join(t["name"] for t in tt),
            "car": 100 * np.mean([float(t["car_0_2"]) for t in tt]),
            "week_diff": 100 * np.mean([float(t["diff_week_car_0_2"]) for t in tt]),
            "day_diff": 100 * np.mean([float(t["diff_car_0_2"]) for t in tt]),
        }
    )
res["leave_date_out"] = []
for d in sorted({t["t0"] for t in T}):
    tt = [t for t in T if t["t0"] != d]
    res["leave_date_out"].append(
        {
            "excluded": d,
            "n": len(tt),
            **{
                col: summary([float(t[col]) for t in tt], [t["t0"] for t in tt])
                for col in ["car_0_2", "diff_week_car_0_2", "diff_car_0_2"]
            },
        }
    )
# A conservative week-cluster sensitivity also addresses overlapping three-day windows and reused controls.
res["week_cluster"] = {
    col: summary(
        [float(t[col]) for t in T],
        [str(CT[t["code"] + "|" + t["t0"]]["week"]) for t in T],
    )
    for col in ["car_0_2", "diff_week_car_0_2", "diff_car_0_2"]
}
# Verify AR-window identities without invoking original estimator.
errors = []
for r in C:
    if r.get("status") != "ok":
        continue
    ar = r.get("daily_ar", [])
    if len(ar) != 41:
        continue
    for out, a, b in [("car_0_2", 20, 23), ("car_1_2", 21, 23), ("car_3_20", 23, 41)]:
        if r.get(out) is not None and all(v is not None for v in ar[a:b]):
            if abs(sum(ar[a:b]) - r[out]) > 1e-10:
                errors.append([r["event_key"], out])
res["window_sum_errors"] = errors
res["car_distribution"] = {
    "min": min(float(t["car_0_2"]) for t in T) * 100,
    "max": max(float(t["car_0_2"]) for t in T) * 100,
    "median": float(np.median([float(t["car_0_2"]) for t in T])) * 100,
}
(O / "result_revision_audit.json").write_text(
    json.dumps(res, ensure_ascii=False, indent=2)
)
print(
    json.dumps(
        {
            k: v
            for k, v in res.items()
            if k not in ["match_rows", "date_rows", "leave_date_out"]
        },
        ensure_ascii=False,
        indent=2,
    )
)
