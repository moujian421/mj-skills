"""Daily price-drop monitor: sub-BSR top N variation groups (own brands excluded), price actions in the last 2 data days.
Usage:
  daily_monitor.py pick   --config CFG --run RUN --date D        -> RUN/top.json, RUN/asins.txt
  daily_monitor.py detect --config CFG --run RUN --date D        -> RUN/drops.json, RUN/drop_asins.txt
  daily_monitor.py emit   --config CFG --run RUN --date D        -> appends to data/<slug>/daily_rows.json, RUN/spec_daily.json
  daily_monitor.py reset  --config CFG --run RUN --date D        -> keeps only rows from the week of D (call on the weekly update)
Rows stay in daily_rows.json for the whole week; the weekly update calls reset, which drops last week's rows."""
import json, os, re, sys, glob, argparse, datetime as dt
sys.path.insert(0, os.path.dirname(__file__))
from cfg import load_cfg, raw_index, run_dirs, trends, all_items

ap = argparse.ArgumentParser()
ap.add_argument("cmd", choices=["pick", "detect", "emit", "reset"])
ap.add_argument("--config", required=True); ap.add_argument("--run", required=True); ap.add_argument("--date", required=True)
A = ap.parse_args()
cfg = load_cfg(A.config); DC = cfg.get("daily", {}); NODE = cfg["node_id"]
DATA = os.path.dirname(os.path.abspath(A.config)); ROWS_P = os.path.join(DATA, "daily_rows.json")
os.makedirs(A.run, exist_ok=True)

def fp(p): return f"${p:.2f}".rstrip("0").rstrip(".") if p else "-"
def md(s): return s[5:]
def num(v):
    try: return float(v) if v not in (None, "") else None
    except (TypeError, ValueError): return None
def load_rows(): return json.load(open(ROWS_P)) if os.path.exists(ROWS_P) else []

def short_name(asin, brand, title):
    it = all_items(cfg).get(asin)
    if it: return it.get("name")
    t = re.sub(r"^\s*" + re.escape(brand or "") + r"\s*", "", title or "", flags=re.I)
    t = re.split(r"[,|–—(]", t)[0].strip()
    return f"{brand} {t[:45]}".strip()

