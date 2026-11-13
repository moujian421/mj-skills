#!/usr/bin/env python3
"""把卖家后台下载的 ABA 热门搜索词周报 xlsx 导入成本地周表（免费，不花 Credits）。
用法: aba_import.py FILE.xlsx [FILE.xlsx ...]
- 完整导入：报表里每一列都保留（国家/报告周期/日期这几列每行都一样，只存在文件名和 coverage.json 里）。
  用户 2026-11-13 要求存完整报表，并随 skill 推到 GitHub，别人安装 skill 时一起下载。
- 按文件里的“开始日期”归周；同一周多个文件（不同排名段）自动合并去重。
- 输出 data/aba/<开始日期>.csv.gz 和 data/aba/coverage.json（每周覆盖的排名范围和行数）。
- “排名变化/变化名次”是和上一周比：上升 → 上周排名 = 本周 + 变化名次；下降 → 本周 - |变化名次|；“--” = 上周不在榜（新词）。
  原始的“排名变化”“变化名次”也原样保留在 rank_change、rank_change_n 两列。
"""
import csv, gzip, json, sys, warnings
from pathlib import Path
import openpyxl
warnings.filterwarnings("ignore")
SKILL = Path(__file__).resolve().parent.parent
OUT = SKILL / "data" / "aba"; OUT.mkdir(parents=True, exist_ok=True)
# 列名 -> 报表原列名（None = 计算列）
MAP = [("keyword", "搜索词"), ("rank", "搜索量排名"), ("prev_rank", None), ("is_new", None),
       ("rank_change", "排名变化"), ("rank_change_n", "变化名次"),
       ("top3_click", "最新前三商品总点击份额"), ("top3_conv", "最新前三商品总转化份额")]
for n in (1, 2, 3):
    MAP += [(f"asin{n}", f"#{n} 商品"), (f"title{n}", f"#{n} 商品标题"), (f"click{n}", f"#{n} 商品点击份额"), (f"conv{n}", f"#{n} 商品转化份额")]
COLS = [c for c, _ in MAP]
cov_f = OUT / "coverage.json"; cov = json.loads(cov_f.read_text(encoding="utf-8")) if cov_f.exists() else {}
for f in sys.argv[1:]:
    ws = openpyxl.load_workbook(f, read_only=True).worksheets[0]
    it = ws.iter_rows(values_only=True); h = list(next(it)); ix = {k: i for i, k in enumerate(h)}
    need = ["搜索词", "开始日期", "搜索量排名", "排名变化", "变化名次"]
    miss = [k for k in need if k not in ix]
    if miss: print(f"{f}: 缺列 {miss}，跳过"); continue
    extra = [k for k in h if k not in {src for _, src in MAP} | {"国家", "报告周期", "开始日期", "结束日期"}]
    if extra: print(f"{Path(f).name}: 报表有新列 {extra}，没存，需要在 aba_import.py 的 MAP 里加上")
    g = lambda row, k: row[ix[k]] if k in ix else None
    rows = {}; week = None
    for row in it:
        kw = str(g(row, "搜索词") or "").strip()
        if not kw or g(row, "搜索量排名") is None: continue
        week = week or str(g(row, "开始日期"))[:10]
        r = int(g(row, "搜索量排名")); ch = g(row, "排名变化"); v = g(row, "变化名次")
        d = abs(int(float(v))) if isinstance(v, (int, float)) else 0
        prev = "" if ch == "--" else (r + d if ch == "上升" else r - d if ch == "下降" else r)
        rec = {"keyword": kw, "rank": r, "prev_rank": prev, "is_new": 1 if ch == "--" else 0}
        for c, src in MAP:
            if src and c not in rec:
                x = g(row, src); rec[c] = "" if x is None else x
        rows[kw] = [rec[c] for c in COLS]
    if not week: print(f"{f}: 没有数据"); continue
    wf = OUT / f"{week}.csv.gz"
    if wf.exists():   # 合并同一周的其他排名段
        with gzip.open(wf, "rt", encoding="utf-8") as fh:
            for r0 in csv.DictReader(fh):
                if r0["keyword"] not in rows: rows[r0["keyword"]] = [r0.get(c, "") for c in COLS]
    with gzip.open(wf, "wt", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh); w.writerow(COLS); w.writerows(rows.values())
    rk = [int(r[1]) for r in rows.values()]
    cov[week] = {"min": min(rk), "max": max(rk), "rows": len(rk)}
    print(f"{Path(f).name}: 周 {week}，合并后 {len(rk)} 行，排名 {min(rk)}–{max(rk)}", flush=True)
cov_f.write_text(json.dumps(dict(sorted(cov.items())), ensure_ascii=False, indent=1), encoding="utf-8")
