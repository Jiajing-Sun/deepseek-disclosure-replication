"""Generate the article price tables, two figures and event-level CSV.
Reads article_data.json; does not choose events or re-estimate returns.
Use run_all.py for snapshot reproduction or full estimation with external inputs."""

from pathlib import Path
import json, csv
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

B = Path(__file__).resolve().parent
D = json.loads((B / "article_data.json").read_text())
S = D["comparisons"]
C = D["core"]


def num(x):
    # Use a mathematical minus sign in LaTeX.
    """Format a two-decimal table entry with a mathematical minus sign."""
    return ("%.2f" % x).replace("-", "$-$")


def interval(v):
    """Format a two-endpoint confidence interval for LaTeX."""
    return "[%s, %s]" % (num(v[0]), num(v[1]))


# Keep each mean and interval aligned with the same weighting and matching rule.
rows = [
    ("First public denials", C["mean"], C["ci"], C["date_mean"], C["date_ci"]),
    (
        "Same-week matched difference",
        S["week"]["mean_pp"],
        S["week"]["ci_pp"],
        S["week"]["date_mean_pp"],
        S["week"]["date_ci_pp"],
    ),
    (
        "Same-day matched difference",
        S["day"]["mean_pp"],
        S["day"]["ci_pp"],
        S["day"]["date_mean_pp"],
        S["day"]["date_ci_pp"],
    ),
]
t = r"""\begin{table}[htbp]
\caption{Main price comparisons and weighting. CAR is in percent; matched differences are in percentage points. Each row uses 28 focal events on 12 dates.}\label{tab:prices}
\small
\begin{tabularx}{\linewidth}{X r l r l}
\toprule
& \multicolumn{2}{c}{Event-equal} & \multicolumn{2}{c}{Date-equal} \\
Outcome & Mean & 95\% interval & Mean & 95\% interval \\
\midrule
"""
for name, m, ci, dm, dci in rows:
    t += (
        f"{name} & {num(m)} & {interval(ci)} & {num(dm)} & {interval(dci)} "
        + r"\\"
        + "\n"
    )
t += r"""\bottomrule
\end{tabularx}
\begin{adjustwidth}{0cm}{0cm}\footnotesize
Event-equal intervals cluster by event date. Date-equal intervals use the 12 date means and a $t$ reference distribution. Matching follows Equation~\ref{eq:match}: each focal CAR is compared with its own pool mean before averaging, and the pools may overlap.
\end{adjustwidth}
\end{table}
"""
(B / "price_table.tex").write_text(t)
# Report supplementary restrictions separately, retaining the midnight information cutoff.
t = r"""\begin{table}[htbp]
\caption{Supplementary matching conditions. All entries are percentage points, with 28 focal events and 12 dates.}\label{tab:sensitivity}
\small
\begin{tabularx}{\linewidth}{X r l r l}
\toprule
& \multicolumn{2}{c}{Event-equal} & \multicolumn{2}{c}{Date-equal} \\
Condition & Mean & 95\% interval & Mean & 95\% interval \\
\midrule
"""
for key, name in [
    ("week_exclude_prior_qa", "Week; exclude earlier theme answers"),
    ("day_exclude_prior_qa", "Day; exclude earlier theme answers"),
    ("week_match_limit", "Week; match previous closing-limit state"),
]:
    d = S[key]
    t += (
        f"{name} & {num(d['mean_pp'])} & {interval(d['ci_pp'])} & {num(d['date_mean_pp'])} & {interval(d['date_ci_pp'])} "
        + r"\\"
        + "\n"
    )
t += r"""\bottomrule
\end{tabularx}
\begin{adjustwidth}{0cm}{0cm}\footnotesize
Earlier answers must predate 00:00 on the event date. Event-equal intervals cluster by event date; date-equal intervals use date means.
\end{adjustwidth}
\end{table}
"""
(B / "sensitivity_table.tex").write_text(t)
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "pdf.fonttype": 42})
# Solid arrows describe observed connections; numbers come from the article evidence.
# Dashed feedback is unestimated; the gray box identifies unobserved variables outside the boundary.
fig, ax = plt.subplots(figsize=(9.2, 5.2))
ax.set(xlim=(0, 10.4), ylim=(0, 6.0))
ax.axis("off")
INK, SOFT = "#2c3e55", "#f2f4f7"


def box(x, y, w, h, title, body, dashed=False):
    """Draw a labeled system component; dashed boxes identify unobserved components."""
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.04",
            facecolor="white" if dashed else SOFT,
            edgecolor="#8a8f98" if dashed else INK,
            linewidth=0.9,
            linestyle="--" if dashed else "-",
        )
    )
    ax.text(
        x + w / 2,
        y + h - 0.32,
        title,
        ha="center",
        va="center",
        fontsize=9,
        fontweight="bold",
        color="#555" if dashed else INK,
    )
    ax.text(
        x + w / 2,
        y + (h - 0.32) / 2,
        body,
        ha="center",
        va="center",
        fontsize=8.3,
        linespacing=1.45,
        color="#555" if dashed else "black",
    )


