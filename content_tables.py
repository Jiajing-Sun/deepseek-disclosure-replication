# Content-only tabulation: no return inputs or outcome-based selection.
"""Tabulate sample formation, denial breadth, adoption and shared wording.
This module reads coded documents and announcement text; it never reads returns.
The original Chinese coding labels are data values, preserved for exact replication."""

import json, re, collections
from common import *

TEMPLATES = {
    "开源模型任何用户可免费训练": r"任何用户皆可(免费)?基于该模型开展训练",
    "各家厂商均可适配与本地化部署": r"各(家)?厂商均可根据(自身|业务)需求对其进行模型的适配",
    "未与DeepSeek签署服务合作协议": r"未与DeepSeek(公司)?签署服务合作协议",
    "无任何业务往来": r"无任何业务往来",
    "未直接或间接持有深度求索股权": r"未直接或间接持有杭州深度求索",
    "对当前主营业务开展无实质影响": r"对(当前|公司)?(当前)?主营业务开展(并)?无实质(性)?影响",
    "相关平台将公司股票纳入DeepSeek概念股": r"相关平台将公司股票纳入DeepSeek概念股",
}


# Format counts without changing coding categories.
def md_table(header, rows):
    """Format headers and rows as a Markdown table."""
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(x) for x in r) + " |" for r in rows]
    return "\n".join(out)


