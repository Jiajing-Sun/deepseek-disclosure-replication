"""Independently reconstruct article aggregates from the 28 public event rows.

These checks establish internal numerical consistency of the released derived data.
They do not re-estimate returns from prices or validate document coding.
"""

from pathlib import Path
import json
from statistics import mean, stdev
from scipy.stats import t

ROOT = Path(__file__).resolve().parent


def interval(values, dates):
    """Compute CR1 event-equal and t-based date-equal intervals without stats_util."""
    n = len(values)
    unique = sorted(set(dates))
    groups = [[v for v, d in zip(values, dates) if d == day] for day in unique]
    g = len(groups)
    average = mean(values)
    variance = (
        g / (g - 1) * sum(sum(v - average for v in row) ** 2 for row in groups) / n**2
    )
    critical = t.ppf(0.975, g - 1)
    daily = [mean(row) for row in groups]
    date_mean = mean(daily)
    date_se = stdev(daily) / g**0.5
    return [
        average,
        average - critical * variance**0.5,
        average + critical * variance**0.5,
        date_mean,
        date_mean - critical * date_se,
        date_mean + critical * date_se,
    ]


def main():
    """Check counts, matching summaries, confidence intervals and history accounting."""
    data = json.loads((ROOT / "article_data.json").read_text())
    evidence = json.loads((ROOT / "content_evidence.json").read_text())
    history = json.loads((ROOT / "historical_evidence.json").read_text())
    rows = data["event_rows"]
    dates = [row["t0"] for row in rows]
    assert len(rows) == 28 and len(set(dates)) == 12
    assert len({(row["code"], row["t0"]) for row in rows}) == 28
    checks = [("car", data["core"], "mean", "ci", "date_mean", "date_ci")]
    checks += [
        (
            key + "_diff",
            data["comparisons"][key],
            "mean_pp",
            "ci_pp",
            "date_mean_pp",
            "date_ci_pp",
        )
        for key in ["week", "day"]
    ]
    for column, source, m, ci, dm, dci in checks:
        actual = interval([row[column] for row in rows], dates)
        expected = [source[m], *source[ci], source[dm], *source[dci]]
        assert all(abs(a - b) < 1e-9 for a, b in zip(actual, expected)), column
    for rule in ["week", "day"]:
        assert sorted(row[rule + "_n"] for row in rows) == sorted(
            data["comparisons"][rule]["pool_sizes"]
        )
    combinations = evidence["adoption_by_denied_dimension"]
    assert sum(row["total"] for row in combinations) == evidence["c1_documents"] == 38
    for row in combinations:
        assert row["commercial_only"] + row["equity_only"] + row["both"] == row["total"]
    assert combinations[0]["total"] == 18
    assert sum(evidence["attention_reference_types"].values()) == 38
    assert evidence["attention_reference_types"]["classification"] == 23
    assert len(history) == len(evidence["history_timing"]) == 9
    assert sum(h["classification"] == "Restatement" for h in history) == 5
    assert sum(h["classification"] == "Scope update" for h in history) == 4
    gaps = sorted(h["sessions_before_event"] for h in evidence["history_timing"])
    assert gaps[4] == evidence["history_gap_median"] == 3
    assert sum(g <= 20 for g in gaps) == evidence["history_gap_within_20"] == 8
    role = evidence["roles"]["T1"]
    assert abs(role["ar0"] + role["car12"] - role["car02"]) < 1e-9
    assert abs(role["car02"] - data["core"]["mean"]) < 1e-9
    (ROOT / "result_snapshot_check.json").write_text(
        json.dumps(
            {
                "passed": True,
                "events": 28,
                "dates": 12,
                "history_cases": 9,
                "checked": [
                    "event/date means and intervals",
                    "matched pool sizes",
                    "content-count identities",
                    "history counts",
                    "AR window decomposition",
                ],
            },
            indent=2,
        )
        + "\n"
    )
    print("Public snapshot numerical checks passed.")


if __name__ == "__main__":
    main()
