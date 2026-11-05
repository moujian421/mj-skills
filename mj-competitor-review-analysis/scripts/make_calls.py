#!/usr/bin/env python3
"""生成卖家精灵 review 的调用清单，交给 batch-offload 的 oc_pull.sh 去拉。

两步：
  1) 探总数：每个 ASIN × 每个星级调一次（size=1，只返回 star），拿到各星级的文字评论总数
     python3 make_calls.py probe --site US --asin B07YN1W5W3 [--asin ...] > WORK/calls_probe.txt
  2) 翻页：读第 1 步的落盘结果，按星级翻页（每页 20 条，接口上限）
     python3 make_calls.py pages --site US --probe-dir WORK/pull_probe > WORK/calls_pages.txt

按星级分开翻页有两个好处：每个星级的页数更少，不容易碰到接口的翻页上限；
拉完能逐星级核对条数。--max-pages 是单个星级最多翻几页的保护上限。
"""
import argparse
import json
import sys
from pathlib import Path

PAGE_SIZE = 20  # 卖家精灵 review 每页最多返回 20 条（2026-10-30 实测，传 200 也只给 20）
FIELDS = "author,title,content,date,star,skus,verified,vine,image,video,likes"


def call(site, asin, page, size, star, fields):
    args = {"marketplace": site, "asin": asin, "page": page, "size": size,
            "starList": [star], "returnFields": fields}
    return 'tools["sellersprite-mcp"]["review"](' + json.dumps(args, ensure_ascii=False) + ')'


def probe(a):
    for asin in a.asin:
        for star in range(1, 6):
            print(call(a.site, asin.strip().upper(), 1, 1, star, "star"))


def pages(a):
    d = Path(a.probe_dir)
    index = json.loads((d / "raw" / "index.json").read_text())
    plan = []
    for x in index:
        if x["tool"] != "review":
            continue
        args = x["args"]
        if x.get("error"):
            print(f"探数失败，先重跑：{args}", file=sys.stderr)
            continue
        data = json.loads((d / "raw" / x["file"]).read_text()).get("data") or {}
        total = int(data.get("total") or 0)
        n = min((total + PAGE_SIZE - 1) // PAGE_SIZE, a.max_pages)
        if total > a.max_pages * PAGE_SIZE:
            print(f"{args['asin']} {args['starList'][0]}星 共 {total} 条，超过 {a.max_pages} 页上限，"
                  f"只拉前 {a.max_pages * PAGE_SIZE} 条（最新的）", file=sys.stderr)
        plan.append((args["asin"], args["starList"][0], total, n))
    for asin, star, total, n in sorted(plan):
        for p in range(1, n + 1):
            print(call(a.site, asin, p, PAGE_SIZE, star, FIELDS))
    # 探数汇总写一份，merge_reviews.py 用来核对条数
    expected = {}
    for asin, star, total, n in plan:
        expected.setdefault(asin, {})[str(star)] = total
    (d / "expected.json").write_text(json.dumps(expected, ensure_ascii=False, indent=1))
    calls = sum(n for *_, n in plan)
    print(f"共 {len(expected)} 个 ASIN，{sum(t for _, _, t, _ in plan)} 条文字评论，{calls} 个翻页调用",
          file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("probe")
    p1.add_argument("--site", default="US")
    p1.add_argument("--asin", action="append", required=True)
    p2 = sub.add_parser("pages")
    p2.add_argument("--site", default="US")
    p2.add_argument("--probe-dir", required=True)
    p2.add_argument("--max-pages", type=int, default=150)
    a = ap.parse_args()
    probe(a) if a.cmd == "probe" else pages(a)


if __name__ == "__main__":
    main()
