"""Recompute article content combinations and history timing when requested.
Set DISCLOSURE_INPUT_DIR to the flat analysis staging directory for recomputation.
Without it, explicitly reuse the supplied content_evidence.json snapshot.
Content categories are determined without returns; price-role summaries are descriptive.
"""

from pathlib import Path
import os
import bisect
import collections
import json
import re

B = Path(__file__).resolve().parent
SRC = (
    Path(os.environ["DISCLOSURE_INPUT_DIR"])
    if os.environ.get("DISCLOSURE_INPUT_DIR")
    else None
)
OUT = B / "content_evidence.json"

ADOPTED = {"已接入或部署-部分产品或场景", "已接入或部署"}
# Aggregate the original adoption labels into the five article categories.
ADOPT_ROWS = [
    ("Adopted or deployed", ADOPTED),
    ("Testing, adaptation or research", {"测试/适配/研发中"}),
    ("Distribution, listing or hosting", {"仅分发/上架/托管"}),
    ("Explicit non-involvement", {"明确不涉及"}),
    ("Not stated", {"未说明"}),
]
# Use the same open-license wording pattern as the content-table analysis.
OPEN_LICENCE = r"任何用户皆可(免费)?基于该模型开展训练"
NO_SERVICE_AGREEMENT = r"未与DeepSeek(公司)?签署服务合作协议"


def read_jsonl(path):
    """Read nonblank JSON Lines records in their original order."""
    return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]


def compact(text):
    return re.sub(r"\s+", "", text)


def attention_type(quote):
    """Classify quoted attention references using the fixed ordered text rules."""
    if quote is None:
        return "none"
    if "概念股" in quote and re.search("平台|媒体", quote):
        return "classification"
    if re.search("传言|传闻|股吧", quote):
        return "rumor"
    if "互动易" in quote:
        return "platform_question"
    if "关注度" in quote:
        return "attention"
    return "report_on_own_activity"


