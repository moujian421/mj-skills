#!/usr/bin/env python3
"""按词簇查亚马逊供给，判断需求类型、供给缺口、Google 热度阶段（替代西柚版 classify.py）。
用法: PULLER=cb|agy|oc supply.py WORK RUN [RUN ...]   （cb=CodeBuddy hy3，agy=Gemini Flash，oc=DeepSeek）
  中途限流停了可以直接重跑同一条命令：已拉到的复用，只补缺的行。
  WORK：这次的工作目录（如 data/supply_20261104）
词簇 = Flash 拆出的产品核心词（core_tags.jsonl，复数去 s）。全部词簇都查。
第 1 轮：每个词簇的代表词用卖家精灵 competitor_lookup 精准匹配查前 10 个商品（按销量）；精准匹配不到 3 个的再用词组匹配（matchType 1：所有词都出现、不限顺序）查一次。
  不要用模糊匹配（matchType 2，任意词命中，返回几百万无关商品）。
第 2 轮：代表词看起来新（对口商品 <3 个或最早对口商品 12 个月内上架）且有新属性的，再查核心词。
对口校验：Flash 判断每个商品标题是否真对口（references/relevance_prompt.txt），蹭词老链接不算。
第 3 轮：新产品 / 供给缺口 / 供给早期的词簇里，只取排在前面的 google_top_n 个（默认 30）查 Google Trends，判断上升 / 平稳 / 回落。
判定：
  核心词是老产品 = 有对口商品早于 12 个月前上架，或精准匹配商品 >=100；否则新产品。老产品 + 有新属性 = 旧产品新属性，无属性 = 旧产品回暖。
  供给缺口 = 对口商品 <3；供给早期 = 对口商品全部 12 个月内上架；否则已有供给（近 90 天新进 >=3 个时注明）。属性只是尺寸规格时供给看核心词。
  代表词：优先和核心词一样的词，其次最短的词，去掉 best/top 等修饰。
输出 WORK/supply.csv（每个关键词一行），WORK/clusters.csv（每个词簇一行），只打印统计。"""
import csv, json, os, re, statistics, subprocess, sys
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import aba_trend as A
from agylib import agy_jsonl
SKILL = Path(__file__).resolve().parent.parent
BO = Path.home() / ".claude/skills/batch-offload/scripts"
WORK = Path(sys.argv[1]).resolve(); WORK.mkdir(parents=True, exist_ok=True)
RUNS = [Path(p).resolve() for p in sys.argv[2:]]
TODAY = datetime.now()
norm = lambda c: " ".join(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w for w in c.lower().split())


def run_puller(calls, out):
    p = os.environ.get("PULLER", "oc")
    script = {"cb": "cb_pull.sh", "agy": "agy_pull.sh"}.get(p, "oc_pull.sh")
    cmd = [str(BO / script), str(calls), str(out)] + (["gemini-3.8-flash-low"] if p == "agy" else ["5"])
    r = subprocess.run(cmd, capture_output=True, text=True)
    return (r.stdout.strip().splitlines() or [""])[-1]


def pull(tag, lines):
    """跑一轮卖家精灵/Google 调用，返回 {调用参数 JSON: 返回体}。
    已拉到的结果（tag_pull、tag_r*_pull）复用；缺的行（限流、漏调）写成 tag_rN 补跑，不重复调用已成功的。"""
    if not lines: return {}
    if not (WORK / f"{tag}_pull" / "index.json").exists():  # 已拉过就不覆盖原清单，否则行号对不上
        (WORK / f"{tag}_calls.txt").write_text("\n".join(lines) + "\n")
    def collect():
        res = {}
        for d in sorted(WORK.glob(f"{tag}_pull")) + sorted(WORK.glob(f"{tag}_r*_pull")):
            if (d / "index.json").exists():
                for e, body in A.pulled(WORK, d.name):
                    if body is not None: res[json.dumps(e["args"], sort_keys=True)] = body
        return res
    if not (WORK / f"{tag}_pull" / "index.json").exists():
        print(tag, run_puller(WORK / f"{tag}_calls.txt", WORK / f"{tag}_pull"))
    for n in range(1, 4):
        res = collect()
        miss = [l for l in lines if json.dumps(A.parse_line(l)[2], sort_keys=True) not in res]
        if not miss: break
        rt = f"{tag}_r{n}"
        while (WORK / f"{rt}_pull" / "index.json").exists(): n += 10; rt = f"{tag}_r{n}"
        (WORK / f"{rt}_calls.txt").write_text("\n".join(miss) + "\n")
        print(rt, f"补跑 {len(miss)} 行:", run_puller(WORK / f"{rt}_calls.txt", WORK / f"{rt}_pull"))
    res = collect()
    left = sum(1 for l in lines if json.dumps(A.parse_line(l)[2], sort_keys=True) not in res)
    if left: print(f"{tag}: 还有 {left} 行没拉到（结果里会标查询失败）")
    return res


