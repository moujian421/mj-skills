#!/usr/bin/env python3
"""ABA 文件版本地预筛（免费）：从导入的周表里挑出“排名明显上升”的词，交给 Flash 清洗和西柚补数。
用法: aba_screen.py RUN [周开始日 yyyy-mm-dd，默认最新一周]
规则（config.json）：
  1 只看本周排名 <= max_search_rank（50 万）的词
  2 剔除：含 holiday_roots、含 U+FFFC 等异常字符、带 + 号拼接
  3 有去年同期周表时（推荐）：rise = 去年同周 ±ly_window 周的最好排名 / 近 avg_weeks 周排名中位数（本地排名同比，免费）。
    没有去年周表时退回：rise = 基准排名 / 本周排名，基准 = 中位数(上周排名[来自“变化名次”], 4–12 周前已导入周表里的排名)；
    某个旧周表覆盖了这个排名段但词不在里面 → 记为该表最大排名 ×2（掉出覆盖范围）；上周不在榜（“--”）= 新词，rise 记 99。
    rise >= aba_rise_min 才进候选。导入的旧周越多，越不会只看本周一周。
  4 单品垄断（第 1 名点击 >=50%）往后放，再按 rise 从高到低取前 aba_pre_cap 个（控制后面西柚的花费），其余计数不保留明细
输出 RUN/candidates.csv、RUN/screened.json、RUN/meta.json，只打印统计。
"""
import csv, gzip, json, re, statistics as st, sys
from datetime import datetime, timedelta
from pathlib import Path
SKILL = Path(__file__).resolve().parent.parent
CFG = json.loads((SKILL / "config.json").read_text(encoding="utf-8"))
ABA = SKILL / "data" / "aba"; cov = json.loads((ABA / "coverage.json").read_text())
RUN = Path(sys.argv[1]); RUN.mkdir(parents=True, exist_ok=True)
week = sys.argv[2] if len(sys.argv) > 2 else max(cov)
def load(w):
    with gzip.open(ABA / f"{w}.csv.gz", "rt", encoding="utf-8") as fh: return {r["keyword"]: r for r in csv.DictReader(fh)}
cur = load(week); T = datetime.strptime(week, "%Y-%m-%d")
W, A = CFG["ly_window"], CFG["avg_weeks"]
recent = {}
for k in range(1, A):
    w = (T - timedelta(weeks=k)).strftime("%Y-%m-%d")
    if w in cov: recent[w] = load(w)
ly = {}
for k in range(52 - W - A + 1, 52 + W + 1):
    w = (T - timedelta(weeks=k)).strftime("%Y-%m-%d")
    if w in cov: ly[w] = load(w)
old = {}
for k in range(4, 13):
    w = (T - timedelta(weeks=k)).strftime("%Y-%m-%d")
    if w in cov: old[w] = load(w)
def rank_in(w, t, kw, ref):
    """该周表里的排名；不在表里但表覆盖了 ref 这段 → 当作掉出覆盖（最大排名 ×2）；表没覆盖这段 → None"""
    if kw in t: return int(t[kw]["rank"])
    return cov[w]["max"] * 2 if cov[w]["min"] <= ref else None
TH = CFG["max_search_rank"]; keep = []; cnt = {"本周行数": len(cur), "近几周表": len(recent), "去年同期表": len(ly), "旧周表": sorted(old), "超门槛": 0, "节日词": 0, "异常字符": 0, "上升不够": 0}
for kw, r in cur.items():
    now = int(r["rank"]); low = kw.lower()
    if now > TH: cnt["超门槛"] += 1; continue
    if any(h in low for h in CFG["holiday_roots"]): cnt["节日词"] += 1; continue
    # 不可见字符、+ 号、开头/结尾是标点、和已有词只差连字符（如 RLM+blender、car air freshener -、floor-lamp）
    if re.search(r"[\ufffc\u200b-\u200f\u202a-\u202e\u2060\ufeff+]", kw) or re.search(r"[-_,.]\s*$|^\W", kw) \
            or ("-" in kw and kw.replace("-", " ") in cur):
        cnt["异常字符"] += 1; continue
    # 有去年同期周表 → 本地排名同比（免费）：近 A 周排名中位数 vs 去年同周 ±W 周最好排名
    if ly:
        nowr = [now] + [x for x in (rank_in(w, t, kw, now) for w, t in recent.items()) if x]
        lyr = [x for x in (rank_in(w, t, kw, now) for w, t in ly.items()) if x]
        rise = round(min(lyr) / st.median(nowr), 1) if lyr else 99
        if rise < CFG["aba_rise_min"]: cnt["上升不够"] += 1; continue
    else:   # 没有去年数据 → 退回看近期上升：上周排名 + 4–12 周前周表
        base = []
        if r["prev_rank"]: base.append(int(r["prev_rank"]))
        for w, t in old.items():
            x = rank_in(w, t, kw, now)
            if x: base.append(x)
        rise = 99 if (r["is_new"] == "1" and not base) else (round(st.median(base) / now, 1) if base else 0)
        if rise < CFG["aba_rise_min"]: cnt["上升不够"] += 1; continue
    t3 = float(r["top3_click"] or 0) / 100; t1 = float(r["click1"] or 0) / 100
    keep.append({"keyword": kw, "departments": r["title1"], "rank": now, "prev_rank": r["prev_rank"] or "新进榜", "rise": rise,
                 "top1_click": round(t1, 2), "monopoly": "是" if t1 >= CFG["brand_top1_click"] else "",
                 "top3_click": round(t3, 2), "concentrated": "是" if t3 >= CFG["top3_click_concentrated"] else "",
                 "top3_asin": "/".join(x for x in (r["asin1"], r["asin2"], r["asin3"]) if x)})
keep.sort(key=lambda x: (x["monopoly"] == "是", -x["rise"])); cnt["上升够的"] = len(keep)   # 单品垄断（多是品牌爆款）往后放
keep = keep[:CFG["aba_pre_cap"]]; cnt["取前"] = len(keep)
with open(RUN / "candidates.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, list(keep[0].keys())); w.writeheader(); w.writerows(keep)
json.dump({"keep": [{**k, "top3Brands": []} for k in keep], "removed": []}, open(RUN / "screened.json", "w", encoding="utf-8"), ensure_ascii=False)
json.dump({"date": week.replace("-", ""), "source": "aba_file", "screen": cnt}, open(RUN / "meta.json", "w", encoding="utf-8"), ensure_ascii=False)
print(json.dumps(cnt, ensure_ascii=False))
