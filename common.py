"""Shared file, identifier, exchange-calendar and date-parsing helpers.
All analysis paths resolve to the flat staging directory created by run_all.py.
Inputs are read-only; regenerated analysis outputs use the result_ prefix."""

from pathlib import Path
import json, re, hashlib, datetime

# All analysis inputs and outputs share one flat staging directory.
# The result_ prefix identifies new outputs; baseline_ identifies archived checks.
CA = Path(__file__).resolve().parent
RESEARCH = DATA = OUT_DATA = RESULTS = FIGURES = CA


def read_jsonl(path):
    """Read nonblank JSON Lines records in their original order."""
    return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]


def write_jsonl(path, rows):
    """Write derived JSON Lines with a result_ prefix, preserving the input file."""
    Path(path).with_name("result_" + Path(path).name).write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    )


def write_json(path, obj):
    """Write a derived JSON object with a result_ prefix."""
    Path(path).with_name("result_" + Path(path).name).write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n"
    )


def sha256_file(path):
    """Return a SHA-256 digest for provenance checks."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def symbol_of(code):
    """Map a six-digit security code to its exchange-prefixed price identifier."""
    return ("sh" if code.startswith("6") else "sz") + code


def board_of(code):
    """Classify the sample-period exchange board from the security-code prefix."""
    if code.startswith("688"):
        return "SSE_STAR"
    if code.startswith("6"):
        return "SSE_main"
    if code.startswith(("300", "301")):
        return "SZSE_ChiNext"
    return "SZSE_main"


def doc_pages(aid):
    """Load extracted announcement pages for a supplied announcement identifier."""
    return json.loads((DATA / "announcement_text_pages.json").read_text())[str(aid)]


def compact(text):
    """Remove all whitespace. PDF extraction inserts spaces/newlines inside words and dates."""
    return re.sub(r"\s+", "", text)


def trading_calendar():
    """Trading days from the Tencent CSI All Share (sh000985) series, 2024-01-02..2025-04-30.

    The index trades on every SSE/SZSE trading day, so this is used as the exchange calendar.
    """
    rows = [
        r
        for r in read_jsonl(DATA / "daily_prices.jsonl")
        if r["symbol"] == "sh000985" and r["adjustment_requested"] == "raw"
    ]
    cal = sorted(r["date"] for r in rows)
    assert len(cal) == len(set(cal))
    return cal


DATE_RE = re.compile(
    r"(?:(20\d{2})年)?(\d{1,2})月(\d{1,2})日|(?<=[、，,和及至与])(\d{1,2})日"
)


def parse_dates(s, default_year=2025):
    """Return position, ISO date and explicit-year flag for Chinese date expressions.
    Year and month carry forward within lists; invalid calendar dates are ignored."""
    out = []
    year, month = None, None
    for m in DATE_RE.finditer(s):
        if m.group(2):
            if m.group(1):
                year = int(m.group(1))
            month, day = int(m.group(2)), int(m.group(3))
        else:
            if month is None:
                continue
            day = int(m.group(4))
        yy = year if year else default_year
        try:
            out.append(
                (m.start(), datetime.date(yy, month, day).isoformat(), bool(year))
            )
        except ValueError:
            pass
    return out


CN_DIGIT = {
    "〇": 0,
    "○": 0,
    "О": 0,
    "零": 0,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


def _cn_small(s):
    """Convert a Chinese integer from one through thirty-one to an integer."""
    if "十" in s:
        a, _, b = s.partition("十")
        return (CN_DIGIT[a] if a else 1) * 10 + (CN_DIGIT[b] if b else 0)
    return CN_DIGIT[s]


CN_DATE_RE = re.compile(
    r"([〇○О零一二三四五六七八九]{4})年([一二三四五六七八九十]{1,3})月([一二三四五六七八九十]{1,3})日"
)


def cn_dates(s):
    """Parse dates written with Chinese numerals, ignoring invalid dates."""
    out = []
    for m in CN_DATE_RE.finditer(s):
        try:
            y = int("".join(str(CN_DIGIT[c]) for c in m.group(1)))
            out.append(
                (
                    m.start(),
                    datetime.date(
                        y, _cn_small(m.group(2)), _cn_small(m.group(3))
                    ).isoformat(),
                )
            )
        except (KeyError, ValueError):
            pass
    return out