if A.cmd == "pick":
    own = {b.lower() for b in DC.get("own_brands", [])}
    rows = {}
    for f in sorted(glob.glob(os.path.join(A.run, "snap", "**", "raw", "product_research_*.json"), recursive=True)):
        d = json.load(open(f)); d = d.get("data", d)
        for x in d.get("items", []):
            r = [s.get("rank") for s in x.get("subcategories") or [] if s.get("code") == NODE]
            if r and r[0]: rows[x["asin"]] = dict(x, subrank=r[0], parent=x.get("parent") or x["asin"])
    src = "卖家精灵当日"
    if not rows:
        # SellerSprite down: Sorftime BestSeller top 100 (category_products), same day, has sub rank per node
        for f in sorted(glob.glob(os.path.join(A.run, "sorftime", "**", "raw", "category_products_*.json"), recursive=True)):
            for x in json.load(open(f)).get("data", []):
                sc = x.get("sub_category") or []
                r = [e[2] for e in sc if len(e) > 2 and str(e[1]) == NODE]
                if not r or not r[0]: continue
                img = (x.get("main_image") or [None])[0]
                if img: img = re.sub(r"\.jpg$", "._AC_US200_.jpg", img)   # 200px thumbnail
                rows[x["asin"]] = {"asin": x["asin"], "parent": x.get("parent_asin") or x["asin"], "brand": x.get("brand"),
                                   "title": x.get("title"), "units": x.get("monthly_sales_volume"), "price": x.get("price"), "imageUrl": img, "subrank": r[0]}
        if rows: src = "Sorftime 当日"
    if not rows:
        # SellerSprite down: fall back to the newest earlier daily top list, then to the weekly snapshot
        prev = sorted(p for p in glob.glob(os.path.join(DATA, "daily_runs", "*", "top.json")) if os.path.basename(os.path.dirname(p)) < A.date)
        if prev:
            top = json.load(open(prev[-1])); src = os.path.basename(os.path.dirname(prev[-1]))
            for t in top: t.setdefault("rank_src", src)
            json.dump(top, open(os.path.join(A.run, "top.json"), "w"), ensure_ascii=False, indent=1)
            open(os.path.join(A.run, "asins.txt"), "w").write("\n".join(t["asin"] for t in top) + "\n")
            json.dump({"rows": [{"asin": t["asin"], "image": t.get("image")} for t in top]}, open(os.path.join(A.run, "snap.json"), "w"))
            print(json.dumps({"fallback": "daily " + src, "competitors": len(top)}, ensure_ascii=False)); sys.exit(0)
        snaps = sorted(glob.glob(os.path.join(DATA, "snapshots", "*.json")))
        if not snaps: sys.exit("no snapshot rows")
        src = os.path.basename(snaps[-1])[:-5]
        for r in json.load(open(snaps[-1]))["rows"]:
            rows[r["asin"]] = dict(r, imageUrl=r.get("image"), title="")
    if src.endswith("当日"):
        # daily rank history: same-day sub-BSR of every listed ASIN (sub rank <= 100), to replace Xiyou riser_bsr pulls later
        hd = os.path.join(DATA, "daily_ranks"); os.makedirs(hd, exist_ok=True)
        json.dump({"date": A.date, "source": "sellersprite" if src.startswith("卖家精灵") else "sorftime",
                   "rows": [{"asin": r["asin"], "parent": r["parent"], "brand": r.get("brand"), "subrank": r["subrank"], "price": r.get("price")}
                            for r in rows.values() if r["subrank"] <= 100]},
                  open(os.path.join(hd, A.date + ".json"), "w"), ensure_ascii=False)
    groups = {}
    for r in rows.values(): groups.setdefault(r["parent"], []).append(r)
    ranked = sorted(groups.values(), key=lambda g: min(r["subrank"] for r in g))[:DC.get("top_n", 20)]
    top = []
    for g in ranked:
        # the child already tracked in the weekly table stands for the group; otherwise the best-selling child
        known = [r for r in g if r["asin"] in all_items(cfg)]
        rep = known[0] if known else max(g, key=lambda r: r.get("units") or 0)
        if (rep.get("brand") or "").lower() in own: continue
        top.append({"asin": rep["asin"], "brand": rep.get("brand"), "rank": min(r["subrank"] for r in g),
                    "name": short_name(rep["asin"], rep.get("brand"), rep.get("title")), "image": rep.get("imageUrl"),
                    **({} if src.endswith("当日") else {"rank_src": src})})
    json.dump(top, open(os.path.join(A.run, "top.json"), "w"), ensure_ascii=False, indent=1)
    open(os.path.join(A.run, "asins.txt"), "w").write("\n".join(t["asin"] for t in top) + "\n")
    # snapshot-shaped file so fetch_images.py can find the image URLs
    json.dump({"rows": [{"asin": t["asin"], "image": t["image"]} for t in top]}, open(os.path.join(A.run, "snap.json"), "w"))
    print(json.dumps({"source": src, "groups_in_top": len(ranked), "competitors": len(top)}, ensure_ascii=False))

def coupon_set(pd):
    out = set()
    for k in ("coupon", "promotion"):
        for c in pd.get(k) or []:
            out.add((k, json.dumps(c, ensure_ascii=False, sort_keys=True) if isinstance(c, (dict, list)) else str(c)))
    return out
def coupon_text(k, c):
    try: v = json.loads(c)
    except ValueError: v = c
    if isinstance(v, dict):
        v = v.get("text") or v.get("desc") or v.get("value") or v.get("discount") or json.dumps(v, ensure_ascii=False)
    return ("优惠券 " if k == "coupon" else "促销 ") + str(v)

