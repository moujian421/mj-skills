#!/usr/bin/env python3
"""ABA 周度趋势新词发现：生成调用清单、过滤、判断季节性、出报告。

用法（RUN 是本周的数据目录，DATE 是 ABA 周的周六 yyyymmdd）：
  aba_trend.py calls1 RUN DATE   # 两个清单的第 1 页 -> RUN/calls1.txt
  aba_trend.py calls2 RUN        # 按第 1 页的 total 补齐剩余页 -> RUN/calls2.txt
  aba_trend.py screen RUN        # 合并、节日词/品牌词过滤、词簇 -> RUN/screened.json + 西柚清单 RUN/calls3.txt
  aba_trend.py final RUN         # 去年同期季节性判断 -> RUN/candidates.csv、RUN/report.md
只打印统计，不打印全量数据。
"""
import csv, json, math, re, sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
CFG = json.loads((SKILL / "config.json").read_text())
FIELDS = ("keyword,departments,searchRank,searches,purchases,w1SearchRank,w4SearchRank,w12SearchRank,"
          "w1RankGrowthRate,w4RankGrowthRate,clickShareRate,cvsShareRate,top3Brands,top3AsinDtoList,titleDensityExact")
STOP = {"for", "and", "with", "the", "a", "an", "of", "to", "in", "on", "&", "men", "women", "mens", "womens",
        "kids", "girls", "boys", "adults", "set", "pack", "small", "large", "mini", "best", "new"}


import os
PULLER = os.environ.get("PULLER", "oc")  # oc=DeepSeek(oc_pull.sh)  cb=CodeBuddy hy3(cb_pull.sh)


def fmt(server, tool, args):
    j = json.dumps(args, ensure_ascii=False)
    return f"{server} / {tool} : {j}" if PULLER == "cb" else f'tools["{server}"]["{tool}"]({j})'


def parse_line(line):
    m = re.match(r'\s*tools\["([^"]+)"\]\["([^"]+)"\]\((.*)\)\s*$', line) or re.match(r"\s*(\S+)\s*/\s*(\S+)\s*:\s*(.*)$", line)
    return m.group(1), m.group(2), json.loads(m.group(3))


def is_month(date):
    return len(str(date)) == 6


def period_end(date):
    """周：周六；月：月末最后一天"""
    if is_month(date):
        y, m = int(date[:4]), int(date[4:])
        return datetime(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)
    return datetime.strptime(date, "%Y%m%d")


def psize(date):
    # 实测每页上限：周度 40、月度 15，size 填更大也只给这么多
    return CFG["page_size_monthly"] if is_month(date) else CFG["page_size"]


def ss_call(extra):
    tool = "aba_research_monthly" if is_month(extra.get("date", "")) else "aba_research_weekly"
    req = {"marketplace": CFG["marketplace"], "maxSearchRank": CFG["max_search_rank"],
           "departments": CFG["departments"], "size": psize(extra.get("date", "")), "returnFields": FIELDS}
    req.update(extra)
    return fmt("sellersprite-mcp", tool, {"request": req})


def lists(date):
    # A：异动市场（上周/上月不在榜的词，含新词和回归词）；B：周排名提升 >= 阈值（飙升词）
    # 月度只跑 A：用来补“进榜那周没跑到、之后稳住”的词（如 fat trimmer）
    if is_month(date):
        return {"A": {"date": date, "searchModel": 2}}
    return {"A": {"date": date, "searchModel": 2},
            "B": {"date": date, "minRankGrowthRate": CFG["min_rank_growth_pct"]}}


def load_raw(path):
    t = Path(path).read_text()
    # CodeBuddy 返回超长时只留“saved to <文件>”指针，去读那个文件
    m = re.search(r"(?:saved to|Full output saved to:?)\s+(/\S+?)\.?\s*$", t.splitlines()[0] if t else "")
    if m and Path(m.group(1)).exists():
        t = Path(m.group(1)).read_text()
    try:
        d = json.loads(t)
    except json.JSONDecodeError:
        return None
    # MCP 包装：{"content":[{"type":"text","text":"..."}]} 或直接是返回体
    if isinstance(d, dict) and "content" in d and isinstance(d["content"], list):
        for c in d["content"]:
            if c.get("type") == "text":
                try:
                    return json.loads(c["text"])
                except json.JSONDecodeError:
                    return None
    if isinstance(d, list) and d and isinstance(d[0], dict) and "text" in d[0]:
        try:
            return json.loads(d[0]["text"])
        except json.JSONDecodeError:
            return None
    return d


