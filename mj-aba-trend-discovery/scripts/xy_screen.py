#!/usr/bin/env python3
"""西柚版本地筛选：读 RUN/raw/page_*.json（xy_pull.py 拉的），按周历史判断，不再调接口。
用法: xy_screen.py RUN
输出 RUN/candidates.csv（保留）、RUN/screened.json（keep/removed + 原因）、RUN/meta.json，只打印统计。
规则（参数在 config.json）：
  1 类目：西柚根类目名含 exclude_root_substr 任一项 → 剔除；没有类目的不剔，交给 Flash 判断（新形态商品常未归类）
  2 节日词：含 holiday_roots → 剔除
  3 同比（只算不剔）：yoy = 近 4 周平均周搜索量 / 去年同周 ±ly_window 周内滚动 4 周平均的最高值（去年不在榜记 999 = 新词）；
    其中搜索量都是近 avg_weeks（4）周平均，单周跳一下不会被高估；rank_ly（去年同期最好排名）只做参考。2026-11-12 实测排名倍数和搜索量倍数判断结果一致，按用户习惯用搜索量。
    是否剔除放到 xy_core.py：关键词或核心大词任一同比 >= growth_min 才保留（用户 2026-11-12）。
  4 走势标签（不剔除）：持续上升 / 新进榜 / 单周跳升；来源标签（不剔除）：2–4 个月前在榜周排名中位数
    ≤50 万 = 一直在50万内，50–100 万 = 从50-100万涨进，否则（含在榜不足 4 周）= 从100万外冲进
  5 供给（不剔除）：前 3 ASIN 评论数中位 <100 供给早期，<1000 供给中，否则成熟
  6 单品垄断（不剔除，标记）：第 1 名 ASIN 点击占比 >= brand_top1_click；点击集中：前 3 合计 >= top3_click_concentrated
    （站外单品爆款/刷榜词常见，Argon 2026-11-12 建议）
"""
import csv, json, statistics as st, sys
from pathlib import Path
SKILL = Path(__file__).resolve().parent.parent
CFG = json.loads((SKILL / "config.json").read_text(encoding="utf-8"))
RUN = Path(sys.argv[1]); OUT_RANK = 2_500_000
rk = lambda x: x if x else OUT_RANK
med = lambda xs: int(st.median([rk(x) for x in xs])) if xs else OUT_RANK

items = {}
for f in sorted((RUN / "raw").glob("*.json")):
    for k in (json.loads(f.read_text(encoding="utf-8")).get("data") or {}).get("list") or []:
        items.setdefault(k["searchTerm"]["original"].strip(), k)
