#!/usr/bin/env python3
"""ABA 文件版：给 Flash 清洗后的候选词补西柚周搜索量（只查候选词，很便宜），算 4 周平均同比和走势。
用法: aba_enrich.py RUN
- get_keyword_aba_trends：近 12 周 + 去年同周 ±ly_window 周（多查 avg_weeks-1 周算滚动平均），每 100 个词 2 次调用，
  约 20 个词·周 1 Credit → 每个词约 1.5 Credits。按关键词缓存在 RUN/aba_hist.json，重跑不重复扣费。
- 输出覆盖 RUN/candidates_clean.csv（原表备份为 candidates_clean_pre.csv），列和西柚拉数版一致，接着跑 xy_core.py。
"""
import csv, json, shutil, statistics as st, sys
from datetime import datetime, timedelta
from pathlib import Path
HERE = Path(__file__).resolve().parent; SKILL = HERE.parent
sys.path.insert(0, str(Path.home() / ".claude/skills/mj-category-cpc/scripts"))
from mcp_call import Client
CFG = json.loads((SKILL / "config.json").read_text(encoding="utf-8"))
RUN = Path(sys.argv[1]); W, A, OUT = CFG["ly_window"], CFG["avg_weeks"], 2_500_000
pre = RUN / "candidates_clean_pre.csv"
if not pre.exists(): shutil.copy(RUN / "candidates_clean.csv", pre)
rows = list(csv.DictReader(open(pre, encoding="utf-8")))
week = json.loads((RUN / "meta.json").read_text(encoding="utf-8"))["date"]; T = datetime.strptime(week, "%Y%m%d")
wl = lambda s, n: [(s + timedelta(weeks=i)).strftime("%Y-%m-%d") for i in range(n)]
rec_s = T - timedelta(weeks=11); rec_w = wl(rec_s, 12)
ly_s = T - timedelta(weeks=52 + W + A - 1); ly_w = wl(ly_s, 2 * W + A)
hf = RUN / "aba_hist.json"; hist = json.loads(hf.read_text(encoding="utf-8")) if hf.exists() else {}
need = [r["keyword"] for r in rows if r["keyword"] not in hist]
cost = 0
if need:
    c = Client(CFG["xiyou_server"])
    def q(kws, s, e, why):
        global cost
        r = c.call("get_keyword_aba_trends", {"country": CFG["marketplace"], "keywords": kws, "start_week": s.strftime("%Y-%m-%d"),
                   "end_week": e.strftime("%Y-%m-%d"), "user_task": CFG["user_task"], "intent_summary": why})
        cost += r.get("cost_credits") or 0
        d = r.get("data") or {}
        if not isinstance(d, dict) or "entities" not in d: print("西柚异常:", str(r)[:300]); return None
        return {(e.get("searchTerm") or "").strip().lower(): {w["reportFromDate"]: [w.get("searchFrequencyRank"), w.get("weeklySearchVolume") or 0]
                for w in e.get("trends") or [] if w.get("searchFrequencyRank")} for e in d["entities"]}
    for i in range(0, len(need), 100):
        b = need[i:i+100]
        a = q(b, rec_s, T, "查 ABA 文件筛出的候选词近 12 周搜索量，算 4 周平均和走势")
        l = q(b, ly_s, T - timedelta(weeks=52 - W), "查候选词去年同期搜索量，判断是不是季节词、算同比")
        if a is None or l is None: continue
        for kw in b: hist[kw] = {**l.get(kw.lower(), {}), **a.get(kw.lower(), {})}
        hf.write_text(json.dumps(hist, ensure_ascii=False), encoding="utf-8")
out = []
for r in rows:
    h = hist.get(r["keyword"])
    if h is None: continue
    rk = lambda d: (h.get(d) or [None])[0]; vo = lambda d: (h.get(d) or [0, 0])[1]
    vols = [vo(d) for d in rec_w]; ranks = [rk(d) for d in rec_w]
    vnow = round(sum(vols[-A:]) / A); lv = [vo(d) for d in ly_w]
    vly = round(max([sum(lv[j - A + 1:j + 1]) / A for j in range(A - 1, len(lv))] or [0]))
    lyr = [rk(d) for d in ly_w[A - 1:] if rk(d)]
    m4 = int(st.median([x or OUT for x in ranks[-4:]])); mp = int(st.median([x or OUT for x in ranks[:4]]))
    present4 = sum(1 for x in ranks[-4:] if x); histn = sum(1 for x in ranks[:-4] if x)
    trend = "持续上升" if present4 >= 3 and mp / m4 >= 2 else ("新进榜" if histn <= 2 else "单周跳升")
    r.update({"vol_week": vols[-1], "vol": vnow, "vol_ly": vly, "vol_add": vnow - vly, "yoy": round(vnow / vly, 1) if vly else 999,
              "rank_ly": min(lyr) if lyr else OUT, "m4": m4, "m_prev": mp, "trend": trend, "supply": "未知", "top3_ratings": "",
              "top3_price": "", "weekly_volume": vols[-1], "cvr": "", "cpc": ""})
    out.append(r)
cols = list(out[0].keys()) if out else ["keyword"]
with open(RUN / "candidates_clean.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, cols); w.writeheader(); w.writerows(out)
from collections import Counter
print(json.dumps({"候选": len(rows), "补到": len(out), "新查": len(need), "西柚扣费": cost,
                  "4周平均同比>=2": sum(1 for r in out if r["yoy"] >= CFG["growth_min"]), "走势": Counter(r["trend"] for r in out)}, ensure_ascii=False))