def lookup_call(phrase, mt=3):
    return A.fmt("sellersprite-mcp", "competitor_lookup", {"request": {"marketplace": A.CFG["marketplace"], "keyword": phrase, "matchType": mt,
                 "order": {"field": "total_units", "desc": True}, "size": 10, "variation": "Y", "returnFields": "asin,title,availableDate,ratings,price"}})


def items_of(res, phrase, mt=3):
    b = res.get(json.dumps(A.parse_line(lookup_call(phrase, mt))[2], sort_keys=True))
    if not b or b.get("code") != "OK": return None, []
    return b["data"].get("total"), b["data"].get("items") or []


def relevance(pairs):
    """pairs: [(phrase, title)] -> {(phrase,title): 0/1}，结果缓存在 WORK/relevance.jsonl"""
    cache = WORK / "relevance.jsonl"; got = {}
    if cache.exists():
        for l in open(cache):
            o = json.loads(l); got[(o["p"], o["t"])] = o["rel"]
    todo = [p for p in dict.fromkeys(pairs) if p not in got]
    for i in range(0, len(todo), 250):
        chunk = todo[i:i + 250]
        lines = {str(j): f"{p}\t{t[:150]}" for j, (p, t) in enumerate(chunk)}
        out = agy_jsonl(SKILL / "references/relevance_prompt.txt", lines, key="rel")
        with open(cache, "a") as f:
            for j, (p, t) in enumerate(chunk):
                o = out.get(str(j))
                if o is None: continue
                got[(p, t)] = int(o.get("rel", 0)); f.write(json.dumps({"p": p, "t": t, "rel": got[(p, t)]}, ensure_ascii=False) + "\n")
    return got


