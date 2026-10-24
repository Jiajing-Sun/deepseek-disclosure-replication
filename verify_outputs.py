"""Compare recomputed analysis with the archived numerical baseline.
Floating-point tolerance is 1e-9. This checks numerical replication, not human coding validation.
"""

from pathlib import Path
import json, math

B = Path(__file__).resolve().parent


def walk(a, b, p=""):
    """Recursively compare nested results, allowing 1e-9 relative and absolute floating tolerance."""
    if isinstance(a, dict) and isinstance(b, dict):
        for k in set(a) | set(b):
            if k not in a or k not in b:
                yield p + "/" + k, "missing"
            else:
                yield from walk(a[k], b[k], p + "/" + k)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            yield p, "length"
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                yield from walk(x, y, p + "/" + str(i))
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if not math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9):
            yield p, [a, b]
    elif a != b:
        yield p, [a, b]


report = {}
for name in ["main_results.json", "content_tables.json"]:
    a = json.loads((B / ("baseline_" + name)).read_text())
    b = json.loads((B / ("result_" + name)).read_text())
    report[name] = list(walk(a, b))
(B / "result_reproduction_check.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2)
)
print(
    "Main-result differences:",
    len(report["main_results.json"]),
    "Content differences:",
    len(report["content_tables.json"]),
)
# The corrected midnight cutoff is checked against its own reference values.
a = json.loads((B / "result_supplementary.json").read_text())
assert abs(a["week_exclude_prior_qa"]["mean_pp"] - 8.861828084577494) < 1e-8
assert abs(a["day_exclude_prior_qa"]["mean_pp"] - 4.392324292269812) < 1e-8
assert not report["main_results.json"], report["main_results.json"][:5]
assert not report["content_tables.json"], report["content_tables.json"][:5]