def pulled(run, sub):
    """返回 [(调用参数, 返回体)]。兼容 oc_pull（index 是列表）和 cb_pull（index 是 {行号: 文件}）。"""
    idx = run / sub / "index.json"
    if not idx.exists():
        return []
    ix = json.loads(idx.read_text())
    out = []
    if isinstance(ix, list) and ix and "line" in ix[0]:  # agy_pull：[{line, file}]
        lines = [l for l in (run / sub.replace("pull", "calls")).with_suffix(".txt").read_text().splitlines() if l.strip()]
        for e in ix:
            f = Path(e["file"]) if os.path.isabs(str(e["file"])) else run / sub / "raw" / e["file"]
            out.append(({"args": parse_line(lines[int(e["line"]) - 1])[2]}, load_raw(f) if f.exists() else None))
    elif isinstance(ix, list):
        for e in ix:
            body = load_raw(run / sub / "raw" / e["file"]) if not e.get("error") else None
            out.append(({"args": e["args"]}, body))
    else:
        lines = [l for l in (run / sub.replace("pull", "calls")).with_suffix(".txt").read_text().splitlines() if l.strip()]
        for n, fn in ix.items():
            body = load_raw(run / sub / "raw" / fn)
            out.append(({"args": parse_line(lines[int(n) - 1])[2]}, body))
    return out


def which_list(req):
    return "A" if req.get("searchModel") == 2 else "B"


def cmd_calls1(run, date):
    run.mkdir(parents=True, exist_ok=True)
    (run / "meta.json").write_text(json.dumps({"date": date}))
    lines = [ss_call({**v, "page": 1}) for v in lists(date).values()]
    (run / "calls1.txt").write_text("\n".join(lines) + "\n")
    print(f"calls1: {len(lines)} 行")


def cmd_calls2(run):
    date = json.loads((run / "meta.json").read_text())["date"]
    lines, totals = [], {}
    for e, body in pulled(run, "pull1"):
        req = e["args"]["request"]
        if not body or body.get("code") != "OK":
            print("第 1 页出错：", which_list(req), (body or {}).get("data"))
            continue
        k = which_list(req)
        totals[k] = body["data"]["total"]
        pages = math.ceil(totals[k] / psize(date))
        lines += [ss_call({**lists(date)[k], "page": p}) for p in range(2, pages + 1)]
    (run / "calls2.txt").write_text("\n".join(lines) + ("\n" if lines else ""))
    json.dump(totals, open(run / "totals.json", "w"))
    print(f"totals={totals} calls2: {len(lines)} 行")


def tokens(kw):
    return [t for t in re.findall(r"[a-z0-9']+", kw.lower()) if t not in STOP]


def cmd_screen(run):
    items = {}
    for sub in ("pull1", "pull2"):
        for e, body in pulled(run, sub):
            if not body or body.get("code") != "OK":
                continue
            k = which_list(e["args"]["request"])
            for it in body["data"].get("items") or []:
                kw = (it.get("keyword") or "").strip().lstrip("￼").strip()
                if not kw:
                    continue
                if kw in items and items[kw]["list"] == "A":
                    continue
                it["keyword"], it["list"] = kw, k
                items[kw] = it
    totals = json.loads((run / "totals.json").read_text()) if (run / "totals.json").exists() else {}
    got = defaultdict(int)
    for it in items.values():
        got[it["list"]] += 1
    stat = {"拉到": dict(got), "接口 total": totals}

    hol = [h.lower() for h in CFG["holiday_roots"]]
    keep, drop = [], defaultdict(list)
    for kw, it in items.items():
        if it["list"] == "A" and is_month(json.loads((run / "meta.json").read_text())["date"]):
            it["type"] = "月度新词"
        elif it["list"] == "A":
            it["type"] = "新词" if it.get("w4SearchRank") is None and it.get("w12SearchRank") is None else "回归词"
        else:
            it["type"] = "飙升词"
        if any(h in kw.lower() for h in hol):
            drop["节日词"].append(kw); continue
        keep.append(it)

    # 词簇：相邻两个实词组成的词组（复数去 s），同一周有几个候选词共用
    bg_words = defaultdict(set)
    for it in keep:
        tk = [t[:-1] if len(t) > 3 and t.endswith("s") and not t.endswith("ss") else t for t in tokens(it["keyword"])]
        it["_bg"] = {" ".join(tk[i:i + 2]) for i in range(len(tk) - 1)} or set(tk)
        for b in it["_bg"]:
            bg_words[b].add(it["keyword"])
    for it in keep:
        best = max(it["_bg"], key=lambda b: (len(bg_words[b]), b), default="")
        it["cluster"], it["cluster_size"] = best, len(bg_words.get(best, ()))
        del it["_bg"]

    # 品牌词 / 单品垄断：词簇 >= 3 时豁免（一个爆款带火的新品类，首发期常被单个 ASIN 垄断）
    kept = []
    for it in keep:
        low = it["keyword"].lower()
        if it["cluster_size"] < CFG["cluster_exempt"]:
            brands = [b.lower() for b in (it.get("top3Brands") or []) if b and len(b) >= 3]
            if any(b in low for b in brands):
                drop["含品牌名"].append(it["keyword"]); continue
            asins = it.get("top3AsinDtoList") or []
            if asins and (asins[0].get("clickRate") or 0) >= CFG["brand_top1_click"]:
                drop["单品垄断"].append(it["keyword"]); continue
        kept.append(it)
    keep = kept

    stat["过滤"] = {k: len(v) for k, v in drop.items()}
    stat["留下"] = len(keep)
    json.dump({"keep": keep, "drop": drop, "stat": stat}, open(run / "screened.json", "w"), ensure_ascii=False)

    # 西柚：查去年同期前 8 周到后 2 周
    date = period_end(json.loads((run / "meta.json").read_text())["date"])
    ly = date - timedelta(days=364)
    s, e = (ly - timedelta(days=56)).strftime("%Y-%m-%d"), (ly + timedelta(days=14)).strftime("%Y-%m-%d")
    kws = [it["keyword"] for it in keep]
    lines = []
    for i in range(0, len(kws), CFG["xiyou_batch"]):
        args = {"keywords": kws[i:i + CFG["xiyou_batch"]], "start_week": s, "end_week": e, "country": CFG["marketplace"],
                "user_task": CFG["user_task"], "intent_summary": "查候选词去年同期 ABA 排名，判断是不是季节词"}
        lines.append(fmt(CFG.get("xiyou_server", "xydc-mcp"), "get_keyword_aba_trends", args))
    (run / "calls3.txt").write_text("\n".join(lines) + ("\n" if lines else ""))
    print(json.dumps(stat, ensure_ascii=False), f"calls3: {len(lines)} 行（约 {len(kws)} Credits）")


