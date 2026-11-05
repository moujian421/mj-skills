"""Weekly actions & effects for tracked ASINs (+ risers).
Usage: python3 weekly.py --config CFG --run RUN_DIR --date YYYY-MM-DD [--extra-dirs D1 D2 ...]
Writes RUN_DIR/weekly_rows.json and prints one line per row."""
import re, json, sys, argparse, statistics as st, datetime as dt, collections
sys.path.insert(0, __import__("os").path.dirname(__file__))
from cfg import load_cfg, weeks, raw_index, run_dirs, trends, all_items

ap = argparse.ArgumentParser()
ap.add_argument("--config", required=True); ap.add_argument("--run", required=True)
ap.add_argument("--date", required=True); ap.add_argument("--extra-dirs", nargs="*", default=[])
A = ap.parse_args()
cfg = load_cfg(A.config); NODE = cfg["node_id"]
idx = raw_index(A.extra_dirs + run_dirs(A.run))
ITEMS = all_items(cfg)
W = weeks(cfg, A.date)
SHOW = [x for x in W if x[3] == "show"]

def avg(v):
    v = [x for x in v if x is not None]; return round(st.mean(v), 1) if v else None
def fp(p): return f"${p:.2f}".rstrip("0").rstrip(".") if p else "-"
def md(s): return s[5:]

RAT = {}
for a in ITEMS:
    if (a, "get_asin_info_trends") in idx:
        RAT[a] = {k: r.get("ratings") for k, r in trends(idx[(a, "get_asin_info_trends")]).items()}

def fam(a, day):
    """Links of the same brand with (near-)identical rating counts = one variation group."""
    r = RAT.get(a, {}).get(day)
    if not r: return frozenset([a])
    return frozenset(x for x in RAT if ITEMS[x]["brand"] == ITEMS[a]["brand"] and RAT[x].get(day)
                     and abs(RAT[x][day] - r) <= max(5, 0.001 * r))  # same group differs by 0~2; 20 merged two Caddytek models 17 reviews apart
def short(x): return ITEMS[x].get("short") or ITEMS[x]["name"]

def ads_of(a):
    if (a, "get_asin_ad_change_trends") not in idx: return []
    out = []
    for day, r in sorted(trends(idx[(a, "get_asin_ad_change_trends")]).items()):
        if r.get("added"):
            c = collections.Counter(x["campaignType"].upper() for x in r["added"])
            out.append((day, " + ".join(f"{n} 个 {k}" if n > 1 else k for k, n in c.items())))
    return out