if A.cmd == "detect":
    top = json.load(open(os.path.join(A.run, "top.json")))
    idx = raw_index(run_dirs(os.path.join(A.run, "price")))
    th = DC.get("drop_min", 0.05); out = []; missing = []
    for t in top:
        a = t["asin"]
        if (a, "get_asin_info_trends") not in idx: missing.append(a); continue
        inf = trends(idx[(a, "get_asin_info_trends")]); days = sorted(inf)
        if len(days) < 2: missing.append(a); continue
        pdx = lambda x: inf[x].get("priceDistribution") or {}
        P = lambda x: num(pdx(x).get("display"))
        deal = lambda x: num(pdx(x).get("deal"))
        prime = lambda x: num(pdx(x).get("prime")) is not None and not deal(x)
        win = days[-2:]; drops, other = [], []; skip = set()
        for x in win:
            i = days.index(x)
            if i == 0 or x in skip: continue
            y = days[i - 1]; p0, p1 = P(y), P(x)
            if deal(x) and not deal(y):
                pdeal = deal(x); base = p0 or num(pdx(y).get("strikethrough"))
                tag = "Prime 专享 Deal" if num(pdx(x).get("prime")) == pdeal else "Deal"
                drops.append((x, "deal", f"{md(x)} 开始{tag}，价 {fp(pdeal)}" + (f"（前一天 {fp(base)}，{pdeal/base-1:+.0%}）" if base else "")))
            elif deal(x) and deal(y) and deal(x) < deal(y) * (1 - 0.03):
                drops.append((x, "deal_down", f"{md(x)} Deal 价下调 {fp(deal(y))}→{fp(deal(x))}（{deal(x)/deal(y)-1:+.0%}）"))
            elif deal(y) and not deal(x) and p1:
                other.append(f"{md(x)} Deal 结束，回到 {fp(p1)}")
            elif prime(x) and not prime(y) and p0 and p1 and p1 < p0:
                gap = i >= 2 and prime(days[i - 2])             # Prime price missing for just one day, then back
                drops.append((x, "prime", f"{md(x)} {'恢复' if gap else '起'} Prime 专享价 {fp(p1)}（原价 {fp(p0)}，{p1/p0-1:+.0%}）"
                                          + (f"，{md(y)} 单日中断" if gap else "")))
            elif p0 and p1 and not deal(x) and not deal(y) and abs(p1 / p0 - 1) >= th:
                if p1 < p0:
                    lab = "Prime 专享价下调" if prime(x) and prime(y) else "降价"
                    p2 = P(days[i + 1]) if i + 1 < len(days) else None
                    once = p2 is not None and abs(p2 / p0 - 1) < 0.03   # back to the old price the next day
                    if once: skip.add(days[i + 1])
                    drops.append((x, "price", f"{'⚠️ ' if p1/p0-1 <= -0.3 else ''}{md(x)} {'单日' if once else ''}{lab} {fp(p0)}→{fp(p1)}（{p1/p0-1:+.0%}）"
                                              + ("，次日恢复" if once else "")))
                else:
                    other.append(f"{'⚠️ ' if p1/p0-1 >= 0.2 else ''}{md(x)} 涨价 {fp(p0)}→{fp(p1)}（{p1/p0-1:+.0%}）")
            elif p0 and not p1:
                other.append(f"⚠️ {md(x)} 无售价/疑似断货")
            new_c = coupon_set(pdx(x)) - coupon_set(pdx(y))
            for k, c in sorted(new_c):
                drops.append((x, "coupon:" + c, f"{md(x)} 新增{coupon_text(k, c)}"))
            s0, s1 = num(pdx(y).get("strikethrough")), num(pdx(x).get("strikethrough"))
            if s0 and s1 and abs(s1 / s0 - 1) >= 0.03: other.append(f"⚠️ {md(x)} 划线价 {fp(s0)}→{fp(s1)}")
            r0, r1 = inf[y].get("ratings"), inf[x].get("ratings")
            if r0 and r1 and r0 - r1 >= 50: other.append(f"⚠️ {md(x)} 评分数 {r0}→{r1}（-{r0-r1}）")
        # small drops on both days that add up: compare the last day with the day before the window
        if not any(k in ("price", "deal", "deal_down", "prime") for _, k, _ in drops) and len(days) >= 3:
            b0, b1 = P(days[-3]), P(days[-1])
            if b0 and b1 and not deal(days[-1]) and not deal(days[-3]) and b1 <= b0 * (1 - th):
                drops.append((days[-1], "price_cum", f"{md(win[0])}~{md(win[-1])} 连续小幅降价，累计 {fp(b0)}→{fp(b1)}（{b1/b0-1:+.0%}）"))
        if drops:
            out.append(dict(t, window=[win[0], win[-1]], drops=[{"day": d, "key": k, "text": s} for d, k, s in drops], other=other))
    json.dump(out, open(os.path.join(A.run, "drops.json"), "w"), ensure_ascii=False, indent=1)
    open(os.path.join(A.run, "drop_asins.txt"), "w").write("".join(t["asin"] + "\n" for t in out))
    print(json.dumps({"checked": len(top) - len(missing), "missing": missing, "with_drop": len(out)}, ensure_ascii=False))

