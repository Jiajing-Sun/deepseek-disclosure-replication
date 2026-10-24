"""Check freshly estimated event records against archived records before auditing.

Unlike aggregate comparisons alone, this detects changes in any event's return,
classification, matching attribute or completeness indicator.
"""

from pathlib import Path
import json
import math

ROOT = Path(__file__).resolve().parent


def equal(a, b):
    """Recursively compare data, retaining a 1e-9 tolerance for floating arithmetic."""
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(equal(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(equal(x, y) for x, y in zip(a, b))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)
    return a == b


def main():
    """Verify both event populations and save event counts for the release record."""
    report = {}
    for name in [
        "event_returns_candidate_firms.jsonl",
        "event_returns_population.jsonl",
    ]:
        baseline = [
            json.loads(line)
            for line in (ROOT / ("baseline_" + name)).read_text().splitlines()
            if line
        ]
        recomputed = [
            json.loads(line)
            for line in (ROOT / ("result_" + name)).read_text().splitlines()
            if line
        ]
        assert equal(baseline, recomputed), f"Event-level mismatch: {name}"
        report[name] = {"events_checked": len(baseline), "passed": True}
    (ROOT / "result_event_record_check.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print("Fresh event records match archived records.")


if __name__ == "__main__":
    main()
