#!/usr/bin/env python3
"""西柚 find_keyword_opportunities 直连拉数（不经过 LLM、不用卖家精灵）。
用法: xy_pull.py RUN [--week=2026-10-25] [--scale=0.5] [--server=xydc-mcp]
--week 把某个历史 ABA 周（周日开始）当成“本周”拉（西柚 cycleFilter），扣费和最新周一样。
按 config.rank_bands 分段拉：每段 [ABA 最小, 最大, 词数]，段内按默认“周搜索量增长得分”降序，每页 50。
为什么分段：不分段时前 50 个词全在 5.6 万名内（2026-11-12 实测），5–50 万段几乎拉不到，新兴词恰恰多在这段。
--scale 按比例缩小每段词数（试跑用）。原始返回落盘 RUN/raw/b<段>_p<页>.json，只打印统计。每词 10 Credits。
"""
import json, sys, time
from pathlib import Path
SKILL = Path(__file__).resolve().parent.parent
CFG = json.loads((SKILL / "config.json").read_text(encoding="utf-8"))
sys.path.insert(0, str(Path.home() / ".claude/skills/mj-category-cpc/scripts"))
from mcp_call import Client

opt = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--"))
run = Path([a for a in sys.argv[1:] if not a.startswith("--")][0])
server = opt.get("server", CFG["xiyou_server"]); scale = float(opt.get("scale", 1))
WEEK = opt.get("week")   # 历史周（ABA 周的周日 yyyy-mm-dd），把那一周当成“本周”跑；不给 = 西柚最新一周
from datetime import datetime, timedelta
cyc = {"cycleFilter": {"cycle": "weekly", "startDate": WEEK,
       "endDate": (datetime.strptime(WEEK, "%Y-%m-%d") + timedelta(days=6)).strftime("%Y-%m-%d")}} if WEEK else {}
(run / "raw").mkdir(parents=True, exist_ok=True)
c = None; cost = 0; summary = []
for bi, (lo, hi, n) in enumerate(CFG["rank_bands"]):
    n = max(1, int(n * scale)); got = 0; total = None
    base = {"country": CFG["marketplace"], "rangeFilters": {"searchFrequencyRank": [{"min": str(lo), "max": str(hi)}]},
            **cyc, "user_task": CFG["user_task"], "intent_summary": f"拉 ABA {lo}-{hi} 名里增长得分靠前的关键词及其全部周历史，用于本地判断新兴、季节性"}
    # 页大小必须整段固定：西柚按 page×pageSize 定位，末页改小会重复拉前面的词（2026-11-12 踩坑，白扣 500 Credits）
    size = max(d for d in range(1, 51) if n % d == 0)
    p = 0
    while got < n:
        p += 1
        out = run / "raw" / f"b{bi}_p{p:02d}.json"
        if out.exists():
            r = json.loads(out.read_text(encoding="utf-8"))
        else:
            c = c or Client(server)
            for attempt in range(3):
                try:
                    r = c.call("find_keyword_opportunities", {**base, "page": p, "pageSize": size}); break
                except Exception as e:
                    r = {"_err": str(e)}; time.sleep(5)
            out.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
            cost += r.get("cost_credits") or 0
        lst = ((r.get("data") or {}).get("list")) or []
        total = (r.get("data") or {}).get("total", total); got += len(lst)
        if not lst:
            print(f"段 {lo}-{hi} 第 {p} 页为空: {str(r)[:200]}"); break
    summary.append(f"{lo}-{hi}: {got}/{total}")
if WEEK: (run / "pull_week.txt").write_text(WEEK)
print(f"server={server} 周={WEEK or '最新'} " + "  ".join(summary) + f"  本次扣 {cost} Credits")
