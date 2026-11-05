#!/usr/bin/env python3
"""站外热点雷达：在商品词进 ABA 之前发现它。
用法:
  PULLER=cb radar.py RUN                         每周雷达（亚马逊下拉新词 + TikTok Shop 新品 → 抽商品名 → Google → 亚马逊）
  PULLER=cb radar.py RUN --words "knightcat,fat trimmer"   单词核查（只查给的词，可和雷达一起跑）
  PULLER=cb radar.py RUN --words-only --words "..."         只做单词核查
  RUN：data/<日期> 之类的目录。中途停了重跑同一条命令即可，已拉到的复用。
PULLER：cb=CodeBuddy hy3（默认），agy=Gemini Flash，oc=DeepSeek。拉数复用 mj-aba-trend-discovery 的读取函数。
输出 RUN/radar.csv、RUN/radar.xlsx，只打印统计。"""
import csv, json, os, re, statistics, string, subprocess, sys, time, urllib.parse, urllib.request
from datetime import datetime, timedelta
from pathlib import Path

os.environ.setdefault("PULLER", "cb")
ABA = Path.home() / ".claude/skills/mj-aba-trend-discovery/scripts"
sys.path.insert(0, str(ABA))
import aba_trend as A  # fmt / parse_line / pulled
from agylib import agy_jsonl

SKILL = Path(__file__).resolve().parent.parent
CFG = json.loads((SKILL / "config.json").read_text())
BO = Path.home() / ".claude/skills/batch-offload/scripts"
args = sys.argv[1:]
RUN = Path(args[0]).resolve(); RUN.mkdir(parents=True, exist_ok=True)
WORDS = []
if "--words" in args:
    WORDS = [w.strip() for w in args[args.index("--words") + 1].split(",") if w.strip()]
WORDS_ONLY = "--words-only" in args
TODAY = datetime.now()
MK = CFG["marketplace"]
DATA = SKILL / "data"
norm = lambda s: " ".join(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w for w in re.sub(r"[^a-z0-9 ]", " ", s.lower()).split())
key = lambda line: json.dumps(A.parse_line(line)[2], sort_keys=True)


