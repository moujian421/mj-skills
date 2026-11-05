#!/usr/bin/env python3
"""把多个 RUN 的保留词 / 剔除词合并成一个 xlsx。
用法: export_xlsx.py OUT.xlsx RUN [RUN ...] [--supply=WORK/supply.csv ...]
--supply：supply.py 的结果，加上需求类型、供给、Google 热度、最早对口商品上架日期，词簇改用核心词，供给缺口/早期排最前。
保留词优先读 candidates_classified.csv（有需求类型），没有就读 candidates_clean.csv + core_tags.jsonl（需求类型=待核实）。
同一个词出现在多个 RUN 时合并成一行，“来源”列列出全部。词簇在合并后的保留词里重算。"""
import csv, json, re, sys
from collections import defaultdict
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

args = sys.argv[1:]
sup_files = [Path(a.split("=", 1)[1]) for a in args if a.startswith("--supply=")]
args = [a for a in args if not a.startswith("--supply=")]
out, runs = args[0], [Path(p).resolve() for p in args[1:]]
SUP = {}
for f in sup_files:
    for r in csv.DictReader(open(f)): SUP[r["keyword"]] = r
label = lambda run: (lambda d: f"{d[:4]}-{d[4:6]} 月" if len(d) == 6 else f"{d[:4]}-{d[4:6]}-{d[6:]} 周")(json.loads((run / "meta.json").read_text())["date"])
keep, rem = {}, {}
for run in runs:
    src = label(run)
    cls = run / "candidates_classified.csv"
    if cls.exists():
        rows = list(csv.DictReader(open(cls)))
    else:
        rows = list(csv.DictReader(open(run / "candidates_clean.csv"))) if (run / "candidates_clean.csv").exists() else []
        tags = {}
        if (run / "core_tags.jsonl").exists():
            for l in open(run / "core_tags.jsonl"):
                o = json.loads(l); tags[o.get("keyword", o["id"])] = o
        for i, r in enumerate(rows):
            o = tags.get(r["keyword"], {}); r["core"], r["attr"], r["demand_type"] = o.get("core", ""), o.get("attr", ""), "待核实"
    for r in rows:
        k = r["keyword"]
        if k in keep: keep[k]["src"].append(src)
        else: r["src"] = [src]; keep[k] = r
    if (run / "candidates_removed.csv").exists():
        for r in csv.DictReader(open(run / "candidates_removed.csv")):
            if r["keyword"] in keep: continue
            if r["keyword"] in rem: rem[r["keyword"]]["src"].append(src)
            else: r["src"] = [src]; rem[r["keyword"]] = r
for k in list(rem):
    if k in keep: rem.pop(k)
keep, rem = list(keep.values()), list(rem.values())
for r in keep:
    s = SUP.get(r["keyword"])
    if s:
        r["demand_type"], r["supply"], r["google"], r["g_peak"], r["rep_earliest"], r["cluster_core"] = s["demand"], s["supply"], s["google"], s["g_peak"], s["rep_earliest"], s["cluster"]
STOP = {"for","and","with","the","a","an","of","to","in","on","&","men","women","mens","womens","kids","girls","boys","adults","set","pack","small","large","mini","best","new"}
def bgs(k):
    tk = [t[:-1] if len(t) > 3 and t.endswith("s") and not t.endswith("ss") else t for t in re.findall(r"[a-z0-9']+", k.lower()) if t not in STOP]
    return {" ".join(tk[i:i+2]) for i in range(len(tk)-1)} or set(tk)
bw = defaultdict(set)
for r in keep:
    r["_b"] = bgs(r["keyword"])
    for b in r["_b"]: bw[b].add(r["keyword"])
for r in keep:
    b = max(r["_b"], key=lambda x: (len(bw[x]), x)); r["cluster"], r["cluster_size"] = b, str(len(bw[b]))
cc = defaultdict(int)
for r in keep:
    if r.get("cluster_core"): cc[r["cluster_core"]] += 1
for r in keep:
    if r.get("cluster_core"): r["cluster"], r["cluster_size"] = r["cluster_core"], str(cc[r["cluster_core"]])
SUPPRI = {"供给缺口": 0, "供给早期": 1}
pri = {"新词": 0, "月度新词": 0, "回归词": 1, "飙升词": 2}
keep.sort(key=lambda r: (SUPPRI.get(r.get("supply", ""), 2), -int(r["cluster_size"]), r["cluster"], pri.get(r["type"], 3), int(r["searchRank"])))
TAGCN = {"brand":"品牌词","ip":"IP/图书/名人","sports":"球队赛事","risk":"高风险","holiday":"节日季节","junk":"无效词"}
hdr = [("词簇","cluster"),("同簇词数","cluster_size"),("关键词","keyword"),("需求类型","demand_type"),("供给","supply"),("Google热度","google"),("Google峰值月","g_peak"),("最早对口商品上架","rep_earliest"),("产品核心词","core"),("新属性","attr"),
       ("来源","src"),("类型","type"),("本周/月排名","searchRank"),("1周前","w1SearchRank"),("4周前","w4SearchRank"),("12周前","w12SearchRank"),
       ("搜索量","searches"),("购买量","purchases"),("类目","departments"),("第1名点击占比","top1_click"),("第1名ASIN","top1_asin"),("去年同期最好排名","ly_peak")]
num = {"cluster_size","searchRank","w1SearchRank","w4SearchRank","w12SearchRank","searches","purchases","ly_peak","core_weeks"}
def conv(k, v):
    if k == "src": return " / ".join(v)
    if v in ("", "None", None): return None
    if k in num: return int(float(v))
    if k == "top1_click": return round(float(v), 3)
    if k == "departments": return v.replace("|", " / ")
    return v
def sheet(ws, rows, cols):
    ws.append([a for a, _ in cols])
    for r in rows: ws.append([conv(k, r.get(k)) for _, k in cols])
    for c in ws[1]: c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="305496"); c.alignment = Alignment(horizontal="center", wrap_text=True)
    W = {"词簇":20,"关键词":44,"产品核心词":22,"新属性":18,"来源":22,"类目":30,"剔除原因":12,"说明":14,"供给":20,"需求类型":12,"最早对口商品上架":14}
    for i, (a, k) in enumerate(cols, 1):
        ws.column_dimensions[get_column_letter(i)].width = W.get(a, 11)
        if k == "top1_click":
            for row in ws.iter_rows(min_row=2, min_col=i, max_col=i):
                for c in row: c.number_format = "0.0%"
    kc = [k for _, k in cols].index("keyword") + 2
    ws.freeze_panes = ws.cell(row=2, column=kc); ws.auto_filter.ref = ws.dimensions
wb = Workbook(); ws = wb.active; ws.title = f"保留 {len(keep)}"
sheet(ws, keep, hdr)
for r in rem: r["tagcn"] = TAGCN.get(r.get("tag"), r.get("tag"))
rem.sort(key=lambda r: (r["tagcn"] or "", r["keyword"]))
rc = [("剔除原因","tagcn"),("说明","why")] + [h for h in hdr if h[1] not in ("cluster","cluster_size","demand_type","core","attr","supply","google","g_peak","rep_earliest")]
sheet(wb.create_sheet(f"已剔除 {len(rem)}"), rem, rc)
wb.save(out)
from collections import Counter
print(json.dumps({"保留": len(keep), "剔除": len(rem), "需求类型": Counter(r["demand_type"] for r in keep), "供给": Counter(r.get("supply", "") for r in keep)}, ensure_ascii=False))
