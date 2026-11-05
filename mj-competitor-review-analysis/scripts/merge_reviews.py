#!/usr/bin/env python3
"""合并翻页结果、去重、核对条数，生成打标输入。只打印统计，不打印评论内容。

用法:
    python3 merge_reviews.py WORK --probe-dir WORK/pull_probe PULL_DIR [PULL_DIR ...]

PULL_DIR 是 oc_pull.sh 的输出目录（里面有 raw/index.json）。补拉过的目录一起传进来，重复的页会去重。
输出:
    WORK/reviews.jsonl     一行一条评论：id, asin, star, date, variant, verified, vine, image, video, likes, title, content
    WORK/tag_input.tsv     id<TAB>[N星] 标题 | 正文（打标用）
    WORK/missing_calls.txt 漏掉的页（直接当清单交给 oc_pull.sh 补拉）；没有漏页就不生成
"""
import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from make_calls import FIELDS, PAGE_SIZE, call  # noqa: E402


def clean(s):
    return " ".join(str(s or "").replace("\t", " ").split())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("pull_dirs", nargs="+")
    ap.add_argument("--probe-dir", required=True)
    ap.add_argument("--site", default="US")
    a = ap.parse_args()
    work = Path(a.work)
    expected = json.loads((Path(a.probe_dir) / "expected.json").read_text())

    seen_pages = defaultdict(set)
    rows, keys, dup = [], set(), 0
    errors = []
    for d in map(Path, a.pull_dirs):
        for x in json.loads((d / "raw" / "index.json").read_text()):
            if x["tool"] != "review":
                continue
            args = x["args"]
            if x.get("error"):
                errors.append(args)
                continue
            asin, star, page = args["asin"], args["starList"][0], args["page"]
            seen_pages[(asin, star)].add(page)
            data = json.loads((d / "raw" / x["file"]).read_text()).get("data") or {}
            for it in data.get("items") or []:
                k = hashlib.md5("|".join([asin, str(it.get("author")), str(it.get("date")),
                                          clean(it.get("title"))[:60], clean(it.get("content"))[:200]])
                                .encode()).hexdigest()
                if k in keys:
                    dup += 1
                    continue
                keys.add(k)
                ts = it.get("date")
                rows.append({
                    "asin": asin,
                    "star": it.get("star") if it.get("star") is not None else star,
                    "star_missing": it.get("star") is None,
                    "date": datetime.fromtimestamp(ts / 1000, timezone.utc).strftime("%Y-%m-%d") if ts else "",
                    "variant": " / ".join(it.get("skus") or []),
                    "verified": bool(it.get("verified")), "vine": bool(it.get("vine")),
                    "image": bool(it.get("image")), "video": bool(it.get("video")),
                    "likes": it.get("likes") or 0,
                    "title": clean(it.get("title")), "content": clean(it.get("content")),
                })

    rows.sort(key=lambda r: (r["asin"], r["date"]))
    for i, r in enumerate(rows, 1):
        r["id"] = f"R{i:05d}"
    with open(work / "reviews.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(work / "tag_input.tsv", "w") as f:
        for r in rows:
            text = f"[{r['star']}星] {r['title']} | {r['content']}"
            f.write(f"{r['id']}\t{text[:2000]}\n")

    # 核对：每个 ASIN × 星级，拿到的条数 vs 探数总数；漏页写成补拉清单
    got = Counter((r["asin"], str(r["star"])) for r in rows)
    missing_calls, check = [], []
    for asin, stars in expected.items():
        for star, total in stars.items():
            need = set(range(1, (total + PAGE_SIZE - 1) // PAGE_SIZE + 1))
            lost = sorted(need - seen_pages[(asin, int(star))])
            missing_calls += [call(a.site, asin, p, PAGE_SIZE, int(star), FIELDS) for p in lost]
            n = got[(asin, star)]
            if lost or n < total * 0.97:
                check.append(f"{asin} {star}星：应有 {total}，拿到 {n}，漏页 {lost[:10]}{'…' if len(lost) > 10 else ''}")
    if missing_calls:
        (work / "missing_calls.txt").write_text("\n".join(missing_calls) + "\n")

    per_asin = Counter(r["asin"] for r in rows)
    summary = {
        "reviews": len(rows), "duplicates_removed": dup, "error_calls": len(errors),
        "per_asin": dict(per_asin),
        "per_star": dict(sorted(Counter(str(r["star"]) for r in rows).items())),
        "star_missing": sum(r["star_missing"] for r in rows),
        "empty_content": sum(1 for r in rows if not r["content"]),
        "vine": sum(r["vine"] for r in rows), "verified": sum(r["verified"] for r in rows),
        "date_range": [min(r["date"] for r in rows if r["date"]), max(r["date"] for r in rows if r["date"])] if any(r["date"] for r in rows) else [],
        "shortfall": check, "missing_calls": len(missing_calls),
    }
    (work / "merge_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