# Build sample, content and wording tables from the frozen input labels.
def main():
    frame = json.loads((DATA / "frame_audit.json").read_text())
    screening = json.loads((DATA / "screening_audit.json").read_text())
    coding = read_jsonl(OUT_DATA / "coding_documents.jsonl")
    events = read_jsonl(OUT_DATA / "events_candidate_firms.jsonl")
    docs_groups = {
        r["announcement_id"]: r
        for r in read_jsonl(OUT_DATA / "documents_candidate_firms_groups.jsonl")
    }
    cand = read_jsonl(DATA / "ai_candidates.jsonl")
    ds_kw = [
        r
        for r in cand
        if any(re.search("(?i)deep\\s*seek|深度求索", h["keyword"]) for h in r["hits"])
    ]
    out, md = {}, []

    # sample formation
    t1_events = [e for e in events if e["group"] == "T1"]
    formation = [
        ("巨潮固定标题查询唯一记录（2025Q1）", frame["unique_ids"]),
        ("符合标题与证券范围", frame["eligible_documents"]),
        ("取得PDF并解析", screening["downloaded_and_parsed"]),
        ("AI关键词候选公告（70家公司）", len(cand)),
        ("  其中关键词含DeepSeek/深度求索", len(ds_kw)),
        (
            "扩展检索补充（“幻方”，2家公司）",
            sum(r["supplementary_outside_keyword_set"] for r in coding),
        ),
        ("本轮逐篇编码公告", len(coding)),
        (
            "  涉及DeepSeek/深度求索/幻方的公告",
            sum(r["deepseek_related"] for r in coding),
        ),
        ("候选公司全部异动公告合并后的公司-事件", len(events)),
        (
            "  T1 首次开发商关系否认（公司数）",
            f"{len(t1_events)}（{len({e['code'] for e in t1_events})}）",
        ),
    ]
    out["formation"] = formation
    md.append("### 样本形成\n\n" + md_table(["环节", "数量"], formation))

    # content categories (documents)
    cats = collections.Counter()
    for r in coding:
        for c in r["content"].split("；"):
            cats[c] += 1
    out["content_categories_docs"] = dict(cats)
    md.append(
        "### 内容类型（公告层面，可多选）\n\n"
        + md_table(["内容类型", "公告数"], sorted(cats.items(), key=lambda x: -x[1]))
    )

    # groups (events)
    g = collections.Counter(e["group"] for e in events)
    out["event_groups"] = dict(g)
    md.append(
        "### 公司-事件分组\n\n"
        + md_table(
            ["组别", "事件数", "公司数"],
            [
                (k, g[k], len({e["code"] for e in events if e["group"] == k}))
                for k in ["T1", "T1p", "T2", "R", "K", "K_after_denial", "O", "N", "X"]
            ],
        )
    )

    # content of first denials: all C1 announcements (each firm's first developer-relationship denial among its
    # own filings, text-only label from build_history.py), with the outcome of the first-public-disclosure check
    cmap = {c["announcement_id"]: c for c in coding}
    nov = read_jsonl(OUT_DATA / "document_novelty.jsonl")
    c1_ids = [
        r["announcement_id"]
        for r in nov
        if r["novelty_within_candidate_docs"].startswith("C1")
    ]
    t1_docs = [cmap[a] for a in c1_ids]
    outcome = collections.Counter(docs_groups[a]["doc_group"] for a in c1_ids)
    out["c1_novelty_check_outcome"] = dict(outcome)
    md.append(
        "### 公告中的首次开发商关系否认（C1，按公司）及首次公开性核验结果\n\n"
        + md_table(
            ["核验后组别", "公告数"],
            [(k, outcome[k]) for k in ["T1", "T1p", "T2", "R"] if outcome[k]]
            + [("合计", len(c1_ids))],
        )
    )
    cross = collections.Counter((d["biz"], d["eq"]) for d in t1_docs)
    out["c1_biz_by_eq"] = {f"{a}|{b}": n for (a, b), n in cross.items()}
    biz_levels = ["否认任何业务往来", "否认业务合作", "仅否认特定形式", "未说明"]
    eq_levels = ["否认直接和间接股权", "仅否认特定形式", "未说明"]
    rows = [
        [b]
        + [cross.get((b, e), 0) for e in eq_levels]
        + [sum(cross.get((b, e), 0) for e in eq_levels)]
        for b in biz_levels
    ]
    rows.append(
        ["合计"]
        + [sum(cross.get((b, e), 0) for b in biz_levels) for e in eq_levels]
        + [len(t1_docs)]
    )
    md.append(
        f"### C1首次否认（{len(t1_docs)}份）：商业关系否认宽度 × 股权否认宽度（公告数）\n\n"
        + md_table(["商业关系＼股权"] + eq_levels + ["合计"], rows)
    )
    for dim, lab in [
        ("adopt", "同一公告中的技术采用状态"),
        ("order", "订单/合同"),
        ("rev", "收入"),
        ("prod", "产品/商业化"),
    ]:
        c = collections.Counter(d[dim] for d in t1_docs)
        out[f"c1_{dim}"] = dict(c)
        md.append(
            f"### C1首次否认（{len(t1_docs)}份）：{lab}\n\n"
            + md_table(["编码", "公告数"], sorted(c.items(), key=lambda x: -x[1]))
        )
    attn = sum(1 for d in t1_docs if d["market_attention_quote"])
    out["c1_with_market_attention_statement"] = attn
    # the same breadth table for the 28 T1 events only (after the first-public-disclosure check)
    t1_only = [
        cmap[a]
        for e in t1_events
        for a in e["announcement_ids"].split(";")
        if a in cmap
    ]
    cross_t1 = collections.Counter((d["biz"], d["eq"]) for d in t1_only)
    rows = [
        [b]
        + [cross_t1.get((b, e), 0) for e in eq_levels]
        + [sum(cross_t1.get((b, e), 0) for e in eq_levels)]
        for b in biz_levels
    ]
    rows.append(
        ["合计"]
        + [sum(cross_t1.get((b, e), 0) for b in biz_levels) for e in eq_levels]
        + [len(t1_only)]
    )
    out["t1_biz_by_eq"] = {f"{a}|{b}": n for (a, b), n in cross_t1.items()}
    md.append(
        f"### 其中T1（首次公开否认，{len(t1_only)}份）：商业关系否认宽度 × 股权否认宽度\n\n"
        + md_table(["商业关系＼股权"] + eq_levels + ["合计"], rows)
    )
    out["t1_adopt"] = dict(collections.Counter(d["adopt"] for d in t1_only))

    # boilerplate usage across all coded DeepSeek-related documents
    ds_docs = [r for r in coding if r["deepseek_related"]]
    tmpl = {}
    for name, pat in TEMPLATES.items():
        hits = [
            r
            for r in ds_docs
            if re.search(
                pat,
                compact("\n".join(p["text"] for p in doc_pages(r["announcement_id"]))),
                re.I,
            )
        ]
        tmpl[name] = {"documents": len(hits), "firms": len({r["code"] for r in hits})}
    out["boilerplate_in_deepseek_docs"] = tmpl
    out["deepseek_docs"] = len(ds_docs)
    md.append(
        f"### DeepSeek相关公告中的共同表述（{len(ds_docs)}份公告）\n\n"
        + md_table(
            ["表述", "公告数", "公司数"],
            [(k, v["documents"], v["firms"]) for k, v in tmpl.items()],
        )
    )
    write_json(RESULTS / "content_tables.json", out)
    (RESULTS / "result_content_tables.md").write_text("\n\n".join(md) + "\n")
    print("\n\n".join(md))


if __name__ == "__main__":
    main()
