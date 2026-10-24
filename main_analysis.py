# Keep event definitions fixed and retain both planned and exploratory branches.
"""Estimate event returns, matched contrasts and date-clustered uncertainty.
Event membership is supplied by the content/history coding inputs.
The complete analysis retains planned comparisons and explicitly labeled explorations.
"""

import json, csv, collections, datetime
import numpy as np
from common import *
from event_study import Prices, market_model, WINDOWS
from stats_util import (
    iid_ci,
    cluster_mean_ci,
    date_portfolio_ci,
    cluster_diff_ci,
    cluster_ols,
    wild_cluster_mean,
    wild_cluster_diff,
    mde,
)

OUTCOMES = [
    "car_0_2",
    "car_3_20",
    "precar_m20_m1",
    "precar_m5_m1",
    "ar_0",
    "car_1_2",
    "car_m1_1",
    "car_0_5",
    "car_0_20",
]
LIMIT = {"SSE_main": 0.10, "SZSE_main": 0.10, "SZSE_ChiNext": 0.20, "SSE_STAR": 0.20}


# Check overlapping closes before adding securities not covered by the candidate-price file.
def load_prices(cal):
    rows = read_jsonl(DATA / "daily_prices.jsonl")
    have = {r["symbol"] for r in rows}
    frame = read_jsonl(OUT_DATA / "frame_daily_prices_raw.jsonl")
    # consistency: the frame fetch repeats the original request for the 70 candidate firms
    orig = {
        (r["symbol"], r["date"]): r["close"]
        for r in rows
        if r["adjustment_requested"] == "raw"
    }
    gaps = [
        abs(orig[(r["symbol"], r["date"])] - r["close"])
        for r in frame
        if (r["symbol"], r["date"]) in orig
    ]
    frame_keys = {(r["symbol"], r["date"]) for r in frame}
    frame_syms = {r["symbol"] for r in frame}
    missing_in_frame = sum(
        1
        for k in orig
        if k[0] != "sh000985" and k[0] in frame_syms and k not in frame_keys
    )
    rows += [r for r in frame if r["symbol"] not in have]
    ext = OUT_DATA / "extended_firms_daily_prices_raw.jsonl"
    if ext.exists():
        have = {r["symbol"] for r in rows}
        rows += [r for r in read_jsonl(ext) if r["symbol"] not in have]
    return Prices(rows, cal), {
        "overlap_rows": len(gaps),
        "max_abs_close_gap": max(gaps) if gaps else None,
        "rows_missing_in_frame_fetch": missing_in_frame,
    }


# Use sample-period closing-limit rules: growth boards 20%, main board 10%, main-board ST 5%.
def limit_rate(board, name):
    # 2024-25 rules: ChiNext and STAR 20% (incl. ST); main boards 10%, ST/*ST 5%
    if board in ("SZSE_ChiNext", "SSE_STAR"):
        return 0.20
    return 0.05 if "ST" in (name or "") else 0.10