rows = []
targets = [a for a, it in ITEMS.items() if it["role"] in ("tracked", "riser")]
for a in targets:
    it = ITEMS[a]
    if (a, "get_asin_info_trends") not in idx:
        print("MISSING info_trends", a, file=sys.stderr); continue
    inf = trends(idx[(a, "get_asin_info_trends")])
    bs = trends(idx[(a, "get_asin_bsr_trends")]) if (a, "get_asin_bsr_trends") in idx else {}
    tr = trends(idx[(a, "get_asin_traffic_trends")]) if (a, "get_asin_traffic_trends") in idx else {}
    kw = trends(idx[(a, "get_asin_keyword_rank_trends")]) if (a, "get_asin_keyword_rank_trends") in idx else {}
    ADS = ads_of(a)
    days = sorted(inf)
    def P(x):
        v = inf.get(x, {}).get("priceDistribution", {}).get("display"); return float(v) if v else None
    def sub(x):
        for v in bs.get(x, {}).get("values", []):
            if v["categoryId"] == NODE: return v.get("rank")
    org = lambda x: tr.get(x, {}).get("summaryTrafficScore", {}).get("organic")
    adv = lambda x: tr.get(x, {}).get("summaryTrafficScore", {}).get("advertising")
    def kor(x):
        for y in kw.get(x, {}).get("displayPositions", []):
            if y["displayPosition"] == "or": return y.get("totalRank")
    met = {}; rng = {}; skip = set(); adflag = False
    for w, s, e, _ in W:
        ds = [x for x in days if s <= x <= e]
        met[w] = (avg([sub(x) for x in ds]), avg([org(x) for x in ds]), avg([kor(x) for x in ds]), avg([adv(x) for x in ds]))
        sv = [sub(x) for x in ds if sub(x) is not None]; kv = [kor(x) for x in ds if kor(x) is not None]
        rng[w] = ((min(sv), max(sv)) if sv else None, (min(kv), max(kv)) if kv else None, len(kv), len(ds))
    isdeal = lambda x: bool(inf.get(x, {}).get("priceDistribution", {}).get("deal"))
    isprime = lambda x: bool(inf.get(x, {}).get("priceDistribution", {}).get("prime")) and not isdeal(x)
    for k in range(1, len(W) - 1):
        w, s, e, _ = W[k]
        ds = [x for x in days if s <= x <= e]
        if not ds: continue
        acts = []
        dd = [x for x in ds if isdeal(x)]
        if dd:
            pv = sorted({fp(float(inf[x]["priceDistribution"]["deal"])) for x in dd})
            pd_ = all(inf[x]["priceDistribution"].get("prime") == inf[x]["priceDistribution"]["deal"] for x in dd)
            acts.append(f"{'Prime 专享 ' if pd_ else ''}Deal {len(dd)}天（{'、'.join(md(x) for x in dd)}）价 {'/'.join(pv)}")
        for x in ds:
            i = days.index(x)
            if i == 0 or x in skip: continue
            y = days[i - 1]; p0, p1 = P(y), P(x)
            if isdeal(y) and not isdeal(x) and p1:
                acts.append(f"{md(x)} Deal 结束，回到 {'Prime 专享价 ' if isprime(x) else ''}{fp(p1)}"); continue
            if isprime(x) and not isprime(y) and not isdeal(y) and p0 and p1:
                if p1 < p0: acts.append(f"{md(x)} 起 Prime 专享价 {fp(p1)}（原价 {fp(p0)}，{p1/p0-1:+.0%}）")
                continue
            if isprime(y) and not isprime(x) and not isdeal(x) and p1:
                acts.append(f"{md(x)} Prime 专享价结束，回到 {fp(p1)}"); continue
            if p1 and not p0: acts.append(f"{md(x)} 恢复售价 {fp(p1)}"); continue
            if p0 and p1 and abs(p1/p0 - 1) >= 0.05 and not isdeal(x) and not isdeal(y):
                p2 = P(days[i + 1]) if i + 1 < len(days) else None
                if p2 and abs(p2/p0 - 1) < 0.03:
                    lab = ("Prime 专享价单日" + ("上调" if p1 > p0 else "下调")) if isprime(x) else ("单日" + ("涨" if p1 > p0 else "降") + "价")
                    acts.append(f"{'⚠️ ' if abs(p1/p0-1) >= 0.3 else ''}{md(x)} {lab} {fp(p0)}→{fp(p1)}（{p1/p0-1:+.0%}），次日恢复"); skip.add(days[i + 1])
                else:
                    lab = ("Prime 专享价" + ("上调" if p1 > p0 else "下调")) if isprime(x) and isprime(y) else (("涨" if p1 > p0 else "降") + "价")
                    acts.append(f"{'⚠️ ' if p1/p0-1 >= 0.2 else ''}{md(x)} {lab} {fp(p0)}→{fp(p1)}（{p1/p0-1:+.0%}）")
        i0 = days.index(ds[0])
        prevs = inf[days[i0 - 1]]["priceDistribution"].get("strikethrough") if i0 > 0 else None
        for x in ds:
            v = inf[x]["priceDistribution"].get("strikethrough")
            if v and prevs and abs(float(v)/float(prevs) - 1) >= 0.03: acts.append(f"⚠️ {md(x)} 划线价 {fp(float(prevs))}→{fp(float(v))}")
            if v: prevs = v
        # no price on any day of the whole pull = Xiyou never captured prices (e.g. some FBM listings), not a stockout
        npd = [] if not any(P(z) for z in days) else [x for x in ds if not P(x)]
        if npd: acts.append(f"⚠️ 无售价/疑似断货 {len(npd)}天")
        famdays = set()
        for x in ds:
            i = days.index(x)
            if i == 0: continue
            # a day with missing rating counts is a data gap, not a variation change: compare only links seen on both days
            if not RAT[a].get(days[i - 1]) or not RAT[a].get(x): continue
            both = {z for z in RAT if RAT[z].get(days[i - 1]) and RAT[z].get(x)}
            f0, f1 = fam(a, days[i - 1]) & both, fam(a, x) & both
            if f0 != f1 and i + 1 < len(days) and RAT[a].get(days[i + 1]) and (fam(a, days[i + 1]) & both) == f0: continue  # one-day glitch
            if f0 != f1 and i >= 2 and RAT[a].get(days[i - 2]) and (fam(a, days[i - 2]) & both) == f1: continue  # recovery from a one-day glitch
            if f0 != f1 and (len(f0) > 1 or len(f1) > 1):
                famdays.add(x); r0, r1 = RAT[a][days[i - 1]], RAT[a][x]
                if len(f1) < len(f0):
                    acts.append(f"⚠️ {md(x)} 变体组拆分：与 {'、'.join(short(z) for z in sorted(f0-f1))} 不再共享评论（评分数 {r0:,}→{r1:,}），小类排名改为单独计算")
                else:
                    acts.append(f"⚠️ {md(x)} 重新并入变体组：与 {'、'.join(short(z) for z in sorted(f1-f0))} 共享评论（评分数 {r0:,}→{r1:,}），小类排名恢复按变体组计算")
        for x in ds:
            i = days.index(x)
            if x in famdays or i == 0: continue
            r0 = inf[days[i - 1]].get("ratings"); r1 = inf[x].get("ratings")
            if r0 and r1 and r0 - r1 >= 50:
                nxt = inf[days[i + 1]].get("ratings") if i + 1 < len(days) else None
                if not (nxt and nxt - r1 >= 50): acts.append(f"⚠️ {md(x)} 评分数 {r0}→{r1}（-{r0-r1}）")
        for x, lab in ADS:
            if s <= x <= e: acts.append(f"{md(x)} 新开 {lab} 广告活动")
        a0 = [adv(x) for x in ds]; pw = W[k - 1][0]
        if sum(1 for z in a0 if z == 0) >= 4 and (adflag or (met[pw][3] or 0) >= 5):
            acts.append("⚠️ 广告流量持续为0" if adflag else "⚠️ 广告流量归零（疑似停广告）"); adflag = True
        if (met[pw][3] or 0) < 1 and (met[w][3] or 0) >= 3: acts.append("广告流量从0恢复（疑似重开广告）")
        if W[k][3] != "show": continue
        if it["role"] == "riser":
            if it.get("detected_week") != s: continue      # risers appear only in the week they were found
        elif not acts: continue
        b, c = met[pw], met[w]
        def ch(x, y, fmt="{:.0f}", pct=True):
            if x is None and y is None: return "—"
            if x is None: return f"无→{fmt.format(y)}"
            if y is None: return f"{fmt.format(x)}→无"
            s_ = f"{fmt.format(x)}→{fmt.format(y)}"
            if pct and x: s_ += f"（{y/x-1:+.0%}）"
            return s_
        def verdict(b, c):
            kd = (b[2]-c[2])/b[2] if b[2] and c[2] and (abs(b[2]-c[2]) >= 2 or (b[2] <= 5 and abs(b[2]-c[2]) >= 1)) else (0 if b[2] and c[2] else None)
            od = (c[1]/b[1]-1) if b[1] and c[1] is not None and b[1] >= 5 else None
            sd = (b[0]-c[0])/b[0] if b[0] and c[0] and (abs(b[0]-c[0]) >= 1.5 or (b[0] <= 5 and abs(b[0]-c[0]) >= 1)) else (0 if b[0] and c[0] else None)
            g = [z for z in (kd, od, sd) if z is not None and z >= 0.15]; bd = [z for z in (kd, od, sd) if z is not None and z <= -0.15]
            if c[0] and c[0] <= 1.5 and (c[2] is None or c[2] <= 1.5) and not bd: return "✅ 小类第1"
            # small swing: only one metric just past the line (15%~25%) and another moving the other way (>=5%, below the line)
            raw = {"小类排名": (b[0]-c[0])/b[0] if b[0] and c[0] else None, "自然流量": od,
                   "核心词自然位": (b[2]-c[2])/b[2] if b[2] and c[2] else None}
            hit = [(n_, z) for n_, z in (("核心词自然位", kd), ("自然流量", od), ("小类排名", sd)) if z is not None and abs(z) >= 0.15]
            if len(hit) == 1 and abs(hit[0][1]) < 0.25:
                n_, z = hit[0]
                if any(v is not None and v * z < 0 and abs(v) >= 0.05 for k_, v in raw.items() if k_ != n_):
                    i_ = {"小类排名": 0, "自然流量": 1, "核心词自然位": 2}[n_]
                    tail = f"（{z:+.0%}）" if n_ == "自然流量" else ""
                    return f"➖ 小幅波动|只有{n_}过线，{b[i_]:.0f}→{c[i_]:.0f}{tail}"
            if g and not bd: return "✅ 提升"
            if bd and not g: return "❌ 下滑"
            if g and bd: return "➖ 有升有降"
            return "➖ 基本持平"
        def sigs(wn):
            s0, e0 = [(z[1], z[2]) for z in W if z[0] == wn][0]
            return {fam(a, x) for x in days if s0 <= x <= e0}
        def comparable(wa, wb):
            # not comparable only when a real split/merge happens between the two weeks (data-gap days are ignored)
            s0 = [z[1] for z in W if z[0] == wa][0]; e1 = [z[2] for z in W if z[0] == wb][0]
            for i, x in enumerate(days):
                if i == 0 or not (s0 < x <= e1): continue
                p = days[i - 1]
                if not RAT[a].get(p) or not RAT[a].get(x): continue
                both = {z for z in RAT if RAT[z].get(p) and RAT[z].get(x)}
                f0, f1 = fam(a, p) & both, fam(a, x) & both
                if f0 != f1 and i + 1 < len(days) and RAT[a].get(days[i + 1]) and (fam(a, days[i + 1]) & both) == f0: continue  # one-day glitch
                if f0 != f1 and i >= 2 and RAT[a].get(days[i - 2]) and (fam(a, days[i - 2]) & both) == f1: continue  # recovery from a one-day glitch
                if f0 != f1 and (len(f0) > 1 or len(f1) > 1): return False
            return True
        NC = "⚠️ 变体拆分/合并，排名不可比"
        def lab(v, cmp=""):
            h, _, d = v.partition("|")
            return f"{h}{cmp}：{d}" if d else h + cmp
        vb = "⚠️ 断货中，无法判断" if len(npd) >= 5 else (verdict(b, c) if comparable(pw, w) else NC)
        def R(x, r, cnt=None, tot=None):
            if x is None: return "无"
            s_ = f"{int(x+0.5)}" + (f"（{r[0]}~{r[1]}）" if r and r[0] != r[1] else "")
            if cnt is not None and cnt < tot: s_ += f"[{cnt}/{tot}天上榜]"
            return s_
        def rk(wa, wb, i):
            ra, rb = rng[wa], rng[wb]; X, Y = met[wa], met[wb]
            if i == 0: return f"{R(X[0], ra[0])}→{R(Y[0], rb[0])}" if (X[0] or Y[0]) else "—"
            if X[2] is None and Y[2] is None: return "—"
            return f"{R(X[2], ra[1], ra[2], ra[3])}→{R(Y[2], rb[1], rb[2], rb[3])}"
        eff = [lab(vb, "（对比上周）"), f"小类排名 {rk(pw, w, 0)}", f"自然流量 {ch(b[1], c[1])}",
               f"核心词自然位 {rk(pw, w, 2)}" if it.get("keyword") else "核心词自然位 —（无对应核心词）"]
        dates = [m.group(0) for z in acts for m in [re.search(r"\d\d-\d\d", z)] if m]
        lastd = (dt.date.fromisoformat(e) - dt.timedelta(days=2)).isoformat()[5:]
        if dates and max(dates) >= lastd and W[k + 1][3] == "show":
            wn = W[k + 1][0]; n = met[wn]
            eff.append(f"动作在周末，次周：{lab(verdict(c, n)) if comparable(w, wn) else NC}，小类 {rk(w, wn, 0)}，自然流量 {ch(c[1], n[1])}，核心词 {rk(w, wn, 2)}")
        if it["role"] == "riser":
            ty = it.get("type")
            head_ = {"gradual": "📈 重点：渐进上升（", "new": "🆕 重点：新品冲榜（"}.get(ty, "🚀 重点：快速上升（")
            lead = {"gradual": "上升起点：", "new": "冲榜："}.get(ty, "起飞：")
            eff = [head_ + it.get("why", "排名明显稳定上升") + "）" + ("；下周复核" if it.get("recheck") else ""),
                   lead + it.get("takeoff_text", "")] + eff
            if not acts: acts = ["（本周无可识别的价格/广告/Listing 动作，打法见复盘页签）"]
        # weekend rank from the BSR series itself: info_trends often ends a day earlier, which used to drop Sunday
        wkend = [sub(x) for x in sorted(bs) if s <= x <= e and dt.date.fromisoformat(x).weekday() >= 5 and sub(x) is not None]
        wr = round(st.median(wkend)) if wkend else None
        rows.append({"w": w, "wstart": s, "asin": a, "name": it["name"], "brand": it["brand"], "rank": wr, "sales_rank": it.get("rank"),
                     "riser": it["role"] == "riser", "acts": acts, "eff": eff, "m0": b, "m1": c})
import os as _os
cache_p = _os.path.join(_os.path.dirname(A.config), "riser_rows.json")
cache = json.load(open(cache_p)) if _os.path.exists(cache_p) else []
shown = {z[1] for z in W if z[3] == "show"}
new_keys = {(r["wstart"], r["asin"]) for r in rows if r["riser"]}
cache = [r for r in cache if (r["wstart"], r["asin"]) not in new_keys] + [r for r in rows if r["riser"]]
json.dump(cache, open(cache_p, "w"), ensure_ascii=False, indent=1)
have = {(r["wstart"], r["asin"]) for r in rows}
rows += [r for r in cache if r["wstart"] in shown and (r["wstart"], r["asin"]) not in have]
rows.sort(key=lambda r: (r["wstart"], r["rank"] if r["rank"] is not None else 999, r["sales_rank"] or 999))
json.dump(rows, open(A.run + "/weekly_rows.json", "w"), ensure_ascii=False, indent=1)
for r in rows: print(r["w"], r["asin"], r["name"], "|", " ; ".join(r["acts"]), "|", " ; ".join(r["eff"]))