def recompute():
    """Recompute content counts and history timing, then extract audited group-return summaries."""
    coding = {
        r["announcement_id"]: r for r in read_jsonl(SRC / "coding_documents.jsonl")
    }
    novelty = read_jsonl(SRC / "document_novelty.jsonl")
    groups = {
        r["announcement_id"]: r
        for r in read_jsonl(SRC / "documents_candidate_firms_groups.jsonl")
    }
    pages = json.loads((SRC / "announcement_text_pages.json").read_text())
    text = {a: compact("".join(p["text"] for p in pages[a])) for a in pages}
    c1 = [
        r["announcement_id"]
        for r in novelty
        if r["novelty_within_candidate_docs"].startswith("C1")
    ]
    assert len(c1) == 38
    docs = [coding[a] for a in c1]

    # Partition first denials into commercial-only, equity-only and both; columns must sum to 38.
    def denied(d):
        """Return the exclusive commercial-only, equity-only or both denial category."""
        biz, eq = d["biz"] != "未说明", d["eq"] != "未说明"
        return "both" if biz and eq else ("commercial_only" if biz else "equity_only")

    combos = []
    for label, codes in ADOPT_ROWS:
        sub = [d for d in docs if d["adopt"] in codes]
        c = collections.Counter(denied(d) for d in sub)
        combos.append(
            dict(
                adoption=label,
                commercial_only=c["commercial_only"],
                equity_only=c["equity_only"],
                both=c["both"],
                total=len(sub),
            )
        )
    assert sum(r["total"] for r in combos) == 38

    # Count the broadest commercial and equity denials together; this is not a denial of every relationship.
    broadest = sum(
        1
        for d in docs
        if d["biz"] == "否认任何业务往来" and d["eq"] == "否认直接和间接股权"
    )

    # Verify that every retained attention quotation occurs verbatim in its announcement.
    for d in docs:
        q = d["market_attention_quote"]
        assert q is None or compact(q) in text[d["announcement_id"]], d["code"]
    att = collections.Counter(attention_type(d["market_attention_quote"]) for d in docs)
    att_adopters = collections.Counter(
        attention_type(d["market_attention_quote"])
        for d in docs
        if d["adopt"] in ADOPTED
    )
    lic = [d for d in docs if re.search(OPEN_LICENCE, text[d["announcement_id"]])]
    nsa = [
        d
        for d in docs
        if re.search(NO_SERVICE_AGREEMENT, text[d["announcement_id"]], re.I)
    ]

    # Count adoption reported in focal T1 filings, distinct from adoption evidence available beforehand.
    t1_docs = [d for d in docs if groups[d["announcement_id"]]["doc_group"] == "T1"]
    assert len(t1_docs) == 28

    # Count exchange dates from the earlier record date inclusive to the event date exclusive.
    cal = sorted(
        {
            r["date"]
            for r in read_jsonl(SRC / "daily_prices.jsonl")
            if r["symbol"] == "sh000985" and r["adjustment_requested"] == "raw"
        }
    )
    hist = json.loads((B / "historical_evidence.json").read_text())
    timing = []
    for h in hist:
        t0 = coding[h["announcement_id"]]["t0_final"]
        e = h["earlier_record"]["date"]
        sessions = bisect.bisect_left(cal, t0) - bisect.bisect_left(cal, e)
        timing.append(
            dict(
                code=h["code"],
                classification=h["classification"],
                earlier_date=e,
                event_date=t0,
                sessions_before_event=sessions,
            )
        )
    gaps = sorted(t["sessions_before_event"] for t in timing)

    # Extract audited group summaries; pre-event completeness can differ because of suspended trading.
    res = json.loads((SRC / "result_main_results.json").read_text())
    want = [
        ("T1", "T1 主样本(A/B级时间)"),
        ("T1p", "T1p 此前已由其他渠道公开的否认"),
        ("R", "R 重复否认"),
        ("K", "K DeepSeek相关无否认"),
        ("P", "P 总体基准(上涨触发)"),
    ]
    roles = {}
    for short, g in want:
        rows = {s["outcome"]: s for s in res["summary"] if s["group"] == g}
        roles[short] = dict(
            events=rows["car_0_2"]["n_events"],
            dates=rows["car_0_2"]["n_dates"],
            precar_events=rows["precar_m20_m1"]["n_events"],
            precar=100 * rows["precar_m20_m1"]["mean"],
            ar0=100 * rows["ar_0"]["mean"],
            car12=100 * rows["car_1_2"]["mean"],
            car02=100 * rows["car_0_2"]["mean"],
            car02_ci=[100 * v for v in rows["car_0_2"]["ci_date_cluster"]],
            ar0_ci=[100 * v for v in rows["ar_0"]["ci_date_cluster"]],
            car12_ci=[100 * v for v in rows["car_1_2"]["ci_date_cluster"]],
        )
    diff = {d["contrast"] + "|" + d["outcome"]: d for d in res["differences"]}
    t1_t1p = diff["T1 主样本(A/B级时间) − T1p 此前已由其他渠道公开的否认|car_0_2"]

    return dict(
        note="Recomputed from coded documents and audited results; categories do not use returns.",
        c1_documents=38,
        adoption_by_denied_dimension=combos,
        broadest_commercial_and_equity_denials=broadest,
        attention_reference_types=dict(att),
        attention_reference_types_adopters=dict(att_adopters),
        open_licence_statement=dict(
            documents=len(lic), adopters=sum(d["adopt"] in ADOPTED for d in lic)
        ),
        no_service_agreement_statement=dict(
            documents=len(nsa), adopters=sum(d["adopt"] in ADOPTED for d in nsa)
        ),
        t1_focal_filing_reports_adoption=sum(d["adopt"] in ADOPTED for d in t1_docs),
        history_timing=timing,
        history_gap_median=gaps[len(gaps) // 2],
        history_gap_within_20=sum(g <= 20 for g in gaps),
        history_gap_within_8=sum(g <= 8 for g in gaps),
        roles=roles,
        t1_minus_t1p=dict(
            diff=100 * t1_t1p["diff"],
            ci=[100 * v for v in t1_t1p["ci_date_cluster"]],
            clusters=t1_t1p["clusters"],
        ),
    )


def fmt(v):
    """Format a two-decimal value for an article table."""
    return f"{v:.2f}".replace("-", "$-$")


def write_tables(E):
    # Write the adoption-by-denied-dimension table.
    """Render content-combination and information-role tables from the supplied evidence object."""
    t = r"""\begin{table}[htbp]
\caption{What the 38 first relationship denials exclude and what they report about adoption. Each filing is counted once; the three denial columns are mutually exclusive.}\label{tab:combinations}
\small
\begin{tabularx}{\linewidth}{X r r r r}
\toprule
& \multicolumn{3}{c}{Relationship denied in the same filing} & \\
\cmidrule(lr){2-4}
Adoption status reported & Commercial only & Equity only & Both & Total \\
\midrule
"""
    for r in E["adoption_by_denied_dimension"]:
        t += (
            f"{r['adoption']} & {r['commercial_only']} & {r['equity_only']} & {r['both']} & {r['total']} "
            + r"\\"
            + "\n"
        )
    tot = {
        k: sum(r[k] for r in E["adoption_by_denied_dimension"])
        for k in ("commercial_only", "equity_only", "both", "total")
    }
    t += (
        r"\midrule"
        + "\n"
        + f"Total & {tot['commercial_only']} & {tot['equity_only']} & {tot['both']} & {tot['total']} "
        + r"\\"
        + "\n"
    )
    t += r"""\bottomrule
\end{tabularx}
\begin{adjustwidth}{0cm}{0cm}\footnotesize
``Adopted or deployed'' includes 14 filings that restrict deployment to particular products or scenarios. A dimension the filing does not address is coded as not stated and is not treated as a denial. Source: proposition-level coding of the filings, with verbatim quotations and page references.
\end{adjustwidth}
\end{table}
"""
    (B / "content_combinations.tex").write_text(t)

    # Write descriptive return summaries by information role.
    R = E["roles"]
    names = [
        ("T1", "First public denials"),
        ("T1p", "Restated earlier denials"),
        ("R", "Later repeated denials"),
        ("K", "DeepSeek, no denial"),
        ("P", "Upward-triggered benchmarks"),
    ]
    t = r"""\begin{table}[htbp]
\caption{Information role of the filing and its trading stage. Means of abnormal returns in percent.}\label{tab:roles}
\small
\begin{tabularx}{\linewidth}{>{\raggedright\arraybackslash}X r r r r r}
\toprule
Filing group & $n$ (dates) & $CAR[-20,-1]$ & $AR[0]$ & $CAR[1,2]$ & $CAR[0,2]$ \\
\midrule
"""
    for k, n in names:
        r = R[k]
        t += (
            f"{n} & {r['events']} ({r['dates']}) & {fmt(r['precar'])} & {fmt(r['ar0'])} & {fmt(r['car12'])} & {fmt(r['car02'])} "
            + r"\\"
            + "\n"
        )
    t += r"""\bottomrule
\end{tabularx}
\begin{adjustwidth}{0cm}{0cm}\footnotesize
First public denials are the 28 main events. Restated earlier denials are the five candidates with an earlier equivalent or broader public denial. Later repeated denials are subsequent abnormal-trading announcements that repeat a firm's earlier denial. ``DeepSeek, no denial'' contains DeepSeek-related filings that report facts such as adoption without denying a developer relationship; ``Upward-triggered benchmarks'' comprises the 803 other comparison events, rather than all 1,179 source announcements. The pre-event window is complete for 27, 5, 20, 9 and 780 events, respectively. Groups other than the first and last rows are small and are reported descriptively.
\end{adjustwidth}
\end{table}
"""
    (B / "role_table.tex").write_text(t)


if __name__ == "__main__":
    if SRC is not None:
        print("Recomputing content evidence from external inputs.")
        E = recompute()
        OUT.write_text(json.dumps(E, ensure_ascii=False, indent=2) + "\n")
    else:
        print(
            "Snapshot mode: using archived content evidence; no recoding or return estimation."
        )
        E = json.loads(OUT.read_text())
    assert E["roles"]["T1"]["events"] == 28 and E["roles"]["T1"]["dates"] == 12
    assert abs(E["roles"]["T1"]["car02"] - 10.716064025691214) < 1e-9
    write_tables(E)
    print(
        "Content combinations, attention references, history timing and role table generated."
    )