# Round limit prices to cents using half-up rounding; this is a closing-limit indicator.
def limit_flags(close, i, board, name):
    """(limit_up, limit_down) for day i from the exact limit price: previous close x (1 +/- rate), rounded half-up
    to 0.01 yuan. Replaces the first-run approximation (|return| >= 95% of the board limit, ST ignored), which the
    results-stage review found misclassifies large non-limit moves and ST limit moves.
    """
    from decimal import Decimal, ROUND_HALF_UP

    if i < 1 or not (np.isfinite(close[i]) and np.isfinite(close[i - 1])):
        return False, False
    rate = limit_rate(board, name)
    prev = Decimal(str(close[i - 1]))
    up = float(
        (prev * (1 + Decimal(str(rate)))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    )
    dn = float(
        (prev * (1 - Decimal(str(rate)))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    )
    return close[i] >= up - 1e-6, close[i] <= dn + 1e-6


# Attach market-model returns, adjustment sensitivity, turnover and limit-state features.
def event_returns(ev, prices, mkt, mkt_tri, cal):
    t0 = cal.index(ev["t0"])
    sym = symbol_of(ev["code"])
    s = prices.returns(sym, "raw")
    out = {k: ev[k] for k in ev}
    if s is None:
        out["status"] = "no_price_data"
        return out
    m = market_model(s, mkt, t0)
    out["status"] = m["status"]
    out["n_estimation"] = m.get("n_estimation")
    for k in OUTCOMES:
        out[k] = m.get(k)
    out["missing_days_0_2"] = m.get("car_0_2_missing_days")
    out["daily_ar"] = m.get("daily_ar_m20_p20")
    out["beta"] = m.get("beta")
    out["sigma_resid"] = m.get("sigma_resid")
    # market-adjusted sensitivity

    def madj(a, b):
        """Compute the market-adjusted return for the requested event-relative window."""
        v = s[t0 + a : t0 + b + 1] - mkt[t0 + a : t0 + b + 1]
        return float(v.sum()) if np.all(np.isfinite(v)) else None

    out["madj_0_2"] = madj(0, 2)
    out["madj_3_20"] = madj(3, 20)
    out["madj_pre_m20_m1"] = madj(-20, -1)
    out["pre3_madj"] = madj(-3, -1)
    # adjusted-price / total-return benchmark sensitivity (only where supplier qfq exists)
    q = prices.returns(sym, "qfq")
    if q is not None and np.isfinite(q[t0 - 140 : t0 + 21]).sum() > 100:
        mq = market_model(q, mkt_tri, t0)
        out["car_0_2_qfq_tri"] = mq.get("car_0_2")
        out["car_3_20_qfq_tri"] = mq.get("car_3_20")
    # abnormal turnover (descriptive comparability): mean turnover in a pre-event window relative to the
    # estimation window [-140,-21]; turnover_pct as supplied by Tencent (volume units are not used)
    tv = prices.turnover.get("raw")
    if tv is not None and sym in tv:
        t = tv[sym].to_numpy(dtype=float)
        base = (
            np.nanmean(t[t0 - 140 : t0 - 20])
            if np.isfinite(t[t0 - 140 : t0 - 20]).sum() >= 90
            else np.nan
        )
        for name, a, b in [
            ("turnover_ratio_m20_m1", -20, -1),
            ("turnover_ratio_m5_m1", -5, -1),
            ("turnover_ratio_0_2", 0, 2),
        ]:
            w = t[t0 + a : t0 + b + 1]
            out[name] = (
                float(np.nanmean(w) / base)
                if np.isfinite(base) and base > 0 and np.isfinite(w).all()
                else None
            )
    # limit moves on t0 and within [0,2] (exact limit prices)
    board = ev["board"]
    r0 = s[t0]
    out["ret_t0"] = float(r0) if np.isfinite(r0) else None
    close = prices.close["raw"][sym].to_numpy(dtype=float)
    lf = lambda i: limit_flags(close, i, board, ev.get("name"))
    out["limit_up_t0"], out["limit_down_t0"] = (bool(x) for x in lf(t0))
    out["limit_days_0_2"] = int(sum(1 for i in range(t0, t0 + 3) if any(lf(i))))
    out["limit_up_days_m3_m1"] = int(sum(1 for i in range(t0 - 3, t0) if lf(i)[0]))
    out["limit_up_m1"] = bool(lf(t0 - 1)[0])
    return out


# Summarize each outcome using its own nonmissing events and event dates.
def summarize(rows, key, label):
    v = [(r[key], r["t0"]) for r in rows if r.get(key) is not None]
    if not v:
        return {"group": label, "outcome": key, "n_events": 0}
    y = np.array([a for a, _ in v])
    g = np.array([b for _, b in v])
    m, se, lo, hi = iid_ci(y)
    cm, cse, clo, chi, G = cluster_mean_ci(y, g)
    pm, pse, plo, phi, _ = date_portfolio_ci(y, g)
    top = collections.Counter(g).most_common(1)[0]
    return {
        "group": label,
        "outcome": key,
        "n_events": len(y),
        "n_firms": len({r["code"] for r in rows if r.get(key) is not None}),
        "n_dates": int(G),
        "max_single_date_share": top[1] / len(y),
        "max_date": top[0],
        "mean": m,
        "median": float(np.median(y)),
        "sd": float(y.std(ddof=1)) if len(y) > 1 else None,
        "share_positive": float((y > 0).mean()),
        "ci_iid": [lo, hi],
        "ci_date_cluster": [clo, chi],
        "se_date_cluster": cse,
        "date_portfolio_mean": pm,
        "ci_date_portfolio": [plo, phi],
        "mde_80pct_date_cluster": mde(cse, G),
    }


# Estimate returns, form fixed groups, construct matched contrasts and report uncertainty.
def main():
    cal = trading_calendar()
    prices, price_check = load_prices(cal)
    mkt = prices.returns("sh000985", "raw")
    tri = {r["date"]: r["close"] for r in read_jsonl(OUT_DATA / "csindex_H00985.jsonl")}
    tri_arr = np.array([tri.get(d, np.nan) for d in cal])
    mkt_tri = np.full(len(cal), np.nan)
    mkt_tri[1:] = tri_arr[1:] / tri_arr[:-1] - 1

    cand = read_jsonl(OUT_DATA / "events_candidate_firms.jsonl")
    pop = read_jsonl(OUT_DATA / "events_population.jsonl")
    res_c = [event_returns(e, prices, mkt, mkt_tri, cal) for e in cand]
    res_p = [event_returns(e, prices, mkt, mkt_tri, cal) for e in pop]
    # trigger direction, one rule for every group (plan amendment 5): text first; if a merged event's
    # documents say up and none says down -> up (and vice versa); otherwise the sign of the
    # market-adjusted return over [-3,-1]
    for r in res_c + res_p:
        parts = set(r["direction"].split("/"))
        if "up" in parts and "down" not in parts and "mixed" not in parts:
            r["direction_resolved"], r["direction_source"] = "up", "text"
        elif "down" in parts and "up" not in parts and "mixed" not in parts:
            r["direction_resolved"], r["direction_source"] = "down", "text"
        else:
            r["direction_resolved"] = (
                None
                if r.get("pre3_madj") is None
                else ("up" if r["pre3_madj"] > 0 else "down")
            )
            r["direction_source"] = "pre[-3,-1] market-adjusted sign"
    write_jsonl(OUT_DATA / "event_returns_candidate_firms.jsonl", res_c)
    write_jsonl(OUT_DATA / "event_returns_population.jsonl", res_p)

    ok = lambda r: r.get("status") == "ok" and r.get("car_0_2") is not None
    main_grade = lambda r: r["timing_grade_worst"] in ("A", "B")
    up = lambda r: r.get("direction_resolved") == "up"
    cg = lambda g, r: r["group"] == g and main_grade(r) and ok(r)
    groups = {
        "T1 主样本(A/B级时间)": [r for r in res_c if cg("T1", r) and up(r)],
        "T1 剔除首次性存疑": [
            r for r in res_c if cg("T1", r) and up(r) and not r.get("novelty_uncertain")
        ],
        "T1p 此前已由其他渠道公开的否认": [r for r in res_c if cg("T1p", r) and up(r)],
        "T2 否认内容更新": [r for r in res_c if cg("T2", r) and up(r)],
        "R 重复否认": [r for r in res_c if cg("R", r) and up(r)],
        "K DeepSeek相关无否认": [r for r in res_c if cg("K", r) and up(r)],
        "K′ 否认之后的DeepSeek相关无否认": [
            r for r in res_c if cg("K_after_denial", r) and up(r)
        ],
        "O 其他AI内容": [r for r in res_c if cg("O", r) and up(r)],
        "N 无AI内容(事前有AI证据)": [r for r in res_c if cg("N", r) and up(r)],
        "P 总体基准(上涨触发)": [r for r in res_p if up(r) and ok(r)],
        # all trigger directions, reported separately (plan amendment 5)
        "T1 全部方向": [r for r in res_c if cg("T1", r)],
        "K 全部方向": [r for r in res_c if cg("K", r)],
        "N 全部方向": [r for r in res_c if cg("N", r)],
        "P 总体基准(全部方向)": [r for r in res_p if ok(r)],
    }
    t1_not_up = [
        f"{r['name']} {r['t0']} ({r['direction']}→{r.get('direction_resolved')})"
        for r in res_c
        if r["group"] == "T1" and not up(r)
    ]
    # plan section 6: every non-computable event is listed with its reason (candidate firms and population P)
    not_computable = [
        {
            "code": r["code"],
            "name": r["name"],
            "t0": r["t0"],
            "group": r["group"],
            "status": r.get("status"),
            "n_estimation": r.get("n_estimation"),
            "missing_days_0_2": r.get("missing_days_0_2"),
        }
        for r in res_c + res_p
        if not ok(r)
    ]
    P_attrition = {
        "P_events_A_grade": len(res_p),
        "direction_resolved": dict(
            collections.Counter(r.get("direction_resolved") for r in res_p)
        ),
        "up_trigger": sum(1 for r in res_p if up(r)),
        "up_trigger_computable": sum(1 for r in res_p if up(r) and ok(r)),
        "up_trigger_not_computable_by_status": dict(
            collections.Counter(r.get("status") for r in res_p if up(r) and not ok(r))
        ),
    }
    summary = [
        summarize(rows, k, lab)
        for lab, rows in groups.items()
        for k in OUTCOMES + ["madj_0_2", "madj_3_20", "car_0_2_qfq_tri"]
    ]

    # matched population benchmark: same t0 & board group, else same ISO week & board group (up-trigger P only)
    P = groups["P 总体基准(上涨触发)"]
    idx_day = collections.defaultdict(list)
    idx_week = collections.defaultdict(list)
    for p in P:
        idx_day[(p["t0"], p["board_group"])].append(p)
        idx_week[(p["week"], p["board_group"])].append(p)
    # The internally frozen plan specifies matching within the same ISO week and board group. The code
    # first written (before any result was seen) matched on the same day first and fell back to the same week;
    # that departure from the plan text was found in the results-stage review. Both are reported:
    # 'matched_benchmark_same_week' is the internally prespecified comparison, 'matched_benchmark' the same-day-first variant.

    def _match(rule):
        """Subtract each event-specific benchmark mean before summarizing event-level differences."""
        out_m = {}
        for lab in [
            "T1 主样本(A/B级时间)",
            "K DeepSeek相关无否认",
            "R 重复否认",
            "N 无AI内容(事前有AI证据)",
        ]:
            rows = []
            for r in groups[lab]:
                if rule == "same_week":
                    pool, how = (
                        idx_week.get((r["week"], r["board_group"])),
                        "same_week_board",
                    )
                else:
                    pool, how = (
                        idx_day.get((r["t0"], r["board_group"])),
                        "same_day_board",
                    )
                    if not pool:
                        pool, how = (
                            idx_week.get((r["week"], r["board_group"])),
                            "same_week_board",
                        )
                if not pool:
                    continue
                rec = {
                    "event_key": r["event_key"],
                    "code": r["code"],
                    "t0": r["t0"],
                    "match": how,
                    "pool_n": len(pool),
                }
                for k in ["car_0_2", "car_3_20", "precar_m20_m1"]:
                    vals = [p[k] for p in pool if p.get(k) is not None]
                    if vals and r.get(k) is not None:
                        rec[k + "_diff"] = r[k] - float(np.mean(vals))
                        rec[k + "_bench"] = float(np.mean(vals))
                rows.append(rec)
            wb = {}
            for k in ["car_0_2", "car_3_20", "precar_m20_m1"]:
                v = [
                    (x[k + "_diff"], x["t0"])
                    for x in rows
                    if x.get(k + "_diff") is not None
                ]
                G = len({t for _, t in v})
                wb[k] = (
                    wild_cluster_mean([a for a, _ in v], [t for _, t in v])
                    if G >= 10
                    else {"not_reported": f"{G} date clusters (<10)"}
                )
            pools = {}
            for r in groups[lab]:
                key = (
                    (r["week"], r["board_group"])
                    if rule == "same_week"
                    else (r["t0"], r["board_group"])
                )
                pools[key] = (idx_week if rule == "same_week" else idx_day).get(key, [])
            union = [p for v in pools.values() for p in v]
            pn = [x["pool_n"] for x in rows]
            out_m[lab] = {
                "rule": rule,
                "n_matched": len(rows),
                "matches_by_rule": dict(collections.Counter(x["match"] for x in rows)),
                "summaries": [
                    summarize(rows, k + "_diff", lab + " 减 匹配P均值")
                    for k in ["car_0_2", "car_3_20", "precar_m20_m1"]
                ],
                "wild_bootstrap": wb,
                "benchmark_mean_event_weighted": {
                    k: float(
                        np.mean(
                            [
                                x[k + "_bench"]
                                for x in rows
                                if x.get(k + "_bench") is not None
                            ]
                        )
                    )
                    for k in ["car_0_2", "car_3_20", "precar_m20_m1"]
                    if rows
                },
                "pool_events_unweighted": {
                    "n": len(union),
                    "car_0_2_mean": (
                        float(np.mean([p["car_0_2"] for p in union])) if union else None
                    ),
                },
                "pool_size": {
                    "min": min(pn) if pn else None,
                    "median": float(np.median(pn)) if pn else None,
                    "events_with_pool_le_2": sum(1 for x in pn if x <= 2),
                },
            }
            write_jsonl(RESULTS / f"matched_{rule}_{lab.split()[0]}.jsonl", rows)
        return out_m

    matched = _match("same_day_first")
    matched_week = _match("same_week")

    # pre-specified group differences (date-clustered)
    diffs = []
    for a, b in [
        ("T1 主样本(A/B级时间)", "K DeepSeek相关无否认"),
        ("T1 主样本(A/B级时间)", "P 总体基准(上涨触发)"),
        ("T1 主样本(A/B级时间)", "N 无AI内容(事前有AI证据)"),
        ("T1 主样本(A/B级时间)", "T1p 此前已由其他渠道公开的否认"),
    ]:
        for k in ["car_0_2", "car_3_20", "precar_m20_m1"]:
            A = [(r[k], r["t0"]) for r in groups[a] if r.get(k) is not None]
            B_ = [(r[k], r["t0"]) for r in groups[b] if r.get(k) is not None]
            if len(A) > 1 and len(B_) > 1:
                d, se, lo, hi, G = cluster_diff_ci(
                    [x for x, _ in A],
                    [g for _, g in A],
                    [x for x, _ in B_],
                    [g for _, g in B_],
                )
                # plan section 4: with fewer than 10 date clusters no significance is interpreted; the Rademacher
                # wild bootstrap also degenerates there (2^G sign patterns), so it is not reported
                wb = (
                    wild_cluster_diff(
                        [x for x, _ in A],
                        [g for _, g in A],
                        [x for x, _ in B_],
                        [g for _, g in B_],
                    )
                    if G >= 10
                    else {"not_reported": f"{G} date clusters (<10)"}
                )
                diffs.append(
                    {
                        "contrast": f"{a} − {b}",
                        "outcome": k,
                        "n_a": len(A),
                        "n_b": len(B_),
                        "diff": d,
                        "se": se,
                        "ci_date_cluster": [lo, hi],
                        "clusters": G,
                        "mde_80pct": mde(se, G),
                        "wild_bootstrap": wb,
                    }
                )
    # one exploratory regression (plan section 4)
    reg_rows = [
        r
        for lab in [
            "T1 主样本(A/B级时间)",
            "K DeepSeek相关无否认",
            "P 总体基准(上涨触发)",
        ]
        for r in groups[lab]
        if r.get("precar_m20_m1") is not None
    ]
    y = [r["car_0_2"] for r in reg_rows]
    X = [
        [1, r["group"] == "T1", r["group"] == "K", r["precar_m20_m1"]] for r in reg_rows
    ]
    reg = cluster_ols(
        y, X, [r["t0"] for r in reg_rows], ["const", "T1", "K", "PreCAR[-20,-1]"]
    )

    # amendment 1: wild cluster bootstrap for the T1 mean
    wild = {}
    for lab in [
        "T1 主样本(A/B级时间)",
        "T1p 此前已由其他渠道公开的否认",
        "K DeepSeek相关无否认",
        "R 重复否认",
    ]:
        for k in ["car_0_2", "car_3_20", "precar_m20_m1"]:
            v = [(r[k], r["t0"]) for r in groups[lab] if r.get(k) is not None]
            G = len({t for _, t in v})
            if len(v) > 2 and G >= 10:
                wild[f"{lab}|{k}"] = wild_cluster_mean(
                    [x for x, _ in v], [t for _, t in v]
                )
            elif v:
                wild[f"{lab}|{k}"] = {"not_reported": f"{G} date clusters (<10)"}

    # plan section 5: descriptive heterogeneity within T1 (cells < 5 events are listed, not averaged)
    coding = {
        r["announcement_id"]: r for r in read_jsonl(OUT_DATA / "coding_documents.jsonl")
    }
    # Planned cells distinguish broad from specific commercial denials and full from specific equity denials.
    # The first run merged unstated dimensions with narrower denials; retain that version as an audit output.
    # The corrected tables separate unstated dimensions from both denial categories
    # as a separate cell because the plan's two-way split does not cover them.
    BORDERLINE_APRE = {
        "688343": "云天励飞：唯一证据为“完成适配…可以交付客户使用”",
        "300846": "首都在线：云服务商，证据为“基于开源的Deepseek…推出多种AI相关业务和解决方案”",
    }

    def t1_attr(r):
        """Map content labels to prespecified breadth, adoption and board characteristics."""
        cs = [coding[a] for a in r["announcement_ids"].split(";") if a in coding]
        biz = next((c["biz"] for c in cs if c["biz"] not in ("未说明",)), "未说明")
        eq = next((c["eq"] for c in cs if c["eq"] not in ("未说明",)), "未说明")
        apre = r.get("apre_before_t0") is True
        return {
            "biz": (
                "broad"
                if biz in ("否认任何业务往来", "否认业务合作")
                else ("specific" if biz == "仅否认特定形式" else "unstated")
            ),
            "eq": (
                "full"
                if eq == "否认直接和间接股权"
                else ("specific" if eq == "仅否认特定形式" else "unstated")
            ),
            "biz_broad": biz in ("否认任何业务往来", "否认业务合作"),
            "eq_full": eq == "否认直接和间接股权",
            "apre": apre,
            "apre_strict": apre and r["code"] not in BORDERLINE_APRE,
            "growth_board": r["board_group"] != "main",
        }

    def cells(rows, spec):
        """Summarize cells with at least five events and list smaller cells individually."""
        outc = []
        for attr, pairs in spec:
            for val, lab in pairs:
                cell = [r for r in rows if t1_attr(r)[attr] == val]
                if len(cell) >= 5:
                    outc.append(
                        {"split": attr, "cell": lab, **summarize(cell, "car_0_2", lab)}
                    )
                else:
                    outc.append(
                        {
                            "split": attr,
                            "cell": lab,
                            "n_events": len(cell),
                            "listed_only": True,
                            "events": [
                                f"{r['name']} {r['t0']} CAR[0,2]={r['car_0_2'] * 100:.1f}%"
                                for r in cell
                            ],
                        }
                    )
        return outc

    t1rows = groups["T1 主样本(A/B级时间)"]
    hetero = cells(
        t1rows,
        [
            (
                "biz",
                [
                    ("broad", "商业关系：否认任何往来或否认合作"),
                    ("specific", "商业关系：仅否认特定形式"),
                    ("unstated", "商业关系：未说明（方案两分之外）"),
                ],
            ),
            (
                "eq",
                [
                    ("full", "股权：否认直接和间接"),
                    ("specific", "股权：仅否认特定形式"),
                    ("unstated", "股权：未说明（方案两分之外）"),
                ],
            ),
            (
                "apre",
                [(True, "事前已有公开采用证据"), (False, "未查到事前公开采用证据")],
            ),
            ("growth_board", [(True, "创业板/科创板"), (False, "主板")]),
        ],
    )
    hetero_first_run = cells(
        t1rows,
        [
            (
                "biz_broad",
                [
                    (True, "商业关系：否认任何往来或否认合作"),
                    (False, "商业关系：仅特定形式或未说明"),
                ],
            ),
            (
                "eq_full",
                [(True, "股权：否认直接和间接"), (False, "股权：特定形式或未说明")],
            ),
        ],
    )
    # POST-HOC sensitivity (results-stage review): two borderline Apre codings treated as 'no Apre'
    hetero_apre_strict = {
        "borderline_firms": BORDERLINE_APRE,
        "cells": cells(
            t1rows,
            [
                (
                    "apre_strict",
                    [
                        (True, "事前已有公开采用证据（剔除2个边界编码）"),
                        (False, "未查到或边界"),
                    ],
                )
            ],
        ),
    }
    # plan section 6: T1 excluding events with substantive same-firm news in [-1,+2]
    clean = [r for r in t1rows if not r.get("other_news_substantive")]
    clean_all = [r for r in t1rows if not r.get("other_news_any_flagged")]
    other_news_sub = {
        "n_excluded_substantive": len(t1rows) - len(clean),
        "excluded_substantive": [
            f"{r['name']} {r['t0']}: {r.get('other_news_substantive_titles')}"
            for r in t1rows
            if r.get("other_news_substantive")
        ],
        "n_excluded_any_flagged": len(t1rows) - len(clean_all),
        "excluded_any_flagged": [
            f"{r['name']} {r['t0']}: {r.get('other_news_titles')}"
            for r in t1rows
            if r.get("other_news_any_flagged")
        ],
        "summary": [
            summarize(clean, k, "T1 剔除同期其他实质消息")
            for k in ["car_0_2", "car_3_20"]
        ]
        + [
            summarize(
                clean_all,
                k,
                "T1 剔除窗口内任何被标记的公告(含同内容风险提示与重叠异动公告)",
            )
            for k in ["car_0_2", "car_3_20"]
        ],
    }
    # amendment 3: P without firms whose Tencent prices disagree with Sohu
    bad = set()
    pdiff = OUT_DATA / "frame_sohu_differences.jsonl"
    if pdiff.exists():
        bad = {r["symbol"][2:] for r in read_jsonl(pdiff)}
    P_clean = [r for r in P if r["code"] not in bad]
    # Exclude company-dates containing adjacent AI topics such as computing infrastructure or humanoid robots.
    adj_ids = set(
        json.loads((OUT_DATA / "population_ai_adjacent_docs.json").read_text())[
            "announcement_ids"
        ]
    )
    P_noadj = [r for r in P if not (set(r["announcement_ids"].split(";")) & adj_ids)]
    p_robust = {
        "firms_with_price_disagreement": sorted(bad),
        "summary": [
            summarize(P_clean, k, "P(上涨) 剔除价格不一致公司")
            for k in ["car_0_2", "car_3_20"]
        ]
        + [
            summarize(P_noadj, k, "P(上涨) 剔除AI相邻主题公告")
            for k in ["car_0_2", "car_3_20"]
        ],
        "n_P_events_with_ai_adjacent_docs": len(P) - len(P_noadj),
    }

    # plan item 8: extended sample (first denials in clarification / risk-warning notices), listing only
    extended = []
    ep = OUT_DATA / "extended_first_denials.jsonl"
    rv = OUT_DATA / "prior_record_review.json"
    ext_nov = (
        {
            x["code"]: x
            for x in json.loads(rv.read_text()).get("extended_sample_novelty", [])
        }
        if rv.exists()
        else {}
    )
    if ep.exists():
        for x in read_jsonl(ep):
            nv = ext_nov.get(x["code"], {})
            row = {
                "code": x["code"],
                "name": x["name"],
                "notice": x["title"],
                "t0": x["t0"],
                "timing_grade": x["timing_grade"],
                "earlier_cninfo_deepseek_statements": len(
                    x["earlier_deepseek_statements"]
                ),
                "novelty_verdict": nv.get("verdict"),
                "earliest_earlier_denial": nv.get("earliest_earlier_denial"),
            }
            if x["t0"]:
                s = prices.returns(symbol_of(x["code"]), "raw")
                m = (
                    market_model(s, mkt, cal.index(x["t0"]))
                    if s is not None
                    else {"status": "no_price_data"}
                )
                row.update(
                    {
                        "status": m["status"],
                        **{
                            k: m.get(k)
                            for k in ["car_0_2", "car_3_20", "precar_m20_m1", "ar_0"]
                        },
                    }
                )
            extended.append(row)

    # plan item 7 (exploratory listing only): same firm's earlier AI-silent notice vs its first denial. Includes the
    # extended-sample first denials whose first notice is a risk warning rather than an abnormal-trading filing).
    silent_pairs = []
    ext_by_code = {x["code"]: x for x in extended if x.get("t0")}
    for r in res_c:
        x = ext_by_code.get(r["code"])
        if x and r["group"] == "X" and r["t0"] < x["t0"]:
            silent_pairs.append(
                {
                    "code": r["code"],
                    "name": r["name"],
                    "denial_group": "扩展样本（" + x["notice"] + "）",
                    "silent_t0": r["t0"],
                    "silent_car_0_2": r.get("car_0_2"),
                    "silent_precar_m20_m1": r.get("precar_m20_m1"),
                    "first_denial_t0": x["t0"],
                    "first_denial_car_0_2": x.get("car_0_2"),
                    "first_denial_precar_m20_m1": x.get("precar_m20_m1"),
                    "trading_days_apart": cal.index(x["t0"]) - cal.index(r["t0"]),
                }
            )
    # first denial event of each firm in announcements, whether T1 or T1p (already public elsewhere)
    t1_by_code = {}
    for r in sorted(res_c, key=lambda r: r["t0"]):
        if r["group"] in ("T1", "T1p") and r["code"] not in t1_by_code:
            t1_by_code[r["code"]] = r
    for r in res_c:
        if (
            r["group"] == "X"
            and r["code"] in t1_by_code
            and r["t0"] < t1_by_code[r["code"]]["t0"]
        ):
            t = t1_by_code[r["code"]]
            silent_pairs.append(
                {
                    "code": r["code"],
                    "name": r["name"],
                    "denial_group": t["group"],
                    "silent_t0": r["t0"],
                    "silent_car_0_2": r.get("car_0_2"),
                    "silent_precar_m20_m1": r.get("precar_m20_m1"),
                    "first_denial_t0": t["t0"],
                    "first_denial_car_0_2": t.get("car_0_2"),
                    "first_denial_precar_m20_m1": t.get("precar_m20_m1"),
                    "trading_days_apart": cal.index(t["t0"]) - cal.index(r["t0"]),
                }
            )

    # daily AR paths
    paths = {}
    for lab in [
        "T1 主样本(A/B级时间)",
        "T1p 此前已由其他渠道公开的否认",
        "R 重复否认",
        "K DeepSeek相关无否认",
        "K′ 否认之后的DeepSeek相关无否认",
        "N 无AI内容(事前有AI证据)",
        "P 总体基准(上涨触发)",
    ]:
        mat = np.array(
            [
                [np.nan if v is None else v for v in r["daily_ar"]]
                for r in groups[lab]
                if r.get("daily_ar")
            ]
        )
        if len(mat) == 0:
            continue
        mean = np.nanmean(mat, axis=0)
        n = np.sum(np.isfinite(mat), axis=0)
        sd = np.nanstd(mat, axis=0, ddof=1)
        paths[lab] = {
            "days": list(range(-20, 21)),
            "mean_ar": mean.tolist(),
            "n": n.tolist(),
            "se_iid": (sd / np.sqrt(n)).tolist(),
            "caar_from_m20": np.nancumsum(mean).tolist(),
        }

    # comparability of the groups before the event (descriptive; plan amendment 8)

    def comp(rows):
        """Describe pre-event characteristics and calendar concentration without causal adjustment."""
        f = lambda k: [r[k] for r in rows if r.get(k) is not None]
        med = lambda k: float(np.median(f(k))) if f(k) else None
        mean = lambda k: float(np.mean(f(k))) if f(k) else None
        dates = sorted(r["t0"] for r in rows)
        return {
            "n_events": len(rows),
            "n_firms": len({r["code"] for r in rows}),
            "n_dates": len(set(dates)),
            "t0_first": dates[0] if dates else None,
            "t0_last": dates[-1] if dates else None,
            "share_t0_2025-02-05_to_02-14": (
                float(np.mean([("2025-02-05" <= d <= "2025-02-14") for d in dates]))
                if dates
                else None
            ),
            "share_growth_board": (
                float(np.mean([r["board_group"] != "main" for r in rows]))
                if rows
                else None
            ),
            "precar_m20_m1_mean": mean("precar_m20_m1"),
            "precar_m20_m1_median": med("precar_m20_m1"),
            "precar_m5_m1_mean": mean("precar_m5_m1"),
            "precar_m5_m1_median": med("precar_m5_m1"),
            "limit_up_days_m3_m1_mean": mean("limit_up_days_m3_m1"),
            "turnover_ratio_m20_m1_median": med("turnover_ratio_m20_m1"),
            "turnover_ratio_m5_m1_median": med("turnover_ratio_m5_m1"),
            "sigma_resid_median": med("sigma_resid"),
            "beta_median": med("beta"),
        }

    comparability = {
        lab: comp(groups[lab])
        for lab in [
            "T1 主样本(A/B级时间)",
            "T1p 此前已由其他渠道公开的否认",
            "T2 否认内容更新",
            "R 重复否认",
            "K DeepSeek相关无否认",
            "K′ 否认之后的DeepSeek相关无否认",
            "O 其他AI内容",
            "N 无AI内容(事前有AI证据)",
            "P 总体基准(上涨触发)",
        ]
    }
    # the same-week pool contains the same-day pool (same day implies same ISO week)
    comparability["P 同周同板块池(对T1，冻结方案的匹配口径)"] = comp(
        [
            p
            for p in P
            if (p["week"], p["board_group"])
            in {(r["week"], r["board_group"]) for r in groups["T1 主样本(A/B级时间)"]}
        ]
    )
    comparability["P 同日同板块池(对T1)"] = comp(
        [
            p
            for p in P
            if (p["t0"], p["board_group"])
            in {(r["t0"], r["board_group"]) for r in groups["T1 主样本(A/B级时间)"]}
        ]
    )
    for lab in groups:
        for k in ["turnover_ratio_0_2"]:
            summary.append(summarize(groups[lab], k, lab))

    # overlapping windows (plan section 6): later same-firm abnormal-trading events inside T1 windows
    by_firm = collections.defaultdict(list)
    for r in res_c:
        by_firm[r["code"]].append(r)
    overlap = []
    for r in groups["T1 主样本(A/B级时间)"]:
        i0 = cal.index(r["t0"])
        later = [
            (cal.index(x["t0"]) - i0, x["group"])
            for x in by_firm[r["code"]]
            if x["t0"] > r["t0"]
        ]
        overlap.append(
            {
                "event_key": r["event_key"],
                "later_within_1_2": [g for d, g in later if d <= 2],
                "later_within_3_20": [g for d, g in later if 3 <= d <= 20],
            }
        )
    overlap_summary = {
        "n_T1": len(overlap),
        "with_later_event_in_1_20": sum(
            bool(o["later_within_1_2"] or o["later_within_3_20"]) for o in overlap
        ),
        "with_later_event_in_1_2": sum(bool(o["later_within_1_2"]) for o in overlap),
        "later_groups_in_1_20": dict(
            collections.Counter(
                g
                for o in overlap
                for g in o["later_within_1_2"] + o["later_within_3_20"]
            )
        ),
        "events": overlap,
    }

    # POST-HOC EXPLORATION (added after the main results were first viewed; not in the frozen plan):
    # is the positive T1 CAR[0,2] concentrated in events whose last trigger day closed limit-up, i.e. a
    # price-limit carry-over that the same-day benchmark shares? Listing and means only, no inference.
    limit_state = {}
    pool_T1 = comparability_pool = [
        p
        for p in P
        if (p["t0"], p["board_group"])
        in {(r["t0"], r["board_group"]) for r in groups["T1 主样本(A/B级时间)"]}
    ]
    for lab, rows in [
        ("T1 主样本(A/B级时间)", groups["T1 主样本(A/B级时间)"]),
        ("T1p 此前已由其他渠道公开的否认", groups["T1p 此前已由其他渠道公开的否认"]),
        ("K DeepSeek相关无否认", groups["K DeepSeek相关无否认"]),
        ("R 重复否认", groups["R 重复否认"]),
        ("P 与T1同日同板块", pool_T1),
        ("P 总体基准(上涨触发)", P),
    ]:
        cell = {}
        for flag in (True, False):
            v = [
                r["car_0_2"]
                for r in rows
                if r.get("limit_up_m1") is flag and r.get("car_0_2") is not None
            ]
            cell["limit_up_t-1" if flag else "not_limit_up_t-1"] = {
                "n": len(v),
                "mean": float(np.mean(v)) if v else None,
                "median": float(np.median(v)) if v else None,
            }
        cell["share_limit_up_t-1"] = (
            float(np.mean([bool(r.get("limit_up_m1")) for r in rows])) if rows else None
        )
        limit_state[lab] = cell

    # data-quality descriptors for T1
    t1 = groups["T1 主样本(A/B级时间)"]
    quality = {
        "T1_limit_up_t0": sum(r["limit_up_t0"] for r in t1),
        "T1_limit_down_t0": sum(r["limit_down_t0"] for r in t1),
        "T1_events_with_any_limit_day_0_2": sum(r["limit_days_0_2"] > 0 for r in t1),
        "T1_mean_limit_up_days_m3_m1": float(
            np.mean([r["limit_up_days_m3_m1"] for r in t1])
        ),
        "T1_n": len(t1),
        "P_up_limit_up_t0_share": float(np.mean([r["limit_up_t0"] for r in P])),
        "price_source_check": price_check,
    }
    out = {
        "plan": "分析方案_冻结.md",
        "groups": {k: len(v) for k, v in groups.items()},
        "summary": summary,
        "matched_benchmark": matched,
        "matched_benchmark_same_week": matched_week,
        "differences": diffs,
        "comparability": comparability,
        "P_attrition": P_attrition,
        "heterogeneity_T1_first_run": hetero_first_run,
        "posthoc_heterogeneity_apre_strict": hetero_apre_strict,
        "overlap_T1": overlap_summary,
        "posthoc_limit_state_exploration": limit_state,
        "exploratory_regression": reg,
        "paths": paths,
        "not_computable": not_computable,
        "quality": quality,
        "wild_bootstrap_means": wild,
        "heterogeneity_T1": hetero,
        "T1_excluding_other_news": other_news_sub,
        "P_price_robustness": p_robust,
        "T1_not_up_trigger": t1_not_up,
        "exploratory_same_firm_silent_vs_first_denial": silent_pairs,
        "extended_sample_listing": extended,
    }
    write_json(RESULTS / "main_results.json", out)
    print(json.dumps(out["groups"], ensure_ascii=False))
    print(json.dumps(quality, ensure_ascii=False))
    print("not computable:", not_computable)


if __name__ == "__main__":
    main()