def cmd_final(run):
    sc = json.loads((run / "screened.json").read_text())
    date = period_end(json.loads((run / "meta.json").read_text())["date"])
    ly = date - timedelta(days=364)
    trends = {}
    for e, body in pulled(run, "pull3"):
        if not body or body.get("status") != 200:
            continue
        for ent in body["data"].get("entities") or []:
            pts = []
            for t in ent.get("trends") or []:
                end = datetime.strptime(t["reportToDate"], "%Y-%m-%d")
                pts.append(((end - ly).days, t.get("searchFrequencyRank")))
            trends[ent["searchTerm"]] = pts
    th, ratio = CFG["seasonal_ly_rank"], CFG["seasonal_spike_ratio"]
    rows, seasonal, nodata = [], [], []
    for it in sc["keep"]:
        pts = trends.get(it["keyword"])
        if pts is None:
            nodata.append(it["keyword"]); it["ly_peak"] = it["ly_base"] = None; it["season"] = "未查到"
        else:
            peak = [r for d, r in pts if -14 <= d <= 14 and r]
            base = [r for d, r in pts if -56 <= d <= -28 and r]
            allr = [r for d, r in pts if r]
            it["ly_peak"] = min(peak) if peak else None
            it["ly_base"] = sorted(base)[len(base) // 2] if base else None
            if it["type"] in ("新词", "回归词", "月度新词"):
                is_season = sum(1 for r in allr if r <= th) >= CFG["seasonal_min_weeks"]
            else:
                b = it["ly_base"] or 2_500_000
                is_season = it["ly_peak"] is not None and it["ly_peak"] <= th and it["ly_peak"] <= ratio * b
            it["season"] = "季节词" if is_season else "否"
            if is_season:
                seasonal.append(it["keyword"]); continue
        rows.append(it)
    pri = {"新词": 0, "月度新词": 0, "回归词": 1, "飙升词": 2}
    rows.sort(key=lambda r: (-r["cluster_size"], pri[r["type"]], r["searchRank"]))

    cols = ["keyword", "type", "searchRank", "w1SearchRank", "w4SearchRank", "w12SearchRank", "searches", "purchases",
            "cluster", "cluster_size", "departments", "top1_click", "top1_asin", "ly_peak", "ly_base", "season"]
    with open(run / "candidates.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(cols)
        for r in rows:
            a = (r.get("top3AsinDtoList") or [{}])[0] or {}
            r["top1_click"], r["top1_asin"] = a.get("clickRate"), a.get("asin")
            w.writerow([("|".join(r[c]) if c == "departments" else r.get(c)) for c in cols])
    st = sc["stat"]; st["季节词"] = len(seasonal); st["西柚未查到"] = len(nodata); st["最终"] = len(rows)
    md = [f"# ABA 趋势新词 {json.loads((run / 'meta.json').read_text())['date']}", "", "统计：`" + json.dumps(st, ensure_ascii=False) + "`", "",
          "| 关键词 | 类型 | 本周排名 | 4周前 | 词簇（个数） | 类目 | 第1名点击 |", "|---|---|---|---|---|---|---|"]
    for r in rows[:80]:
        md.append(f"| {r['keyword']} | {r['type']} | {r['searchRank']} | {r.get('w4SearchRank') or '-'} | "
                  f"{r['cluster']}（{r['cluster_size']}） | {'/'.join(r['departments'][:2])} | {r['top1_click'] or '-'} |")
    (run / "report.md").write_text("\n".join(md) + "\n")
    json.dump({"seasonal": seasonal, "nodata": nodata}, open(run / "seasonal.json", "w"), ensure_ascii=False)
    print(json.dumps(st, ensure_ascii=False))


if __name__ == "__main__":
    c, run = sys.argv[1], Path(sys.argv[2]).resolve()
    {"calls1": lambda: cmd_calls1(run, sys.argv[3]), "calls2": lambda: cmd_calls2(run),
     "screen": lambda: cmd_screen(run), "final": lambda: cmd_final(run)}[c]()
