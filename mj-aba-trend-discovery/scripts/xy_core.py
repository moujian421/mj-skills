#!/usr/bin/env python3
"""核心词准入 + 词簇 + 出表（西柚版最后一步）。
用法: xy_core.py RUN
1 Flash（agy）按 references/core_prompt.txt 拆产品核心词，缓存 RUN/core_tags.jsonl
2 西柚 get_keyword_aba_trends 查核心词近 4 周和去年同期 ±ly_window 周排名（每 20 个词·周约 1 Credit）。
  核心词近 4 周最好排名 <= max_search_rank（50 万）才保留 —— 核心关键词准入门槛；
  关键词或核心词的周搜索量同比（本周 / 去年同期 ±6 周最高）至少一个 >= growth_min（2 倍）才保留，两个都没涨 = 季节/老词剔除；
  核心词涨了 = 核心大词增长（排前），只有关键词涨 = 细分词增长
3 按核心词归簇，输出 RUN/final.csv、RUN/report.md、RUN/trend_<周>.xlsx，只打印统计。
"""
import csv, json, sys
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from pathlib import Path
HERE = Path(__file__).resolve().parent; SKILL = HERE.parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(Path.home() / ".claude/skills/mj-category-cpc/scripts"))
from agylib import agy_jsonl
from mcp_call import Client
CFG = json.loads((SKILL / "config.json").read_text(encoding="utf-8"))
RUN = Path(sys.argv[1])
src = RUN / "candidates_clean.csv" if (RUN / "candidates_clean.csv").exists() else RUN / "candidates.csv"
rows = list(csv.DictReader(open(src, encoding="utf-8")))
week = json.loads((RUN / "meta.json").read_text(encoding="utf-8"))["date"]
# 1 核心词
cache = RUN / "core_tags.jsonl"; core = {}
if cache.exists():
    for l in open(cache, encoding="utf-8"): o = json.loads(l); core[o["keyword"]] = o
todo = {str(i): r["keyword"] for i, r in enumerate(rows) if r["keyword"] not in core}
if todo:
    res = agy_jsonl(SKILL / "references/core_prompt.txt", todo.items())
    with open(cache, "a", encoding="utf-8") as f:
        for i, o in res.items():
            o["keyword"] = todo[i]; core[todo[i]] = o; f.write(json.dumps(o, ensure_ascii=False) + "\n")
for r in rows:
    o = core.get(r["keyword"], {}); r["core"] = (o.get("core") or r["keyword"]).lower().strip(); r["attr"] = o.get("attr", "")
# 2 核心词：近 4 周最好排名（准入）+ 近 4 周平均周搜索量 vs 去年同期 ±ly_window 周内滚动 4 周平均最高值（判断核心大词有没有涨）
OUT = 2_500_000; W = CFG["ly_window"]; A = CFG["avg_weeks"]
own = {r["keyword"].lower(): {"now": int(r["rank"]), "vnow": int(r["vol"] or 0), "vly": int(r["vol_ly"] or 0)} for r in rows}
cfile = RUN / "core_rank3.json"   # {核心词: {"now": 近4周最好排名, "vnow": 近4周平均周搜索量, "vly": 去年同期滚动4周平均最高}}
cached = json.loads(cfile.read_text(encoding="utf-8")) if cfile.exists() else {}
need = sorted({r["core"] for r in rows if r["core"] not in own and r["core"] not in cached})
cost = 0
def aba_weeks(c, kws, start, end, why):
    """返回 {词: {周开始日: (排名, 周搜索量)}}，查询失败返回 None。不在榜的周不返回。"""
    global cost
    r = c.call("get_keyword_aba_trends", {"country": CFG["marketplace"], "keywords": kws,
               "start_week": start.strftime("%Y-%m-%d"), "end_week": end.strftime("%Y-%m-%d"),
               "user_task": CFG["user_task"], "intent_summary": why})
    cost += r.get("cost_credits") or 0
    data = r.get("data") or {}
    if not isinstance(data, dict) or "entities" not in data:
        print("核心词查询异常:", str(r)[:300]); return None
    return {(k.get("searchTerm") or "").lower().strip():
            {w["reportFromDate"]: (w["searchFrequencyRank"], w.get("weeklySearchVolume") or 0) for w in k.get("trends") or [] if w.get("searchFrequencyRank")}
            for k in data["entities"]}