def stats(total, items, rel):
    r = [it for it in items if rel.get((it["_p"], it["title"])) == 1 and it.get("availableDate")]
    dates = sorted(datetime.fromtimestamp(it["availableDate"] / 1000) for it in r)
    recent = [it for it in r if datetime.fromtimestamp(it["availableDate"] / 1000) >= TODAY - timedelta(days=90) and (it.get("ratings") or 0) <= 5]
    return {"total": total, "n_rel": len(r), "earliest": dates[0].strftime("%Y-%m-%d") if dates else "",
            "median": dates[len(dates) // 2].strftime("%Y-%m-%d") if dates else "", "n_recent": len(recent)}


# 1. 读保留词和核心词，按核心词聚类
words = []
for run in RUNS:
    tags = {json.loads(l)["keyword"]: json.loads(l) for l in open(run / "core_tags.jsonl")}
    for r in csv.DictReader(open(run / "candidates_clean.csv")):
        o = tags.get(r["keyword"], {})
        r["core"], r["attr"], r["src"] = o.get("core", ""), (o.get("attr") or "").strip(), run.name
        words.append(r)
clusters = {}
for r in words:
    clusters.setdefault(norm(r["core"]) or r["keyword"].lower(), []).append(r)
# 全部词簇都查（曾跳过单个飙升词，结果漏掉 silicone drill brush）。以后可用 titleDensityExact 预筛
sel = dict(clusters)
FILLER = {"best", "top", "good", "cheap", "new", "great", "amazing", "viral"}
SIZE = re.compile(r"^(\d[\d./-]*\s*(inch|in|mm|cm|ft|oz|lb|pack|pcs|pc|count|ct)?\s*)+$|^(small|large|mini|xl)$", re.I)
qstr = lambda k: " ".join(w for w in k.lower().split() if w not in FILLER)


def pick_rep(c, v):
    # 代表词：优先和核心词一样的词，其次最短的词（带 best、尺寸等修饰的词精准匹配常查不到商品），再按排名
    return qstr(min(v, key=lambda r: (norm(r["keyword"]) != c, len(r["keyword"].split()), int(r["searchRank"])))["keyword"])
rep = {c: pick_rep(c, v) for c, v in sel.items()}
print(f"词簇 {len(clusters)}，查 {len(sel)} 个（跳过只有一个词的飙升词 {len(clusters) - len(sel)} 个）")

# 2. 第 1 轮：代表词
res1 = pull("sup1", [lookup_call(p) for p in sorted(set(rep.values()))])
pairs = []
for p in set(rep.values()):
    _, its = items_of(res1, p)
    for it in its: it["_p"] = p; pairs.append((p, it["title"]))
# 精准匹配不到 3 个商品的（长词组、换了说法），再用模糊匹配查一次，同样做对口校验
few = sorted({p for p in set(rep.values()) if (items_of(res1, p)[0] or 0) < 3})
res1b = pull("sup1b", [lookup_call(p, 1) for p in few])
for p in few:
    _, its = items_of(res1b, p, 1)
    for it in its: it["_p"] = p; pairs.append((p, it["title"]))
rel = relevance(pairs)
rep_st = {}
for c, p in rep.items():
    t, its = items_of(res1, p)
    if p in few:
        t2, its2 = items_of(res1b, p, 1)
        if t2: t, its = t2, its2
    for it in its: it["_p"] = p
    rep_st[c] = stats(t, its, rel) if t is not None else None
    if rep_st[c]: rep_st[c]["exact_total"] = items_of(res1, p)[0] or 0

# 3. 第 2 轮：代表词看起来新、且代表词不等于核心词的，查核心词
cut = (TODAY - timedelta(days=365)).strftime("%Y-%m-%d")
is_size = lambda c: any(r["attr"] for r in sel[c]) and all(SIZE.match(r["attr"]) for r in sel[c] if r["attr"])
need = [c for c in sel if rep_st.get(c) and c != rep[c] and (rep_st[c]["n_rel"] < 3 or rep_st[c]["earliest"] >= cut or is_size(c))]
res2 = pull("sup2", [lookup_call(c) for c in need])
pairs = []
for c in need:
    _, its = items_of(res2, c)
    for it in its: it["_p"] = c; pairs.append((c, it["title"]))
rel.update(relevance(pairs))
core_st = {}
for c in sel:
    if c in need or (c != rep[c] and all(SIZE.match(r["attr"]) for r in sel[c] if r["attr"]) and any(r["attr"] for r in sel[c])):
        t, its = items_of(res2, c)
        for it in its: it["_p"] = c
        core_st[c] = stats(t, its, rel) if t is not None else None
        if core_st[c]: core_st[c]["exact_total"] = t or 0
    elif c == rep[c] or not rep_st.get(c) or not (rep_st[c]["n_rel"] < 3 or rep_st[c]["earliest"] >= cut):
        core_st[c] = rep_st.get(c)  # 代表词已经是老产品，核心词更是

# 4. 判定
out = {}
for c in sel:
    rs, cs = rep_st.get(c), core_st.get(c)
    if rs is None or cs is None:
        demand, supply = "查询失败", ""
    else:
        # 核心词前排常被配件占满（compound bow → 箭、瞄准镜），有 1 个老对口商品或匹配商品很多就算老产品
        old = bool(cs["earliest"] and cs["earliest"] < cut) or cs.get("exact_total", 0) >= 100
        has_attr = any(r["attr"] for r in sel[c]) and c != rep[c]
        demand = ("旧产品新属性" if has_attr else "旧产品回暖") if old else "新产品"
        # 属性只是尺寸规格（4.25 hole saw）时，精准匹配查不到很正常，供给看核心词
        size_only = all(SIZE.match(r["attr"]) for r in sel[c] if r["attr"]) and any(r["attr"] for r in sel[c])
        ss = cs if size_only else rs
        if ss["n_rel"] < 3 and len(rep[c].split()) >= 4 and old and (cs["n_rel"] or 0) >= 3:
            supply = "可能缺口（词组长，需人工看）"  # 长词组精准、词组匹配都查不到，但核心词早有供给
        elif ss["n_rel"] < 3: supply = "供给缺口"
        elif ss["earliest"] >= cut: supply = "供给早期"
        else: supply = "已有供给" + (f"（近90天新进 {ss['n_recent']}）" if ss["n_recent"] >= 3 else "")
    out[c] = {"demand": demand, "supply": supply}

# 5. 第 3 轮：Google Trends（新产品 / 缺口 / 早期里排在前面的 N 个）
# 只查最后排在前面的 N 个词簇（排序和导出表一致：缺口 > 早期 > 可能缺口 > 其他，再按同簇词数、最好排名）
SUPPRI = {"供给缺口": 0, "供给早期": 1}
spri = lambda o: SUPPRI.get(o["supply"], 2 if o["supply"].startswith("可能缺口") else 3)
gq = [c for c, o in out.items() if o["demand"] in ("新产品", "旧产品新属性") or o["supply"] in ("供给缺口", "供给早期")]
gq = sorted(gq, key=lambda c: (spri(out[c]), -len(sel[c]), min(int(r["searchRank"]) for r in sel[c])))[:int(A.CFG.get("google_top_n", 30))]
print(f"Google Trends 查前 {len(gq)} 个词簇")
gcall = lambda q: A.fmt("sellersprite-mcp", "google_trend", {"request": {"marketplace": A.CFG["marketplace"], "keyword": q, "googleProp": "web"}})
res3 = pull("sup3", [gcall(rep[c]) for c in gq])
for c in gq:
    b = res3.get(json.dumps(A.parse_line(gcall(rep[c]))[2], sort_keys=True))
    vals = [it["value"] for it in ((b or {}).get("data") or {}).get("items") or []]
    if not vals or max(vals[-52:] or [0]) == 0:
        phase = "无热度"
    else:
        y, l4, p4, l8 = vals[-52:], sum(vals[-4:]) / 4, sum(vals[-8:-4]) / 4, sum(vals[-8:]) / 8
        mx = max(y)
        phase = "上升" if l4 > max(p4 * 1.3, 0.3 * mx) else ("回落" if l8 < 0.4 * mx else "平稳")
        out[c]["g_peak"] = (datetime.fromtimestamp(((b["data"]["items"])[-52:][y.index(mx)]["time"]) / 1000)).strftime("%Y-%m")
    out[c]["google"] = phase

# 6. 输出
with open(WORK / "clusters.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["cluster", "rep", "n_words", "demand", "supply", "google", "g_peak", "rep_total", "rep_rel", "rep_earliest", "rep_recent", "core_rel", "core_earliest"])
    for c in sel:
        rs, cs, o = rep_st.get(c) or {}, core_st.get(c) or {}, out[c]
        w.writerow([c, rep[c], len(sel[c]), o["demand"], o["supply"], o.get("google", ""), o.get("g_peak", ""), rs.get("total"), rs.get("n_rel"), rs.get("earliest"), rs.get("n_recent"), cs.get("n_rel"), cs.get("earliest")])
with open(WORK / "supply.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["keyword", "src", "cluster", "demand", "supply", "google", "g_peak", "rep_earliest", "rep_rel"])
    for c, v in clusters.items():
        o = out.get(c, {"demand": "未查（单个飙升词）", "supply": ""}); rs = rep_st.get(c) or {}
        for r in v: w.writerow([r["keyword"], r["src"], c, o["demand"], o["supply"], o.get("google", ""), o.get("g_peak", ""), rs.get("earliest", ""), rs.get("n_rel", "")])
from collections import Counter
print(json.dumps({"需求类型": Counter(o["demand"] for o in out.values()), "供给": Counter(o["supply"] for o in out.values()),
                  "Google": Counter(o.get("google", "") for o in out.values())}, ensure_ascii=False))
