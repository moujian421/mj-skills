"""Fill templates/report.html with a report data JSON and write a publishable HTML page.

Usage: python3 -I build_report.py <data.json> <out.html>

Prints the visible character count (excluding chart arrays) and warns above 20,000.
"""
import html
import json
import sys
from pathlib import Path

LIMIT = 20000
TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "report.html"


def visible_chars(node, key=None):
    if key in ("dates", "bsr", "price", "id", "window", "d0"):
        return 0
    if isinstance(node, str):
        return len(node)
    if isinstance(node, list):
        return sum(visible_chars(v) for v in node)
    if isinstance(node, dict):
        return sum(visible_chars(v, k) for k, v in node.items())
    return 0


def main(src, out):
    data = json.loads(Path(src).read_text(encoding="utf-8"))
    for field in ("title", "meta", "sections"):
        if field not in data:
            sys.exit(f"missing field: {field}")
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    page = TEMPLATE.read_text(encoding="utf-8")
    page = page.replace("__PAGE_TITLE__", html.escape(data["title"]))
    page = page.replace("/*__REPORT_DATA__*/null", payload)
    Path(out).write_text(page, encoding="utf-8")
    n = visible_chars({k: v for k, v in data.items() if k != "chart"}) + visible_chars(
        [e.get("label", "") for e in data.get("chart", {}).get("events", [])]
    )
    print(f"wrote {out}; visible characters: {n}")
    if n > LIMIT:
        print(f"WARNING: over the {LIMIT} character limit, trim before publishing")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