def wk_list(start, n): return [(start + timedelta(weeks=i)).strftime("%Y-%m-%d") for i in range(n)]
if need:
    end = datetime.strptime(week, "%Y%m%d"); c = Client(CFG["xiyou_server"])
    now_w = wk_list(end - timedelta(weeks=A - 1), A)
    ly_start = end - timedelta(weeks=52 + W + A - 1); ly_w = wk_list(ly_start, 2 * W + A)
    for i in range(0, len(need), 100):
        batch = need[i:i+100]
        now = aba_weeks(c, batch, end - timedelta(weeks=A - 1), end, "查核心词近 4 周 ABA 排名和搜索量，判断是否进前 50 万（准入门槛）")
        ly = aba_weeks(c, batch, ly_start, end - timedelta(weeks=52 - W), "查核心词去年同期搜索量，判断核心大词本身是否在增长")
        if now is None or ly is None: continue
        for kw in batch:
            n, l = now.get(kw, {}), ly.get(kw, {})
            v = [l.get(d, (0, 0))[1] for d in ly_w]
            roll = [sum(v[j - A + 1:j + 1]) / A for j in range(A - 1, len(v))]
            cached[kw] = {"now": min((x[0] for x in n.values()), default=None),
                          "vnow": round(sum(n.get(d, (0, 0))[1] for d in now_w) / A), "vly": round(max(roll or [0]))}
    cfile.write_text(json.dumps(cached, ensure_ascii=False), encoding="utf-8")
core_info = {**own, **cached}
# 3 准入 + 增长判断 + 词簇（用户 2026-11-12：核心大词和细分词至少一个明显增长；50 万只是门槛，50 万内的明显增长也要）
TH = CFG["max_search_rank"]; G = CFG["growth_min"]; keep, out, flat = [], [], []
for r in rows:
    ci = core_info.get(r["core"]) or {}
    cn, cv, cvly = ci.get("now"), ci.get("vnow") or 0, ci.get("vly") or 0
    r["core_rank"], r["core_vol"], r["core_vol_ly"] = cn or "", cv, cvly
    r["core_yoy"] = (round(cv / cvly, 1) if cvly else 999) if cv else 0
    kg = float(r["yoy"]) >= G; cg = r["core_yoy"] >= G
    if not cn or cn > TH:
        out.append(r); continue
    if not (kg or cg):
        flat.append(r); continue
    r["demand"] = "核心大词增长" if cg else "细分词增长"
    keep.append(r)
import re
ckey = lambda c: " ".join(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w for w in re.findall(r"[a-z0-9]+", c))  # 单复数合并成一簇
cl = defaultdict(list)
for r in keep: cl[ckey(r["core"])].append(r)
for r in keep: r["cluster_size"] = len(cl[ckey(r["core"])]); r["cluster_core_rank"] = min(int(x["core_rank"]) for x in cl[ckey(r["core"])])
DO = {"核心大词增长": 0, "细分词增长": 1}  # 用户 2026-11-12：先看核心大词在涨的，其次细分词在涨的
TO = {"持续上升": 0, "新进榜": 1, "单周跳升": 2}; SO = {"供给早期": 0, "供给中": 1, "未知": 2, "供给成熟": 3}
keep.sort(key=lambda r: (DO[r["demand"]], -r["cluster_size"], ckey(r["core"]), TO[r["trend"]], SO[r["supply"]], -int(r["vol_add"] or 0)))
cols = ["core", "keyword", "demand", "origin", "attr", "cluster_size", "vol_week", "vol", "vol_ly", "yoy", "vol_add", "core_vol", "core_vol_ly", "core_yoy",
        "trend", "supply", "rank", "rank_ly", "core_rank", "m4", "m_prev", "cvr", "cpc", "top1_click", "monopoly", "top3_click", "concentrated",
        "top3_ratings", "top3_price", "top3_asin", "departments"]