def write_spec(rows):
    pal = ["#DDEBF7", "#FCE4D6", "#E2EFDA", "#EDE2F6"]
    runs = sorted({r["run"] for r in rows}, reverse=True); rc = {d: pal[i % 4] for i, d in enumerate(runs)}
    rows = sorted(rows, key=lambda r: (r["run"], -r["rank"]), reverse=True)
    header = ["日期", "小类排名", "ASIN", "品牌", "产品", "主图", "动作"]
    body, styles, images = [], [], []
    for i, r in enumerate(rows, 2):
        d = dt.date.fromisoformat(r["run"])
        rk = f"{r['rank']}（{md(r['rank_src'])} 排名）" if r.get("rank_src") else r["rank"]
        body.append([f"{d.month}/{d.day}", rk, r["asin"], r["brand"], r["name"], "",
                     "\n".join(f"{k}. {a}" for k, a in enumerate(r["acts"], 1))])
        styles.append({"range": f"A{i}", "background_color": rc[r["run"]], "font_weight": "bold"})
        images.append({"cell": f"F{i}", "asin": r["asin"]})
    if not body: body = [["本周暂无降价竞品", "", "", "", "", "", ""]]
    n = len(body) + 1
    foot = (f"每天查看小类 BSR 前 {DC.get('top_n', 20)} 的变体组（卖家精灵当日数据，拉不到时用 Sorftime BestSeller 前 100；剔除 {'、'.join(DC.get('own_brands', []))}），"
            f"用西柚每日价格找出最近 2 天有降价动作的竞品：降价 ≥{DC.get('drop_min', 0.05):.0%}（单日或 2 天累计）、开始 Deal 或 Deal 价下调、Prime 专享价、新增优惠券或促销；"
            "动作列同时列出这 2 天的其他动作（涨价、Deal 结束、划线价、断货、评分数骤降、新开广告）。"
            "西柚数据比当天晚约 2 天；同一个降价只在第一次发现时列出。本页保留本周每天的记录，下次更新周度数据时清空上周的记录。")
    spec = {"tab": cfg["sheet"]["tabs"].get("daily", "竞对动作-日度"), "header": [header], "rows": body, "footer": foot, "ncols": 7,
            "base_styles": [{"range": f"B2:B{n}", "horizontal_alignment": "center"}, {"range": f"F2:F{n}", "horizontal_alignment": "center", "vertical_alignment": "middle"}],
            "styles": styles, "images": images,
            "col_sizes": [{"range": "A:A", "size": 80}, {"range": "B:B", "size": 90}, {"range": "C:C", "size": 120}, {"range": "D:D", "size": 110},
                          {"range": "E:E", "size": 220}, {"range": "F:F", "size": 110}, {"range": "G:G", "size": 520}],
            "row_height": 110, "footer_height": 90, "freeze": {"rows": 1, "cols": 3}, "check_col": 2}
    json.dump(spec, open(os.path.join(A.run, "spec_daily.json"), "w"), ensure_ascii=False)
    return len(rows)

if A.cmd == "emit":
    drops = json.load(open(os.path.join(A.run, "drops.json")))
    rows = [r for r in load_rows() if r["run"] != A.date]           # rerun of the same day replaces that day
    seen = {(r["asin"], k) for r in rows for k in r.get("keys", [])}
    aidx = raw_index(run_dirs(os.path.join(A.run, "ads")))
    added = 0
    for t in drops:
        new = [d for d in t["drops"] if (t["asin"], d["day"] + "|" + d["key"]) not in seen]
        if not new: continue                                          # already listed on an earlier day
        acts = [d["text"] for d in new] + t["other"]
        if (t["asin"], "get_asin_ad_change_trends") in aidx:
            for day, r in sorted(trends(aidx[(t["asin"], "get_asin_ad_change_trends")]).items()):
                if t["window"][0] <= day <= t["window"][1] and r.get("added"):
                    from collections import Counter
                    c = Counter((x.get("campaignType") or "").upper() for x in r["added"])
                    acts.append(f"{md(day)} 新开 " + " + ".join(f"{n} 个 {k}" if n > 1 else k for k, n in c.items()) + " 广告活动")
        rows.append({"run": A.date, "asin": t["asin"], "brand": t["brand"], "name": t["name"], "rank": t["rank"], "rank_src": t.get("rank_src"),
                     "acts": acts, "keys": [d["day"] + "|" + d["key"] for d in new]})
        added += 1
    json.dump(rows, open(ROWS_P, "w"), ensure_ascii=False, indent=1)
    n = write_spec(rows)
    print(json.dumps({"new_rows": added, "rows_this_week": n, "asins": sorted({r["asin"] for r in rows})}, ensure_ascii=False))

if A.cmd == "reset":
    d = dt.date.fromisoformat(A.date); mon = (d - dt.timedelta(days=d.weekday())).isoformat()
    old = load_rows(); rows = [r for r in old if r["run"] >= mon]
    json.dump(rows, open(ROWS_P, "w"), ensure_ascii=False, indent=1)
    write_spec(rows)
    print(json.dumps({"removed": len(old) - len(rows), "kept": len(rows), "asins": sorted({r["asin"] for r in rows})}, ensure_ascii=False))
