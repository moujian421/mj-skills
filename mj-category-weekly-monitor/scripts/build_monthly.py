"""Build the two monthly tabs (大盘月度 / 核心词月度) as write_tab specs.
Usage: python3 build_monthly.py --config CFG --run RUN --month YYYY-MM --ss SS_PULL_DIR --xy XY_PULL_DIR
        --sorftime SORFTIME.json --glance GLANCE.json --date YYYY-MM-DD [--market-note TEXT] [--kw-note TEXT]
SORFTIME.json: {"SalesCount": [...category_trend data...], "AvgPrice": [...]} (strings "yyyy-MM=N")
GLANCE.json:   the items list of market_product_demand_trend ([{"date":"2025-08-01","glanceViews":N}, ...])
SS pull: market_research_statistics in month order (as written by make_calls.py market_ss); a month missing from
  the pull (tool error) can be added as SS_PULL_DIR/fix_YYYYMM.json holding the tool's data object."""
import json, glob, os, sys, argparse
sys.path.insert(0, os.path.dirname(__file__))
from cfg import load_cfg
ap = argparse.ArgumentParser()
for k in ["config", "run", "month", "ss", "xy", "sorftime", "glance", "date"]: ap.add_argument("--" + k, required=True)
ap.add_argument("--market-note", default=""); ap.add_argument("--kw-note", default=""); A = ap.parse_args()
cfg = load_cfg(A.config)
y, m = map(int, A.month.split("-")); months = []
for _ in range(24):
    months.append((y, m)); m -= 1
    if m == 0: y, m = y - 1, 12
months = months[::-1]
# SellerSprite (index file keeps call order)
ss = {}
# main pull plus agy retry folders (retry/, retry2/ ...): any raw/index.json under --ss
for ip in sorted(glob.glob(os.path.join(A.ss, "**", "raw", "index.json"), recursive=True)):
    for e in json.load(open(ip)):
        if e["tool"] != "market_research_statistics" or e.get("error"): continue
        try: d = json.load(open(os.path.join(os.path.dirname(ip), e["file"])))
        except Exception: continue
        if isinstance(d, dict) and d.get("code") not in (None, "OK"): continue
        ss[e["args"]["request"]["month"]] = d.get("data", d)
for f in glob.glob(os.path.join(A.ss, "fix_*.json")):
    ss[os.path.basename(f)[4:10]] = json.load(open(f))
miss = [f"{y}{m:02d}" for y, m in months if f"{y}{m:02d}" not in ss]
if miss: sys.exit(f"SellerSprite months missing: {miss} -> rerun or save fix_YYYYMM.json")
gv = {(int(x["date"][:4]), int(x["date"][5:7])): x["glanceViews"] for x in json.load(open(A.glance))}
sf = json.load(open(A.sorftime))
sfu = {tuple(map(int, x.split("=")[0].split("-"))): int(x.split("=")[1]) for x in sf["SalesCount"]}
sfp = {tuple(map(int, x.split("=")[0].split("-"))): float(x.split("=")[1]) for x in sf["AvgPrice"]}
xyf = sorted(glob.glob(os.path.join(A.xy, "**", "raw", "get_category_market_size_trends_*.json"), recursive=True))[0]
xy = {(int(t["localDate"][:4]), int(t["localDate"][5:7])): (t["sales"]["value"], float(t["salesRevenue"]["value"])) for t in json.load(open(xyf))["data"]["trends"]}
xc = cfg["xiyou"]
hdr1 = ["月份", f"卖家精灵 · 子类 {cfg['category_name']} 头部100", "", "", "", "", "", "Sorftime · 同子类 头部100", "", "", f"西柚 · {xc['categoryName']} 全类目", ""]
hdr2 = ["", "销量（件）", "销售额（USD）", "均价（USD）", "品牌数", "新品数", "类目浏览量", "销量（件）", "均价（USD）", "估算销售额（USD）", "销量（件）", "销售额（USD）"]
data = []
for (y, m) in months:
    d = ss[f"{y}{m:02d}"]; p = d.get("products") or 100
    data.append([f"{y}年{m}月", round(d["avgUnits"] * p), round(d["avgRevenue"] * p), d["avgPrice"], d["brands"], d["newProducts"], gv.get((y, m), "—"),
                 sfu.get((y, m), "—"), sfp.get((y, m), "—"), round(sfu[(y, m)] * sfp[(y, m)]) if (y, m) in sfu and (y, m) in sfp else "—",
                 xy.get((y, m), ("—",))[0], round(xy[(y, m)][1]) if (y, m) in xy else "—"])
num = lambda v: isinstance(v, (int, float))
def tot(rs, c): return sum(r[c] for r in rs if num(r[c]))
cur, prev = data[12:], data[:12]
r1 = [f"近12个月合计（{months[12][0]%100}年{months[12][1]}月~{months[23][0]%100}年{months[23][1]}月）"] + [""] * 11
r2 = [f"上年同期（{months[0][0]%100}年{months[0][1]}月~{months[11][0]%100}年{months[11][1]}月）"] + [""] * 11
r3 = ["同比"] + [""] * 11
for c in [1, 2, 7, 9, 10, 11]:
    a, b = tot(cur, c), tot(prev, c); r1[c], r2[c] = a, b; r3[c] = a / b - 1 if b else "—"