TREND_ORDER = {"持续上升": 0, "新进榜": 1, "单周跳升": 2}
keep, removed = [], []
week = None
PW = (RUN / "pull_week.txt").read_text().strip() if (RUN / "pull_week.txt").exists() else None
for kw, k in items.items():
    tr = [x for x in k["searchTermTrends"] if not PW or x["reportFromDate"] <= PW]   # 跑历史周：截掉之后的周
    if not tr: continue
    t = [x["searchFrequencyRank"] for x in tr]
    week = week or tr[-1]["reportFromDate"]
    info = k["searchTermInfo"]; aba = info.get("abaReport") or {}
    cats = k.get("categories") or []
    root = cats[0]["path"][0]["categoryName"]["original"] if cats and cats[0].get("path") else ""
    leaf = cats[0]["categoryName"]["original"] if cats else ""
    now = t[-1]; W = CFG["ly_window"]  # 去年同周 ±W 周的最好排名（Argon 2026-11-12：±2 周防不住移动节日和提前起量）
    lyw = t[-53 - W:-52 + W] if len(t) >= 53 + W else []
    ly = min([rk(x) for x in lyw]) if lyw else OUT_RANK
    # 增长看搜索量（用户 2026-11-12）：本周周搜索量 ÷ 去年同周 ±W 周最高周搜索量；去年不在榜 = 新词
    # 用户 2026-11-12：增长别只看本周一周 → 近 4 周平均 ÷ 去年同期 ±W 周内“滚动 4 周平均”的最高值
    vols = [x.get("weeklySearchVolume") or 0 for x in tr]; n = len(vols); A = CFG["avg_weeks"]
    vnow = round(sum(vols[-A:]) / A)
    roll = [sum(vols[j - A + 1:j + 1]) / A for j in range(max(A - 1, n - 53 - W), max(A - 1, n - 52 + W))]
    vly = round(max(roll)) if roll else 0
    m4, mprev = med(t[-4:]), med(t[-16:-8])
    present4 = sum(1 for x in t[-4:] if x); hist = sum(1 for x in t[-26:-4] if x)
    trend = "持续上升" if present4 >= 3 and mprev / m4 >= 2 else ("新进榜" if hist <= 2 else "单周跳升")
    # 从哪里涨进来（用户 2026-11-13：保留全部，只加标签）：2–4 个月前（第 9–16 周前）在榜周的排名中位数
    pv = [x for x in t[-16:-8] if x]
    pm = st.median(pv) if len(pv) >= 4 else None
    origin = ("一直在50万内" if pm and pm <= CFG["max_search_rank"] else
              "从50-100万涨进" if pm and pm <= 1_000_000 else "从100万外冲进")
    top = (aba.get("topAsins") or {}).get("asins") or []
    rats = [a.get("ratings") or 0 for a in top]
    rmed = st.median(rats) if rats else None
    supply = "未知" if rmed is None else ("供给早期" if rmed < 100 else "供给中" if rmed < 1000 else "供给成熟")
    top1 = float(top[0].get("clickShare") or 0) if top else 0
    top3 = sum(float(a.get("clickShare") or 0) for a in top)
    row = {"keyword": kw, "departments": f"{root} > {leaf}" if root else "", "rank": now, "rank_ly": ly,
           "vol_week": vols[-1], "vol": vnow, "vol_ly": vly, "vol_add": vnow - vly,
           "yoy": round(vnow / vly, 1) if vly else 999, "m4": m4, "m_prev": mprev, "trend": trend, "origin": origin,
           "weekly_volume": (aba.get("weeklySearchVolume") or {}).get("value"),
           "cvr": info.get("adjustedClickConversionRate"), "cpc": (info.get("cpc") or {}).get("value"),
           "top1_click": round(top1, 2), "monopoly": "是" if top1 >= CFG["brand_top1_click"] else "",
           "top3_click": round(top3, 2), "concentrated": "是" if top3 >= CFG["top3_click_concentrated"] else "",
           "top3_ratings": "/".join(str(r) for r in rats), "supply": supply,
           "top3_price": "/".join(str(a.get("price")) for a in top), "top3_asin": "/".join(a.get("asin", "") for a in top)}
    low = kw.lower(); why = None
    if "￼" in kw: why = "异常字符变体"
    elif root and any(s.lower() in root.lower() for s in CFG["exclude_root_substr"]): why = f"类目剔除:{root}"
    elif any(h in low for h in CFG["holiday_roots"]): why = "节日词"
    if why: row["why"] = why; removed.append(row)
    else: keep.append(row)
keep.sort(key=lambda r: (TREND_ORDER[r["trend"]], -r["yoy"]))
cols = [c for c in keep[0].keys()] if keep else ["keyword"]
with open(RUN / "candidates.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, cols); w.writeheader(); w.writerows(keep)
for r in keep: r["top3Brands"] = []
json.dump({"keep": keep, "removed": removed}, open(RUN / "screened.json", "w", encoding="utf-8"), ensure_ascii=False)
json.dump({"date": week.replace("-", ""), "source": "xiyou"}, open(RUN / "meta.json", "w", encoding="utf-8"), ensure_ascii=False)
from collections import Counter
print(json.dumps({"周": week, "拉到": len(items), "保留": len(keep), "走势": Counter(r["trend"] for r in keep), "来源": Counter(r["origin"] for r in keep),
                  "供给": Counter(r["supply"] for r in keep),
                  "剔除": Counter(r["why"].split(":")[0].split("（")[0] if not r["why"].startswith("去年") else "去年同期" for r in removed)},
                 ensure_ascii=False))