def run_puller(calls, out):
    p = os.environ["PULLER"]
    script = {"cb": "cb_pull.sh", "agy": "agy_pull.sh"}.get(p, "oc_pull.sh")
    cmd = [str(BO / script), str(calls), str(out)] + (["gemini-3.8-flash-low"] if p == "agy" else ["5"] if p == "cb" else [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    return (r.stdout.strip().splitlines() or [""])[-1]


def pull(tag, lines):
    """跑一轮调用，返回 {参数 JSON: 返回体}。已拉到的复用，缺的行补跑最多 3 次。非 JSON 返回（No data available）记为 None。"""
    lines = list(dict.fromkeys(lines))
    if not lines: return {}
    def collect():
        res = {}
        for d in sorted(RUN.glob(f"{tag}_pull")) + sorted(RUN.glob(f"{tag}_r*_pull")):
            if not (d / "index.json").exists(): continue
            for e, body in A.pulled(RUN, d.name):
                k = json.dumps(e["args"], sort_keys=True)
                if body is not None or k not in res: res[k] = body
        return res
    if not (RUN / f"{tag}_pull" / "index.json").exists():  # 已拉过就不覆盖原清单，否则行号对不上
        (RUN / f"{tag}_calls.txt").write_text("\n".join(lines) + "\n")
    if not (RUN / f"{tag}_pull" / "index.json").exists():
        print(tag, run_puller(RUN / f"{tag}_calls.txt", RUN / f"{tag}_pull"), flush=True)
    for n in range(1, 4):
        res = collect()
        miss = [l for l in lines if key(l) not in res]
        if not miss: break
        rt = f"{tag}_r{n}"
        (RUN / f"{rt}_calls.txt").write_text("\n".join(miss) + "\n")
        print(rt, f"补跑 {len(miss)} 行:", run_puller(RUN / f"{rt}_calls.txt", RUN / f"{rt}_pull"), flush=True)
    return collect()


# ---------- 1. 亚马逊下拉联想快照（免费直连，不经过模型） ----------
def suggest(prefix):
    url = "https://completion.amazon.com/api/2017/suggestions?" + urllib.parse.urlencode({"mid": "ATVPDKIKX0DER", "alias": "aps", "prefix": prefix})
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for _ in range(3):
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return [s["value"] for s in json.load(r).get("suggestions", []) if s.get("type") == "KEYWORD"]
        except Exception:
            time.sleep(3)
    return None


cands = []  # {src, text, extra}
if not WORDS_ONLY:
    snap = RUN / "suggest.json"
    if not snap.exists():
        got = {}
        for sd in CFG["seeds"]:
            for ch in [""] + list(string.ascii_lowercase):
                p = f"{sd} {ch}".strip()
                got[p] = suggest(p); time.sleep(CFG["suggest_sleep"])
        snap.write_text(json.dumps(got, ensure_ascii=False))
    got = json.loads(snap.read_text())
    seen_f = DATA / "suggest_seen.json"
    base_f = RUN / "suggest_base.json"  # 本周合并前的累计集合，中途重跑也用它比对
    if not base_f.exists():
        base_f.write_text(seen_f.read_text() if seen_f.exists() else "[]")
    seen_s = set(json.loads(base_f.read_text()))
    seen_all = set(json.loads(seen_f.read_text())) if seen_f.exists() else set()
    now_s = {v for vs in got.values() if vs for v in vs}
    fails = sum(1 for v in got.values() if v is None)
    if seen_s:
        new_s = sorted(now_s - seen_s)
        cands += [{"src": "suggest", "text": v} for v in new_s]
        print(f"下拉联想：{len(got)} 个前缀，失败 {fails}，本周新出现 {len(new_s)} 个")
    else:
        print(f"下拉联想：{len(got)} 个前缀，失败 {fails}，第一次跑只建基线（{len(now_s)} 个词），下周起比对新词")
    if not (RUN / ".suggest_merged").exists():
        seen_f.write_text(json.dumps(sorted(seen_all | now_s), ensure_ascii=False)); (RUN / ".suggest_merged").touch()

    # ---------- 2. TikTok Shop 近期新品（只当词源，不看销量高低） ----------
    since = (TODAY - timedelta(days=CFG["tiktok_exposure_days"])).strftime("%Y-%m-%d")
    tt_lines = [A.fmt("sorftime-mcp", "tiktok_product_search", {"site": "US", "exposure_time_min": since, "weekly_sale_count_min": CFG["tiktok_weekly_sale_min"], "page": p})
                for p in range(1, CFG["tiktok_pages"] + 1)]
    res = pull("tt", tt_lines)
    n_tt = 0
    for l in tt_lines:
        b = res.get(key(l)) or {}
        for it in (b.get("data") if isinstance(b.get("data"), list) else []):
            cat = re.search(r"'name': '([^']+)'", str(it.get("category", "")))
            cat = cat.group(1) if cat else ""
            if any(x.lower() in cat.lower() for x in CFG["tiktok_exclude_categories"]): continue
            cands.append({"src": "tiktok", "text": it["product_name"][:150], "extra": f"{cat}｜周销 {it.get('weekly_sale_count')}｜视频 {it.get('video_count')}｜曝光 {it.get('exposure_time')}"}); n_tt += 1
    print(f"TikTok Shop：保留实物类目新品 {n_tt} 个")

cands += [{"src": "manual", "text": w} for w in WORDS]

# ---------- 3. Flash 抽商品名、分类 ----------
cache = RUN / "extract.jsonl"; ext = {}
if cache.exists():
    for l in open(cache): o = json.loads(l); ext[(o["src"], o["text"])] = o
todo = [c for c in cands if (c["src"], c["text"]) not in ext]
for i in range(0, len(todo), 200):
    chunk = todo[i:i + 200]
    out = agy_jsonl(SKILL / "references/extract_prompt.txt", {str(j): f"{c['src']}\t{c['text']}" for j, c in enumerate(chunk)}, key="type")
    with open(cache, "a") as f:
        for j, c in enumerate(chunk):
            o = out.get(str(j))
            if not o: continue
            o.update(src=c["src"], text=c["text"]); ext[(c["src"], c["text"])] = o
            f.write(json.dumps(o, ensure_ascii=False) + "\n")

seen_f = DATA / "seen.json"
seen = json.loads(seen_f.read_text()) if seen_f.exists() else {}
recheck = (TODAY - timedelta(days=CFG["recheck_days"])).strftime("%Y-%m-%d")
names, skipped = {}, {"非实物/节日": 0, "不新奇": 0, "近期查过": 0}
for c in cands:
    o = ext.get((c["src"], c["text"]))
    if not o: continue
    n = norm(o["name"])
    if not n: continue
    if c["src"] != "manual":
        if o["type"] != "实物功能": skipped["非实物/节日"] += 1; continue
        if not o.get("novel"): skipped["不新奇"] += 1; continue
        if seen.get(n, "") > recheck: skipped["近期查过"] += 1; continue
    e = names.setdefault(n, {"name": n, "src": set(), "type": o["type"], "note": o.get("note", ""), "q": [n], "extra": []})
    e["src"].add(c["src"])
    if c.get("extra"): e["extra"].append(c["extra"])
    if c["src"] == "manual":
        e["type"], e["note"] = o["type"], o.get("note", "")
        e["q"] = list(dict.fromkeys([norm(c["text"])] + [norm(v) for v in o.get("variants") or []] + [n]))[:4]
pri = lambda e: (0 if "manual" in e["src"] else 1 if "tiktok" in e["src"] else 2, -len(e["extra"]))
sel = sorted(names.values(), key=pri)
manual = [e for e in sel if "manual" in e["src"]]
sel = manual + [e for e in sel if "manual" not in e["src"]][:max(0, CFG["google_max"] - len(manual))]
print(f"候选商品名 {len(names)} 个（跳过 {skipped}），查 Google {len(sel)} 个")

# ---------- 4. Google Trends ----------
gcall = lambda q: A.fmt("sellersprite-mcp", "google_trend", {"request": {"marketplace": MK, "keyword": q, "googleProp": "web"}})
gres = pull("g", [gcall(q) for e in sel for q in e["q"]])


def gphase(b):
    items = ((b or {}).get("data") or {}).get("items") or []
    v = [it["value"] for it in items]
    if len(v) < 20 or max(v[-52:]) == 0: return "无热度", "", 0
    y = v[-52:]; mx = max(y); l4 = sum(v[-4:]) / 4
    base = statistics.median(v[-16:-4]) or 0.5
    pk = datetime.fromtimestamp(items[-52:][y.index(mx)]["time"] / 1000)
    persist = sum(1 for x in v[-4:] if x >= 1.5 * base) >= 3  # 持续 3 周以上，不是一周脉冲
    if l4 >= CFG["google_rise_ratio"] * base and l4 >= CFG["google_rise_peak_share"] * mx and persist: ph = "上升"
    elif mx >= 2 * statistics.median(y) and l4 < CFG["google_fall_share"] * mx and (TODAY - pk).days > 28: ph = "已回落"
    else: ph = "平稳"
    return ph, pk.strftime("%Y-%m"), round(mx / (statistics.median(y) or 0.5), 1)


ORDER = {"上升": 0, "已回落": 1, "平稳": 2, "无热度": 3}
for e in sel:
    best = min(((q,) + gphase(gres.get(key(gcall(q)))) for q in e["q"]), key=lambda t: (ORDER[t[1]], -t[3]))
    e["gq"], e["google"], e["g_peak"], e["g_lift"] = best

# ---------- 5. 亚马逊：ABA 历史、商品上架日期、下拉是否已有（只查上升的和用户给的词） ----------
deep = [e for e in sel if e["google"] == "上升" or "manual" in e["src"]]
aq = lambda e: e["gq"] if e["google"] != "无热度" else e["q"][0]
acall = lambda q: A.fmt("sellersprite-mcp", "aba_research_trend", {"marketplace": MK, "keyword": q, "timeGranularity": "W"})
lcall = lambda q: A.fmt("sellersprite-mcp", "competitor_lookup", {"request": {"marketplace": MK, "keyword": q, "matchType": 1, "order": {"field": "total_units", "desc": True},
                                                                   "size": 20, "variation": "Y", "returnFields": "asin,title,availableDate,ratings,price"}})
ares = pull("a", [c(aq(e)) for e in deep for c in (acall, lcall)])
pairs = []
for e in deep:
    q = aq(e)
    b = ares.get(key(acall(q))) or {}
    weeks = [w for w in (b.get("data") or []) if w.get("rank")]
    e["aba_first"] = weeks[0]["label"] if weeks else ""
    e["aba_last"] = (weeks[-1]["label"], weeks[-1]["rank"]) if weeks else ("", "")
    b = ares.get(key(lcall(q))) or {}
    e["items"] = ((b.get("data") or {}).get("items")) or []
    e["total"] = (b.get("data") or {}).get("total", 0) if b else 0
    pairs += [(q, it["title"][:150]) for it in e["items"] if it.get("title")]
    sg = suggest(q) or []
    e["in_suggest"] = any(norm(s) == norm(q) or norm(s).startswith(norm(q) + " ") for s in sg)

tcache = RUN / "titles.jsonl"; tj = {}
if tcache.exists():
    for l in open(tcache): o = json.loads(l); tj[(o["q"], o["t"])] = o
todo = [p for p in dict.fromkeys(pairs) if p not in tj]
for i in range(0, len(todo), 250):
    chunk = todo[i:i + 250]
    out = agy_jsonl(SKILL / "references/title_prompt.txt", {str(j): f"{q}\t{t}" for j, (q, t) in enumerate(chunk)}, key="rel")
    with open(tcache, "a") as f:
        for j, (q, t) in enumerate(chunk):
            o = out.get(str(j))
            if not o: continue
            r = {"q": q, "t": t, "rel": int(o.get("rel", 0)), "pod": int(o.get("pod", 0))}; tj[(q, t)] = r
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

# ---------- 6. 阶段判定 ----------
young = (TODAY - timedelta(days=CFG["supply_young_days"]))
recent8 = (TODAY - timedelta(days=60)).strftime("%Y%m%d")
for e in sel:
    if e not in deep:
        e["stage"] = "TikTok先行（Google未起）" if "tiktok" in e["src"] and e["google"] in ("平稳", "无热度") else {"已回落": "已回落"}.get(e["google"], "观察"); continue
    q = aq(e)
    js = [(it, tj.get((q, it["title"][:150]), {})) for it in e["items"] if it.get("title")]
    func = [it for it, j in js if j.get("rel") == 1 and not j.get("pod")]
    pod = sum(1 for _, j in js if j.get("pod"))
    dates = sorted(datetime.fromtimestamp(it["availableDate"] / 1000) for it in func if it.get("availableDate"))
    e["n_func"], e["n_pod"] = len(func), pod
    e["func_first"] = dates[0].strftime("%Y-%m-%d") if dates else ""
    e["func_young"] = sum(1 for d in dates if d >= young)
    e["func_30d"] = sum(1 for d in dates if d >= TODAY - timedelta(days=30))
    if e["type"] in ("梗周边", "品牌IP", "非商品") or (js and pod / len(js) >= CFG["pod_share"] and len(func) < 3):
        e["stage"] = "梗/IP 伪机会"
    elif e["aba_last"][0] and e["aba_last"][0] >= recent8:
        e["stage"] = "已进ABA（交给 mj-aba-trend-discovery）"
    elif e["google"] == "已回落":
        e["stage"] = "已回落"
    elif e["func_30d"] >= CFG["overheat_new_30d"]:
        e["stage"] = "已过热"  # 一个月内涌进 10 个以上对口新品，抢跑窗口已关
    elif e["google"] == "上升" and (len(func) < CFG["supply_few"] or e["func_young"] == len(func)):
        e["stage"] = "抢跑窗口"
    elif len(func) >= CFG["supply_few"]:
        e["stage"] = "已有供给"
    else:
        e["stage"] = "观察"

SORDER = {"抢跑窗口": 0, "TikTok先行（Google未起）": 1, "已进ABA（交给 mj-aba-trend-discovery）": 2, "观察": 3, "已过热": 4, "已有供给": 5, "已回落": 6, "梗/IP 伪机会": 7}
sel.sort(key=lambda e: (SORDER.get(e["stage"], 9), ORDER[e["google"]], -e["g_lift"]))
HDR = [("阶段", "stage"), ("商品名", "name"), ("来源", "src"), ("类型", "type"), ("说明", "note"), ("Google查询词", "gq"), ("Google热度", "google"), ("Google峰值月", "g_peak"),
       ("峰值/中位数", "g_lift"), ("ABA首次进榜周", "aba_first"), ("ABA最近", "aba_last"), ("亚马逊下拉已有", "in_suggest"), ("词组匹配商品数", "total"),
       ("对口功能商品(前20)", "n_func"), ("其中半年内上架", "func_young"), ("其中30天内上架", "func_30d"), ("最早对口上架", "func_first"), ("印花周边(前20)", "n_pod"), ("TikTok信息", "extra")]


def cell(e, k):
    v = e.get(k, "")
    if k == "src": return "/".join(sorted(v))
    if k == "aba_last": return f"{v[0]} #{v[1]}" if v and v[0] else ""
    if k == "extra": return "；".join(v[:2])
    if k == "in_suggest": return "" if e not in deep else ("是" if v else "否")
    return v


with open(RUN / "radar.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow([h for h, _ in HDR])
    for e in sel: w.writerow([cell(e, k) for _, k in HDR])
try:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    wb = Workbook(); ws = wb.active; ws.title = "站外雷达"
    ws.append([h for h, _ in HDR])
    for e in sel: ws.append([cell(e, k) for _, k in HDR])
    for c in ws[1]: c.font = Font(bold=True); c.fill = PatternFill("solid", fgColor="DDEBF7")
    for col, wd in zip("ABCDEFGHIJKLMNOPQRS", [18, 26, 12, 10, 30, 22, 10, 11, 10, 12, 16, 10, 10, 12, 10, 10, 12, 10, 50]):
        ws.column_dimensions[col].width = wd
    for row in ws.iter_rows(min_row=2):
        for c in row: c.alignment = Alignment(wrap_text=True, vertical="top")
        if row[0].value == "抢跑窗口": row[0].fill = PatternFill("solid", fgColor="C6EFCE")
    ws.freeze_panes = "C2"; ws.auto_filter.ref = ws.dimensions
    wb.save(RUN / "radar.xlsx")
except ImportError:
    pass

for e in sel:
    if "manual" not in e["src"] and not e["stage"].startswith("TikTok先行"): seen[e["name"]] = TODAY.strftime("%Y-%m-%d")
seen_f.write_text(json.dumps(seen, ensure_ascii=False))
from collections import Counter
print(json.dumps({"查了": len(sel), "深查": len(deep), "阶段": Counter(e["stage"] for e in sel), "Google": Counter(e["google"] for e in sel)}, ensure_ascii=False))
for e in sel:
    if "manual" in e["src"] or e["stage"] == "抢跑窗口":
        print(" ", e["stage"], "|", e["name"], "|", e["gq"], e["google"], e["g_peak"], "| ABA", e.get("aba_first", ""), "| 功能", e.get("n_func", ""), "印花", e.get("n_pod", ""), "|", e["note"][:40])