# anomaly: SellerSprite jumps that the other two sources do not show (variation sales counted per child)
yellow = []
for i in range(1, 24):
    def mom(c): return data[i][c] / data[i - 1][c] - 1 if num(data[i][c]) and num(data[i - 1][c]) and data[i - 1][c] else 0
    if mom(1) >= 0.5 and mom(7) <= 0.15 and mom(10) <= 0.15: yellow.append(i + 3)
st = [{"range": "A1:L2", "font_weight": "bold", "font_size": 13, "horizontal_alignment": "center", "vertical_alignment": "middle", "word_wrap": "auto-wrap"},
      {"range": "A1:A2", "background_color": "#404040", "font_color": "#FFFFFF"},
      {"range": "B1:G1", "background_color": "#1F4E79", "font_color": "#FFFFFF"}, {"range": "B2:G2", "background_color": "#DDEBF7", "font_color": "#1F4E79"},
      {"range": "H1:J1", "background_color": "#375623", "font_color": "#FFFFFF"}, {"range": "H2:J2", "background_color": "#E2EFDA", "font_color": "#375623"},
      {"range": "K1:L1", "background_color": "#833C0B", "font_color": "#FFFFFF"}, {"range": "K2:L2", "background_color": "#FCE4D6", "font_color": "#833C0B"},
      {"range": "A3:L29", "vertical_alignment": "middle", "horizontal_alignment": "right"}, {"range": "A3:A29", "horizontal_alignment": "left"},
      {"range": "B3:B28", "number_format": "#,##0"}, {"range": "H3:H28", "number_format": "#,##0"}, {"range": "K3:K28", "number_format": "#,##0"}, {"range": "G3:G26", "number_format": "#,##0"},
      {"range": "C3:C28", "number_format": "$#,##0"}, {"range": "J3:J28", "number_format": "$#,##0"}, {"range": "L3:L28", "number_format": "$#,##0"},
      {"range": "D3:D26", "number_format": "$0.00"}, {"range": "I3:I26", "number_format": "$0.00"}, {"range": "E3:F26", "horizontal_alignment": "center"},
      {"range": "A27:L29", "background_color": "#F2F2F2", "font_weight": "bold"}, {"range": "B29:L29", "number_format": "0.0%"}]
for i, r in enumerate(data, 3):
    if r[6] == "—": st.append({"range": f"G{i}", "font_color": "#A6A6A6", "horizontal_alignment": "center"})
for c, L in ((1, "B"), (7, "H"), (10, "K")):
    vals = [(r[c], i) for i, r in enumerate(data, 3) if num(r[c]) and not (c == 1 and i in yellow)]
    if vals: st.append({"range": f"{L}{max(vals)[1]}", "background_color": "#C6EFCE", "font_weight": "bold"})
for i in yellow: st.append({"range": f"B{i}:C{i}", "background_color": "#FFF2CC"})
ylab = "、".join(data[i - 3][0] for i in yellow)
foot = (f"说明：{cfg['marketplace']} 站，{months[0][0]}年{months[0][1]}月~{months[23][0]}年{months[23][1]}月月度数据（当月未满不列）。卖家精灵与 Sorftime 为同一亚马逊子类（节点 {cfg['node_id']}）头部100商品的月度合计；"
        "卖家精灵类目浏览量为 glance views（'—'=无数据）；卖家精灵、Sorftime 的均价为头部100商品标价的简单平均；Sorftime 销售额=月销量×月均价，为估算。"
        f"西柚为其自建类目 {xc['categoryName']} 全类目口径，范围与另两家不同，不能直接相加。"
        + (f"黄色底=卖家精灵 {ylab} 销量突增而 Sorftime、西柚没有同步上涨，疑似同一产品多条链接各自计入父体销量被重复累加，看走势以 Sorftime、西柚为准。" if yellow else "")
        + "绿色加粗=该列销量最高的月份。" + A.market_note + f"拉取日期 {A.date}。")
market = {"tab": cfg["sheet"]["tabs"]["market"], "header": [hdr1, hdr2], "rows": data + [r1, r2, r3], "footer": foot, "ncols": 12,
          "styles": st, "merges": [{"range": "A1:A2"}, {"range": "B1:G1"}, {"range": "H1:J1"}, {"range": "K1:L1"}],
          "col_sizes": [{"range": "A:A", "size": 200}, {"range": "B:L", "size": 110}], "row_height": 27, "footer_height": 130,
          "freeze": {"rows": 2, "cols": 1}, "check_col": 0}
