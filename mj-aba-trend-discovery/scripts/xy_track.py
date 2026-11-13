#!/usr/bin/env python3
"""跨周跟踪：每周的保留词进 data/watchlist.json，之后每周补新的周排名，看是“一周闪现”还是“站稳/继续上升”。
用法: xy_track.py RUN
- 本周拉数里出现的词：直接用 raw 里的周历史更新（免费）。
- 其他活跃词：get_keyword_aba_trends 只补“上次刷新之后”的周（Argon 2026-11-12：不重复刷近 4 周）。
- 连续 track_archive_weeks（8）周都在 max_search_rank（50 万）外 → 归档，不再刷新。
- 不剔除任何词（用户 2026-11-04 不要留存过滤），只标状态：
    确认 = 首见后下一周起都在 50 万内、最新排名不比首见差 1.5 倍以上（用户 2026-11-12：不用等 4 周，下一周站住就算）；
    闪现 = 首见后下一周就掉出 50 万；其余 观察。
输出：在 RUN/trend_<周>.xlsx 加“持续跟踪”页；final.csv 不改；打印统计。
"""
import json, sys
from datetime import datetime, timedelta
from pathlib import Path
HERE = Path(__file__).resolve().parent; SKILL = HERE.parent
sys.path.insert(0, str(Path.home() / ".claude/skills/mj-category-cpc/scripts"))
from mcp_call import Client
import csv
CFG = json.loads((SKILL / "config.json").read_text(encoding="utf-8"))
RUN = Path(sys.argv[1]); TH = CFG["max_search_rank"]
week = json.loads((RUN / "meta.json").read_text(encoding="utf-8"))["date"]; wk = f"{week[:4]}-{week[4:6]}-{week[6:]}"
WL = SKILL / "data" / "watchlist.json"
wl = json.loads(WL.read_text(encoding="utf-8")) if WL.exists() else {}
# 本周拉到的词的历史（免费）
hist = {}
for f in (RUN / "raw").glob("*.json"):
    for k in (json.loads(f.read_text(encoding="utf-8")).get("data") or {}).get("list") or []:
        hist[k["searchTerm"]["original"].strip()] = {x["reportFromDate"]: x["searchFrequencyRank"] for x in k["searchTermTrends"]}
new = 0
for r in csv.DictReader(open(RUN / "final.csv", encoding="utf-8")):
    kw = r["keyword"]
    if kw not in wl:
        wl[kw] = {"core": r["core"], "demand": r["demand"], "first_week": wk, "first_rank": int(r["rank"]),
                  "ranks": {wk: int(r["rank"])}, "status": "观察", "last_refresh": wk}; new += 1
for kw, o in wl.items():
    if kw in hist:
        o["ranks"].update({d: v for d, v in hist[kw].items() if d >= o["first_week"]}); o["last_refresh"] = wk
# 其他活跃词补周
todo = [kw for kw, o in wl.items() if o["status"] != "归档" and o["last_refresh"] != wk]
cost = 0
if todo:
    c = Client(CFG["xiyou_server"]); end = datetime.strptime(wk, "%Y-%m-%d")
    groups = {}
    for kw in todo:
        start = max(datetime.strptime(wl[kw]["last_refresh"] or wl[kw]["first_week"], "%Y-%m-%d") + timedelta(days=7), end - timedelta(weeks=51))
        if start <= end: groups.setdefault(start, []).append(kw)
    for start, kws in groups.items():
        for i in range(0, len(kws), 100):
            batch = kws[i:i+100]
            r = c.call("get_keyword_aba_trends", {"country": CFG["marketplace"], "keywords": batch,
                       "start_week": start.strftime("%Y-%m-%d"), "end_week": wk, "user_task": CFG["user_task"],
                       "intent_summary": "刷新往期候选词的最新 ABA 周排名，判断是一周闪现还是持续站稳"})
            cost += r.get("cost_credits") or 0
            data = r.get("data") or {}
            if not isinstance(data, dict) or "entities" not in data:
                print("跟踪刷新异常:", str(r)[:300]); continue
            got = {(e.get("searchTerm") or "").lower().strip(): e for e in data["entities"]}
            for kw in batch:
                e = got.get(kw.lower().strip())
                weeks = {w["reportFromDate"]: w.get("searchFrequencyRank") for w in (e or {}).get("trends") or []}
                d = start
                while d <= end:   # 没返回的周记为不在榜
                    ds = d.strftime("%Y-%m-%d"); wl[kw]["ranks"][ds] = weeks.get(ds); d += timedelta(days=7)
                wl[kw]["last_refresh"] = wk
# 状态
from collections import Counter
for kw, o in wl.items():
    ws = sorted(d for d in o["ranks"] if d >= o["first_week"])
    rs = [o["ranks"][d] for d in ws]
    inn = [x for x in rs if x and x <= TH]
    o["weeks_tracked"], o["weeks_in"] = len(rs), len(inn)
    o["latest_rank"] = rs[-1] if rs else None; o["best_rank"] = min(inn) if inn else None
    tail = rs[-CFG["track_archive_weeks"]:]
    after = rs[1:]   # 首见周之后的周
    if len(tail) >= CFG["track_archive_weeks"] and not any(x and x <= TH for x in tail): o["status"] = "归档"
    elif len(rs) >= CFG["track_confirm_weeks"] and after and all(x and x <= TH for x in after)             and o["latest_rank"] <= o["first_rank"] * CFG["track_confirm_max_drop"]: o["status"] = "确认"
    elif after and not (after[0] and after[0] <= TH): o["status"] = "闪现"
    else: o["status"] = "观察"
WL.write_text(json.dumps(wl, ensure_ascii=False, indent=1), encoding="utf-8")
# xlsx
xl = RUN / f"trend_{week}.xlsx"
if xl.exists():
    from openpyxl import load_workbook
    from openpyxl.styles import Font, PatternFill
    wb = load_workbook(xl)
    if "持续跟踪" in wb.sheetnames: del wb["持续跟踪"]
    ws = wb.create_sheet("持续跟踪", 1)
    ws.append(["状态", "关键词", "核心词", "需求类型", "首见周", "首见排名", "最新排名", "跟踪后最好", "跟踪周数", "在50万内周数", "近8周排名（旧→新）"])
    SO = {"确认": 0, "观察": 1, "闪现": 2, "归档": 3}
    for kw, o in sorted(wl.items(), key=lambda kv: (SO[kv[1]["status"]], kv[1]["latest_rank"] or 9e9)):
        last8 = [o["ranks"][d] for d in sorted(o["ranks"]) if d >= o["first_week"]][-8:]
        ws.append([o["status"], kw, o["core"], o["demand"], o["first_week"], o["first_rank"], o["latest_rank"], o["best_rank"],
                   o["weeks_tracked"], o["weeks_in"], " → ".join(str(x) if x else "-" for x in last8)])
    for c in ws[1]: c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="305496")
    ws.freeze_panes = "C2"
    for col in ws.columns: ws.column_dimensions[col[0].column_letter].width = min(50, max(10, max(len(str(c.value or "")) for c in col) + 2))
    wb.save(xl)
print(json.dumps({"跟踪池": len(wl), "本周新增": new, "刷新": len(todo), "西柚扣费": cost,
                  "状态": Counter(o["status"] for o in wl.values())}, ensure_ascii=False))
