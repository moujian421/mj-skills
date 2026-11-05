#!/usr/bin/env python3
"""建或校准标签库时用：按 星级 × 变体 × 时间 分层抽样，写成一份短文本给 Claude 读。

用法:
    python3 sample_for_taxonomy.py WORK [--n 90] [--asof 2026-10-30] [--stars 4,5]

每个星级大致等量抽（--stars 可只抽某几个星级，如校准正面标签时只抽 4,5），
星级内部再按变体、近 12 个月 / 更早轮流抽，每条正文截到 400 字符。
输出 WORK/taxonomy_sample.txt，只打印条数。
"""
import argparse
import json
import random
from collections import defaultdict
from datetime import date, timedelta
from itertools import cycle
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("--n", type=int, default=90)
    ap.add_argument("--asof", default=date.today().isoformat())
    ap.add_argument("--stars", default="1,2,3,4,5")
    a = ap.parse_args()
    work = Path(a.work)
    stars = [int(s) for s in a.stars.split(",")]
    cut = (date.fromisoformat(a.asof) - timedelta(days=365)).isoformat()
    rows = [json.loads(l) for l in open(work / "reviews.jsonl")]
    rows = [r for r in rows if r["star"] in stars and len(r["content"]) > 40]
    random.seed(1)
    picked = []
    per_star = a.n // len(stars)
    for s in stars:
        cells = defaultdict(list)
        for r in rows:
            if r["star"] == s:
                cells[(r["variant"], r["date"] >= cut)].append(r)
        for v in cells.values():
            random.shuffle(v)
        got = []
        keys = list(cells)
        random.shuffle(keys)
        for k in cycle(keys or [None]):
            if len(got) >= per_star or not any(cells.values()):
                break
            if k is not None and cells[k]:
                got.append(cells[k].pop())
        picked += got
    with open(work / "taxonomy_sample.txt", "w") as f:
        for r in picked:
            f.write(f"{r['id']} [{r['star']}星] {r['variant'][:40]} {r['date']}\n"
                    f"  {r['title']} | {r['content'][:400]}\n")
    print(f"抽样 {len(picked)} 条 → {work / 'taxonomy_sample.txt'}")


if __name__ == "__main__":
    main()