with open(RUN / "final.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, cols, extrasaction="ignore"); w.writeheader(); w.writerows(keep)
CN = {"core": "核心词", "keyword": "关键词", "attr": "新属性", "cluster_size": "同簇词数", "trend": "走势", "supply": "供给",
      "rank": "本周ABA", "rank_ly": "去年同期ABA", "yoy": "搜索量同比（999=去年无）", "m4": "近4周中位", "m_prev": "9-16周前中位", "core_rank": "核心词近4周最好", "core_vol": "核心词近4周平均周搜索量", "core_vol_ly": "核心词去年同期4周平均最高", "core_yoy": "核心词搜索量同比",
      "vol_week": "本周周搜索量", "vol": "近4周平均周搜索量", "vol_ly": "去年同期4周平均最高", "vol_add": "4周平均增量", "demand": "需求类型", "origin": "从哪里涨进来",
      "weekly_volume": "周搜索量", "cvr": "点击转化率", "cpc": "CPC", "top1_click": "第1名点击占比", "monopoly": "单品垄断", "top3_click": "前3点击合计", "concentrated": "点击集中",
      "top3_ratings": "前3评论数", "top3_price": "前3价格", "top3_asin": "前3 ASIN", "departments": "西柚类目"}
try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    wb = Workbook(); ws = wb.active; ws.title = "候选"
    ws.append([CN[c] for c in cols])
    for r in keep: ws.append([r.get(c, "") for c in cols])
    ws2 = wb.create_sheet("剔除")
    ws2.append(["关键词", "原因", "本周ABA", "去年同期ABA", "西柚类目"])
    for r in json.load(open(RUN / "screened.json", encoding="utf-8"))["removed"]:
        ws2.append([r["keyword"], r["why"], r["rank"], r["rank_ly"], r["departments"]])
    if (RUN / "candidates_removed.csv").exists():
        for r in csv.DictReader(open(RUN / "candidates_removed.csv", encoding="utf-8")):
            ws2.append([r["keyword"], f"Flash:{r['tag']} {r['why']}", r["rank"], r.get("rank_ly", ""), r["departments"]])
    for r in out: ws2.append([r["keyword"], f"核心词 {r['core']} 未进前{TH//10000}万", r["rank"], r["rank_ly"], r["departments"]])
    for r in flat: ws2.append([r["keyword"], f"关键词搜索量同比 {r['yoy']}、核心词 {r['core']} 同比 {r['core_yoy']}，都 <{G} 倍（季节/老词）", r["rank"], r["rank_ly"], r["departments"]])
    for s in (ws, ws2):
        for c in s[1]: c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="305496")
        s.freeze_panes = "B2"
        for col in s.columns: s.column_dimensions[col[0].column_letter].width = min(40, max(10, max(len(str(c.value or "")) for c in col) + 2))
    wb.save(RUN / f"trend_{week}.xlsx")
except ImportError:
    print("没装 openpyxl，跳过 xlsx")
lines = [f"# ABA 新兴市场候选（西柚，{week} 周）", "", f"保留 {len(keep)} 个词 / {len(cl)} 个核心词簇；核心词未进前 {TH//10000} 万剔除 {len(out)} 个；核心词和关键词同比都 <{G} 倍剔除 {len(flat)} 个。", "",
         "| 需求 | 来源 | 核心词 | 关键词 | 周搜索量 | 去年同期 | 同比 | 核心词搜索量 | 核心词去年 | 核心词同比 | 本周排名 | 走势 | 供给 |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
for r in keep[:80]:
    lines.append(f"| {r['demand']} | {r.get('origin', '')} | {r['core']} | {r['keyword']} | {r['vol']} | {r['vol_ly']} | {r['yoy']} | {r['core_vol']} | {r['core_vol_ly']} | {r['core_yoy']} | {r['rank']} | {r['trend']} | {r['supply']} |")
(RUN / "report.md").write_text("\n".join(lines), encoding="utf-8")
print(json.dumps({"输入": len(rows), "保留": len(keep), "词簇": len(cl), "核心词未达标": len(out), "大词细分词都没涨": len(flat), "查核心词": len(need),
                  "核心词查到排名": sum(1 for k in need if (core_info.get(k) or {}).get("now")), "西柚扣费": cost,
                  "需求": Counter(r["demand"] for r in keep), "来源": Counter(r.get("origin", "") for r in keep), "走势": Counter(r["trend"] for r in keep), "供给": Counter(r["supply"] for r in keep)}, ensure_ascii=False))