json.dump(market, open(os.path.join(A.run, "spec_market.json"), "w"), ensure_ascii=False)
# keywords
kf = sorted(glob.glob(os.path.join(A.xy, "**", "raw", "get_category_keywords_*.json"), recursive=True))[0]
by = {x["searchTerm"]: x for x in json.load(open(kf))["data"]["list"]}
ms = [f"{y}-{m:02d}-01" for y, m in months[::-1]]; lab = lambda s: f"{s[2:4]}年{int(s[5:7])}月"
hdr = ["分组", "关键词"] + [lab(s) for s in ms] + ["近12月合计", "上年同期", "同比", "近12月峰值月", "最新月 ABA 排名", "最新月 竞争难度", "CPC 建议竞价（USD）", "类目相关度"]
rows, kst, merges, missing = [], [], [], []
def sv(x): return {r["localDate"]: (r["searchVolume"]["value"] if isinstance(r["searchVolume"], dict) else r["searchVolume"]) for r in x["trends"]}
def col(i):
    s = ""; i += 1
    while i: i, r = divmod(i - 1, 26); s = chr(65 + r) + s
    return s
for g in cfg["keyword_groups"]:
    terms = [t for t in g["terms"] if t in by]; missing += [t for t in g["terms"] if t not in by]
    if not terms: continue
    s0 = len(rows) + 2; tot24 = [0] * 24
    for i, t in enumerate(terms):
        x = by[t]; v = sv(x); vals = [v.get(s) for s in ms]
        a = sum(vals[:12]) if None not in vals[:12] else None; b = sum(vals[12:]) if None not in vals[12:] else None
        pk = max(range(12), key=lambda j: vals[j] or 0)
        kst.append({"range": f"{col(2+pk)}{len(rows)+2}", "background_color": "#C6EFCE", "font_weight": "bold"})
        rows.append([g["name"] if i == 0 else "", t] + [z if z is not None else "—" for z in vals] +
                    [a if a else "—", b if b else "—", a / b - 1 if a and b else "—", lab(ms[pk]), x["searchFrequencyRank"], x["searchTermCompetitiveDifficulty"], float(x["cpc"]["value"]), float(x["categoryRelevance"])])
        tot24 = [p + (q or 0) for p, q in zip(tot24, vals)]
    e0 = len(rows) + 1
    kst += [{"range": f"A{s0}:B{e0}", "background_color": "#DDEBF7"}, {"range": f"A{s0}:A{e0}", "font_weight": "bold", "horizontal_alignment": "center"}]
    if e0 > s0: merges.append({"range": f"A{s0}:A{e0}"})
    a, b = sum(tot24[:12]), sum(tot24[12:]); pk = max(range(12), key=lambda j: tot24[j])
    kst += [{"range": f"A{len(rows)+2}:AH{len(rows)+2}", "background_color": "#F2F2F2", "font_weight": "bold"},
            {"range": f"{col(2+pk)}{len(rows)+2}", "background_color": "#C6EFCE", "font_weight": "bold"}]
    rows.append(["合计", f"{g['name']}合计（{len(terms)}个）"] + tot24 + [a, b, a / b - 1 if b else "—", lab(ms[pk]), "", "", "", ""])
n = len(rows) + 1
base = [{"range": f"AA1:AD1", "background_color": "#2F5597"}, {"range": "AE1:AH1", "background_color": "#404040"},
        {"range": f"C2:AB{n}", "number_format": "#,##0", "horizontal_alignment": "right"}, {"range": f"AC2:AC{n}", "number_format": "0.0%", "horizontal_alignment": "right"},
        {"range": f"AD2:AD{n}", "horizontal_alignment": "center"}, {"range": f"AE2:AE{n}", "number_format": "#,##0", "horizontal_alignment": "right"},
        {"range": f"AF2:AF{n}", "horizontal_alignment": "center"}, {"range": f"AG2:AG{n}", "number_format": "$0.00", "horizontal_alignment": "right"},
        {"range": f"AH2:AH{n}", "number_format": "0.00", "horizontal_alignment": "center"}, {"range": f"A2:AH{n}", "vertical_alignment": "middle"}]
kfoot = (f"说明：数据来源西柚 get_category_keywords（类目 {xc['categoryName']}，相关度=高），{cfg['marketplace']} 站；月份列为月搜索量，从左到右由新到旧。"
         f"最新月={months[23][0]}年{months[23][1]}月，ABA 排名、竞争难度、CPC 与类目相关度为最新快照。核心词按产品类型分组，共 {sum(len(g['terms']) for g in cfg['keyword_groups'])} 个，同义变体不重复列，已剔除品牌词和他用词。"
         "同比=近12月对比上年同期；绿色加粗=该词近12月搜索量最高的月份。" + A.kw_note + f"拉取日期 {A.date}。")
kw = {"tab": cfg["sheet"]["tabs"]["keywords"], "header": [hdr], "rows": rows, "footer": kfoot, "ncols": 34, "base_styles": base, "styles": kst, "merges": merges,
      "col_sizes": [{"range": "A:A", "size": 120}, {"range": "B:B", "size": 230}, {"range": "C:Z", "size": 72}, {"range": "AA:AH", "size": 95}],
      "row_height": 27, "footer_height": 100, "freeze": {"rows": 1, "cols": 2}, "check_col": 1}
json.dump(kw, open(os.path.join(A.run, "spec_keywords.json"), "w"), ensure_ascii=False)
print(f"market: {len(data)} months, yellow rows {yellow}; keywords: {len(rows)} rows, missing terms {missing or '无'}")
