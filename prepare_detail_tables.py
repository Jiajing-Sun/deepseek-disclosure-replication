"""Generate the nine-case history table and date-level diagnostics.
Run after prepare_content_evidence.py. History summaries are paraphrases, not quotes.
Gaps count exchange dates from the earlier record date inclusive to the focal date exclusive.
For 301299, the January 7 family-history date differs from the January 27 exact-object record.
"""

from pathlib import Path
import json
import csv
from statistics import mean

B = Path(__file__).resolve().parent
D = json.loads((B / "article_data.json").read_text())
H = json.loads((B / "historical_evidence.json").read_text())
T = {
    t["code"]: t
    for t in json.loads((B / "content_evidence.json").read_text())["history_timing"]
}

# Use evidence-based English paraphrases and stable security codes.
summaries = {
    "000532": "Earlier reply: neither the company nor funds managed by its subsidiaries hold equity in High-Flyer or DeepSeek. Filing: they did not take part in DeepSeek financing. The earlier denial covers any holding; the filing's explicit inclusion of controlled subsidiaries is retained as a boundary judgment.",
    "300078": "Earlier statement by the securities department to a financial-news reporter: no link with DeepSeek. Filing: no related cooperation with DeepSeek. The attributed general denial covers the narrower cooperation claim.",
    "301299": "Earlier reply: no business cooperation yet with DeepSeek. Filing: none yet with its affiliate High-Flyer. Company staff told a newspaper, in a report at 15:12 on 27 January before the evening filing, that there was no business cooperation with High-Flyer, which supplies the object-specific match.",
    "301396": "Earlier reply and filing both deny current business cooperation with DeepSeek; the reply also reports work on integrating the model into the company's own products.",
    "600186": "Reply displayed at 10:09: no capital or equity cooperation with DeepSeek. Evening filing: no direct or indirect holding in the developer. Same dimension; the reply appeared during the trading session.",
    "301602": "Earlier reply: no co-investment or joint research with DeepSeek in medical robotics. Filing: no business cooperation, without the field restriction. The commercial denial is broadened.",
    "603956": "Earlier reply: no capital or equity cooperation, while affirming use of DeepSeek models. Filing: adds that no service agreement has been signed and extends the equity denial to direct or indirect holdings in the named developer.",
    "688158": "Earlier reply (2024): no substantive cooperation with High-Flyer. Filing: no direct or indirect holding in the developer. Ownership enters an existing developer-family denial history as a new dimension.",
    "688229": "Earlier reply: no direct business cooperation or commercial contact yet. Filing: drops the direct-only qualifier, adds a direct-or-indirect ownership denial and reports partial integration without revenue.",
}
assert set(summaries) == {h["code"] for h in H}
t = r"""\begin{table}[!t]
\caption{Earlier public evidence and the nine reclassified candidates. Summaries paraphrase the evidence review; they are not verbatim quotations.}\label{tab:history}
\small
\begin{tabularx}{\linewidth}{l l l >{\raggedright\arraybackslash}X}
\toprule
Code & Earlier record & Focal event & Proposition comparison \\
\midrule
"""
# List the five restatements first, then the four scope updates, sorted by security code.
for h in sorted(H, key=lambda x: (x["classification"] != "Restatement", x["code"])):
    channel = "Media" if h["code"] == "300078" else "Platform"
    tm = T[h["code"]]
    gap = f"{tm['sessions_before_event']} day" + (
        "" if tm["sessions_before_event"] == 1 else "s"
    )
    t += (
        h["code"]
        + " & "
        + r"\shortstack[l]{"
        + h["earlier_record"]["date"]
        + r"\\"
        + channel
        + "} & "
        + r"\shortstack[l]{"
        + tm["event_date"]
        + r"\\"
        + gap
        + "} & "
        + r"\textit{"
        + h["classification"]
        + "}. "
        + summaries[h["code"]]
        + r" \\[4pt]"
        + "\n"
    )
t += r"""\bottomrule
\end{tabularx}
\begin{adjustwidth}{0cm}{0cm}\footnotesize
The earlier record marks the retained developer-family history: the earliest same-dimension denial for restatements, and the earliest family denial for updates. For 301299, the later High-Flyer report supplies the exact-object match. ``Focal event'' is the first trading day whose close can reflect the filing. Gaps count exchange trading dates from the earlier date (inclusive) to the event date (exclusive), not elapsed sessions or exact-proposition novelty. Both one-day records precede that day's close (10:09 and 11:30). Platform records are company replies on the exchange question-and-answer platforms, preserved through dated public reproductions. The historical-evidence file retains source URLs and announcement identifiers; the table gives English paraphrases of the evidence comparisons.
\end{adjustwidth}
\end{table}
"""
(B / "history_cases.tex").write_text(t)

# Average events within dates, then average the 12 date means with equal weights.
rows = []
for date in sorted({r["t0"] for r in D["event_rows"]}):
    events = [r for r in D["event_rows"] if r["t0"] == date]
    rows.append(
        dict(
            event_date=date,
            n=len(events),
            car_percent=mean(r["car"] for r in events),
            week_diff_pp=mean(r["week_diff"] for r in events),
            day_diff_pp=mean(r["day_diff"] for r in events),
        )
    )
assert sum(r["n"] for r in rows) == 28 and len(rows) == 12
assert abs(mean(r["car_percent"] for r in rows) - D["core"]["date_mean"]) < 1e-10
assert (
    abs(
        mean(r["week_diff_pp"] for r in rows) - D["comparisons"]["week"]["date_mean_pp"]
    )
    < 1e-10
)
assert (
    abs(mean(r["day_diff_pp"] for r in rows) - D["comparisons"]["day"]["date_mean_pp"])
    < 1e-10
)
with (B / "date_level_diagnostics.csv").open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
t = r"""\begin{table}[!htbp]
\caption{Date-level composition and conditional return differences. Each return entry is the equal-weight mean of focal events on that date. CAR is in percent; differences are in percentage points.}\label{tab:dates}
\small
\begin{tabularx}{\linewidth}{X r r r r}
\toprule
Event date & Events & CAR[0,2] & Week difference & Day difference \\
\midrule
"""
for r in rows:
    f = lambda x: f"{x:.2f}".replace("-", "$-$")  # Use a mathematical minus sign.
    t += (
        f"{r['event_date']} & {r['n']} & {f(r['car_percent'])} & {f(r['week_diff_pp'])} & {f(r['day_diff_pp'])} "
        + r"\\"
        + "\n"
    )
t += r"""\bottomrule
\end{tabularx}
\begin{adjustwidth}{0cm}{0cm}\footnotesize
Equal averaging across the 12 rows recovers the date-equal estimates; weighting each row by its event count recovers the event-equal estimates. These rows describe the same sample and are not independent replications or individual significance tests.
\end{adjustwidth}
\end{table}
"""
(B / "date_diagnostics.tex").write_text(t)
print(
    "Generated nine-case history table, 12-date diagnostic table and CSV; aggregates verified."
)