def arrow(p0, p1, label, lx, ly, dashed=False, ha="center"):
    """Draw and label a system connection without asserting causal identification."""
    ax.annotate(
        "",
        p1,
        p0,
        arrowprops={
            "arrowstyle": "->",
            "color": "#888" if dashed else INK,
            "linewidth": 0.9,
            "linestyle": "--" if dashed else "-",
            "shrinkA": 0,
            "shrinkB": 0,
        },
    )
    ax.text(
        lx,
        ly,
        label,
        ha=ha,
        va="center",
        fontsize=7.8,
        style="italic",
        color="#555" if dashed else INK,
        linespacing=1.3,
    )


box(
    0.1,
    3.55,
    3.0,
    1.55,
    "Firm and developer family",
    "Adoption · contracts\nequity · commercialization",
)
box(
    3.7,
    3.55,
    3.0,
    1.55,
    "Public channels",
    "Abnormal-trading filings\nplatform replies · media",
)
box(
    7.3,
    3.55,
    3.0,
    1.55,
    "Classification and attention",
    "Concept-stock lists · rumors\ninvestor questions",
)
box(3.7, 0.45, 3.0, 1.55, "Event record", "Proposition $q$ and its\nfirst public time")
box(
    7.3,
    0.45,
    3.0,
    1.55,
    "Trading environment",
    "Price triggers · limit states\ncommon event dates",
)
box(
    0.1,
    0.45,
    3.0,
    1.55,
    "Outside the boundary",
    "Investor beliefs\nprivate communication",
    dashed=True,
)
arrow(
    (3.1, 4.33),
    (3.7, 4.33),
    "statements: 18 of 38 first\ndenials also report adoption",
    3.4,
    5.55,
)
arrow((7.3, 4.33), (6.7, 4.33), "occasion cited in 37\nof 38 first denials", 7.0, 5.55)
arrow(
    (5.2, 3.55),
    (5.2, 2.0),
    "cross-channel history\nreclassifies 9 of 37",
    5.05,
    2.78,
    ha="right",
)
arrow((8.1, 2.0), (6.55, 3.55), "rule-based\nfiling trigger", 7.5, 2.95, ha="left")
arrow((6.7, 1.0), (7.3, 1.0), "benchmark mean: 1.87% (week)\nvs 6.22% (day)", 7.0, 0.12)
arrow(
    (9.4, 2.0),
    (9.4, 3.55),
    "attention feedback\n(not estimated)",
    9.5,
    2.78,
    dashed=True,
    ha="left",
)
fig.savefig(B / "information_system.pdf", bbox_inches="tight")
plt.close(fig)
# Plot intervals directly from the numerical source without truncating them.
fig, ax = plt.subplots(figsize=(8, 2.9))
for y, key in [(1, "week"), (0, "day")]:
    d = S[key]
    m = d["mean_pp"]
    lo, hi = d["ci_pp"]
    ax.errorbar(
        m,
        y,
        xerr=[[m - lo], [hi - m]],
        fmt="o",
        capsize=5,
        color="#263e59",
        markersize=7,
    )
    ax.text(20, y, f"{m:.2f}  [{lo:.2f}, {hi:.2f}]", va="center", fontsize=9)
ax.set_yticks([1, 0], ["Same week and board", "Same day and board"])
ax.axvline(0, color="#888", linestyle="--", linewidth=0.8)
ax.set_xlim(-5, 33)
ax.set_ylim(-0.6, 1.6)
ax.set_xlabel("Matched difference in CAR[0,2] (percentage points)")
ax.set_xticks([-5, 0, 5, 10, 15, 20])
ax.spines[["top", "right", "left"]].set_visible(False)
ax.tick_params(axis="y", length=0)
fig.tight_layout()
fig.savefig(B / "matched_differences.pdf", bbox_inches="tight")
plt.close(fig)
# Use security codes as stable identifiers; retain original company names in JSON.
with (B / "event_level_matching.csv").open("w", newline="") as f:
    w = csv.DictWriter(
        f,
        fieldnames=[
            "code",
            "event_date",
            "n_week",
            "n_day",
            "car_percent",
            "week_diff_pp",
            "day_diff_pp",
        ],
    )
    w.writeheader()
    for r in D["event_rows"]:
        w.writerow(
            dict(
                code=r["code"],
                event_date=r["t0"],
                n_week=r["week_n"],
                n_day=r["day_n"],
                car_percent=r["car"],
                week_diff_pp=r["week_diff"],
                day_diff_pp=r["day_diff"],
            )
        )
print("Generated two tables, two vector figures and 28 event rows.")
