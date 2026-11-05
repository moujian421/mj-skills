"""Find listings whose subcategory rank rose clearly and steadily.
prefilter: python3 riser_scan.py prefilter --config CFG --snapdir DIR --date D --out CAND.txt
   compares this week's snapshot with the newest earlier one; writes candidate ASINs (one per line).
supplement: python3 riser_scan.py supplement --config CFG --snapdir DIR --date D --out CAND.txt --newlist RUN/new_listing
   appends new listings (SellerSprite current data, listed within new_listing_days, sub rank <= pool_max_rank) + config risers with recheck=true.
confirm:   python3 riser_scan.py confirm --config CFG --run RUN --date D [--extra-dirs ...]
   uses daily BSR (candidates + tracked) and applies the rule; writes RUN/risers_found.json.
Tracked (head) groups are never risers. Two rules (details in references/rules.md):
  fast    (🚀): last complete week's median vs median of the two weeks before: >=30% better and >=5 places
           (>=3 when base <=15), >=5 days of the week <= base*0.8; if the base fortnight was a dip
           (>1.2x the fortnight before it), the pre-dip level is the base, so a mere recovery does not count.
  gradual (📈): >=3 consecutive weekly medians not worse (rebound <=5%), >=2 clear improvements, >=20% and >=5 places
           (>=3 when start <=15) since the streak start, >=5 days of last week <= start*0.9, 28-day log-rank trend R^2 >= 0.4.
  new     (🆕): base fortnight unranked or beyond watch_from_rank, and >= new.min_days (3) days of last week inside new.top (50);
           1~2 such days -> still listed, flagged '新品冲榜，下周复核' (config risers get recheck=true and are re-pulled next week).
  watch list: base beyond watch_from_rank (or unranked) and last week inside it (but not inside new.top).
  promo: last week contains a promo day and the rule fails once promo days are removed -> flag '大促周，下周复核'."""
import json, os, sys, glob, argparse, statistics as st, datetime as dt
sys.path.insert(0, os.path.dirname(__file__))
from cfg import load_cfg, last_complete_sunday, raw_index, run_dirs, trends, all_items
ap = argparse.ArgumentParser(); ap.add_argument("mode"); ap.add_argument("--config", required=True)
ap.add_argument("--snapdir"); ap.add_argument("--date", required=True); ap.add_argument("--out")
ap.add_argument("--run"); ap.add_argument("--extra-dirs", nargs="*", default=[])
ap.add_argument("--newlist"); A = ap.parse_args()
cfg = load_cfg(A.config); R = cfg["riser_rule"]; items = all_items(cfg)
known = set(items) | {t.get("primary") for t in cfg["tracked"]}

def groups(snap):
    g = {}
    for r in snap["rows"]:
        p = r["parent"]
        if p not in g or r["subrank"] < g[p]["subrank"]: g[p] = r
    return g

if A.mode == "prefilter":
    files = sorted(glob.glob(os.path.join(A.snapdir, "*.json")))
    cur = [f for f in files if os.path.basename(f) <= A.date + ".json"]
    now = json.load(open(cur[-1])); prev = json.load(open(cur[-2])) if len(cur) > 1 else None
    nd = dt.date.fromisoformat(now["date"])
    olds = [f for f in cur[:-1] if 14 <= (nd - dt.date.fromisoformat(os.path.basename(f)[:10])).days <= 35]
    old4 = json.load(open(olds[0])) if olds else None   # oldest snapshot 2-5 weeks back (ideally 3-4)
    G = groups(now); PG = groups(prev) if prev else {}; OG = groups(old4) if old4 else {}
    # parents of tracked ASINs from every snapshot: a Sorftime snapshot lists ~1 child per group, often not the tracked one
    tracked_parents = {r["parent"] for f in cur for r in json.load(open(f))["rows"] if r["asin"] in known} | (known - {None})
    cand = []
    for p, r in G.items():
        if p in tracked_parents or r["subrank"] > R["pool_max_rank"]: continue
        if prev is None: cand.append(r); continue
        old = PG.get(p, {}).get("subrank"); o4 = OG.get(p, {}).get("subrank")
        if old is None or old > R["pool_max_rank"] or r["subrank"] <= old * 0.85 or (o4 and r["subrank"] <= o4 * 0.8): cand.append(r)
    open(A.out, "w").write("\n".join(r["asin"] for r in cand) + ("\n" if cand else ""))
    print(f"prefilter: snapshot {now['date']} vs {prev['date'] if prev else 'none (first run: whole top '+str(R['pool_max_rank'])+')'}"
          f"{' and ' + old4['date'] + ' (3-4 weeks back)' if old4 else ''}"
          f" -> {len(cand)} candidates (tracked groups excluded; their daily BSR comes from the daily stage)")
    sys.exit()

if A.mode == "supplement":
    # new-listing candidates (SellerSprite current data, newest first, sub rank <= pool_max_rank) + config risers with recheck=true
    import datetime as _dt
    snapf = sorted(f for f in glob.glob(os.path.join(A.snapdir, "*.json")) if os.path.basename(f) <= A.date + ".json")[-1]
    a2p = {r["asin"]: r["parent"] for r in json.load(open(snapf))["rows"]}
    allsnap = sorted(f for f in glob.glob(os.path.join(A.snapdir, "*.json")) if os.path.basename(f) <= A.date + ".json")
    tp = {r["parent"] for f in allsnap for r in json.load(open(f))["rows"] if r["asin"] in known} | (known - {None})
    have = {x.strip() for x in open(A.out)} if os.path.exists(A.out) else set()
    recheck = [r["asin"] for r in cfg.get("risers", []) if r.get("recheck")]
    since = (dt.date.fromisoformat(A.date) - dt.timedelta(days=cfg.get("new_listing_days", 90))).isoformat()
    out, why = [], {}
    for f in sorted(glob.glob(os.path.join(A.newlist, "**", "raw", "product_research_*.json"), recursive=True)) if A.newlist else []:
        d = json.load(open(f)); d = d.get("data", d)
        for x in d.get("items", []):
            a = x["asin"]; p = x.get("parent") or a2p.get(a) or a
            listed = _dt.datetime.utcfromtimestamp(x["availableDate"] / 1000).date().isoformat() if x.get("availableDate") else None
            rk = next((s_.get("rank") for s_ in x.get("subcategories") or [] if s_["code"] == cfg["node_id"]), None)
            if not listed or listed < since or not rk or rk > R["pool_max_rank"]: continue
            if (a in known and a not in recheck) or p in tp or a in have or a in out: continue
            out.append(a); why[a] = f"新品 上架 {listed} 小类 {rk}"
    if A.newlist and not glob.glob(os.path.join(A.newlist, "**", "raw", "product_research_*.json"), recursive=True):
        # SellerSprite down: take new listings from this week's snapshot (Sorftime top 100 carries online_date)
        for r in json.load(open(snapf))["rows"]:
            a, p, listed, rk = r["asin"], r["parent"], r.get("listed"), r["subrank"]
            if not listed or listed < since or rk > R["pool_max_rank"]: continue
            if (a in known and a not in recheck) or p in tp or a in have or a in out: continue
            out.append(a); why[a] = f"新品 上架 {listed} 小类 {rk}（快照）"
    for a in recheck:
        if a not in out and a not in have: out.append(a); why[a] = "上周新品冲榜，复核"
    open(A.out, "a").write("".join(a + "\n" for a in out))
    print(f"supplement: +{len(out)} candidates -> {A.out}")
    for a in out: print(" ", a, why[a])
    sys.exit()

# confirm
import math
idx = raw_index(A.extra_dirs + run_dirs(A.run))
end = last_complete_sunday(A.date); rs = end - dt.timedelta(days=6)
WK = [(rs - dt.timedelta(days=7 * i), rs - dt.timedelta(days=7 * i) + dt.timedelta(days=6)) for i in range(5, -1, -1)]  # 6 weeks, oldest first
promo = set(cfg.get("promo_days", []))
G = R.get("gradual", {})
head_ids = {t["asin"] for t in cfg["tracked"]} | {t.get("primary") for t in cfg["tracked"]} | {s_["asin"] for t in cfg["tracked"] for s_ in t.get("siblings", [])}
def series(a):
    out = {}
    for day, r in trends(idx[(a, "get_asin_bsr_trends")]).items():
        for v in r.get("values", []):
            if v["categoryId"] == cfg["node_id"] and v.get("rank"): out[day] = v["rank"]
    return out
def vals(sr, s_, e_, drop_promo=False):
    return [v for k, v in sr.items() if s_.isoformat() <= k <= e_.isoformat() and not (drop_promo and k in promo)]
def med(v, n=4): return st.median(v) if len(v) >= n else None
def need(start): return R["min_places_small"] if start <= R["min_places_if_base_le"] else R["min_places"]
def fast(sr, drop_promo=False):
    rec = vals(sr, *WK[5], drop_promo); base = vals(sr, WK[3][0], WK[4][1]); early = vals(sr, WK[1][0], WK[2][1])
    mr, mb, me = med(rec, 3), med(base, 5), med(early, 5)
    if mr is None: return None
    res = {"recent_med": round(mr), "base_med": round(mb) if mb else None}
    # the base weeks were a dip (stock-out, variation split, one bad fortnight): judge against the level before the dip
    dip = None
    if mb and me and mb > me * 1.2:
        dip = mb; res["note"] = f"基准期 {round(mb)} 是一次下跌，改用下跌前的 {round(me)} 做基准"; mb = me; res["base_med"] = round(me)
    if mb is None or mb > R["watch_from_rank"]:
        res["status"] = "watch" if mr <= R["watch_from_rank"] else "no"; return res
    imp = (mb - mr) / mb; persist = sum(1 for v in rec if v <= mb * R["persist_factor"])
    res.update(improve=round(imp, 2), places=round(mb - mr), persist=f"{persist}/{len(rec)}")
    ok = imp >= R["min_improve_ratio"] and mb - mr >= need(mb) and persist >= min(R["persist_days"], len(rec) - 2)
    if not ok and dip and (dip - mr) / dip >= R["min_improve_ratio"]:
        res["note"] += "；只是回到原水平，不算上升" if imp < R["min_improve_ratio"] else f"；持续天数不够（{persist}/{len(rec)}），下周复核"
    res["status"] = "riser" if ok else "no"; res["type"] = "fast"
    return res
def gradual(sr):
    m = [med(vals(sr, s_, e_)) for s_, e_ in WK]
    k = 5
    if m[k] is None or m[k - 1] is None: return None
    st_ = k
    while st_ - 1 >= 0 and m[st_ - 1] is not None and m[st_] <= m[st_ - 1] * (1 + G.get("rebound", 0.05)): st_ -= 1
    steps = k - st_; imp = sum(1 for i in range(st_ + 1, k + 1) if m[i] < m[i - 1] * 0.97)
    s0 = m[st_]; cum = (s0 - m[k]) / s0
    days = sorted(d for d in sr if (rs - dt.timedelta(days=21)).isoformat() <= d <= end.isoformat())
    r2 = slope = 0
    if len(days) >= 14:
        ys = [math.log(sr[d]) for d in days]; xs = list(range(len(days))); mx, my = st.mean(xs), st.mean(ys)
        sxx = sum((x - mx) ** 2 for x in xs); sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys)); ss = sum((y - my) ** 2 for y in ys)
        slope = sxy / sxx; r2 = (sxy * sxy / sxx) / ss if ss else 0
    rec = vals(sr, *WK[5]); persist = sum(1 for v in rec if v <= s0 * G.get("persist_factor", 0.9))
    ok = (steps >= G.get("min_weeks", 3) and imp >= G.get("min_clear_weeks", 2) and cum >= G.get("min_improve_ratio", 0.2)
          and s0 - m[k] >= need(s0) and persist >= min(R["persist_days"], len(rec) - 2) and slope < 0 and r2 >= G.get("min_r2", 0.4))
    return {"status": "riser" if ok else "no", "type": "gradual", "start_week": WK[st_][0].isoformat(), "start_med": round(s0), "recent_med": round(m[k]),
            "weeks_rising": steps, "improve": round(cum, 2), "places": round(s0 - m[k]), "r2": round(r2, 2), "persist": f"{persist}/{len(rec)}"}
def newrule(sr):
    N = R.get("new", {}); top = N.get("top", 50); need_d = N.get("min_days", 3)
    rec = vals(sr, *WK[5]); mb = med(vals(sr, WK[3][0], WK[4][1]), 5)
    if mb is not None and mb <= R["watch_from_rank"]: return None
    inside = sorted(d for d in sr if rs.isoformat() <= d <= end.isoformat() and sr[d] <= top)
    if not inside: return None
    first = min(sr) if sr else None
    res = {"status": "riser", "type": "new", "base_med": round(mb) if mb else None, "recent_med": round(med(rec, 1)) if rec else None,
           "days_in_top": f"{len(inside)}/{len(rec)}", "first_ranked": first, "takeoff": inside[0], "best": min(sr[d] for d in inside)}
    if len(inside) < need_d: res["flag"] = "新品冲榜，下周复核"
    return res
found = []
for (a, t) in list(idx):
    if t != "get_asin_bsr_trends" or a in head_ids: continue
    sr = series(a)
    if not sr: continue
    j = fast(sr); g = gradual(sr); nw = newrule(sr)
    if j and j["status"] == "riser" and any(k in promo for k in sr if rs.isoformat() <= k <= end.isoformat()):
        j2 = fast(sr, drop_promo=True)
        if not j2 or j2["status"] != "riser": j["flag"] = "大促周，下周复核"
    for z in (j, g):  # fast/gradual only count inside the monitored pool (top pool_max_rank); new listings below it are handled by newrule
        if z and z["status"] == "riser" and (z.get("recent_med") or 999) > R["pool_max_rank"]: z["status"] = "no"
    pick = j if j and j["status"] == "riser" else (g if g and g["status"] == "riser" else (nw if nw else (j if j and j["status"] == "watch" else None)))
    if not pick:
        if j and ("不算上升" in j.get("note", "") or "下周复核" in j.get("note", "")): found.append(dict(j, asin=a, status="excluded"))
        continue
    pick = dict(pick, asin=a, weekly_medians=[(f"{s_.month}/{s_.day}", (round(x) if x else None)) for (s_, e_), x in zip(WK, [med(vals(sr, s_, e_)) for s_, e_ in WK])])
    if pick["status"] == "riser" and pick["type"] == "fast":
        b = pick["base_med"]; days = sorted(sr); take = None
        for i, k in enumerate(days):
            if k < WK[3][0].isoformat(): continue
            rest = [sr[x] for x in days[i:]]
            if sr[k] <= b * R["persist_factor"] and sum(1 for x in rest if x > b * R["persist_factor"]) <= 1: take = k; break
        pick["takeoff"] = take
    elif pick["status"] == "riser" and pick["type"] == "gradual":
        pick["takeoff"] = pick["start_week"]
    found.append(pick)
order = {"riser": 0, "watch": 1, "excluded": 2}
found.sort(key=lambda x: (order[x["status"]], x.get("type", ""), x.get("recent_med", 999)))
json.dump(found, open(os.path.join(A.run, "risers_found.json"), "w"), ensure_ascii=False, indent=1)
print(f"last week {rs}~{end}; fast base {WK[3][0]}~{WK[4][1]}; head groups excluded: {len(cfg['tracked'])}")
for f in found:
    lab = {"fast": "🚀快速", "gradual": "📈渐进", "new": "🆕冲榜"}.get(f.get("type"), "") if f["status"] == "riser" else f["status"]
    extra = (f"base {f.get('base_med')} first ranked {f.get('first_ranked')} days in top {f.get('days_in_top')} best {f.get('best')}" if f.get("type") == "new" else
             f"base {f.get('base_med')}" if f.get("type") != "gradual" else f"start {f.get('start_med')}（{f.get('start_week')} 周起连续 {f.get('weeks_rising')} 周） R² {f.get('r2')}")
    print(f"{lab:8} {f['asin']} {extra} -> last week {f.get('recent_med')} improve {f.get('improve')} places {f.get('places')} persist {f.get('persist')} "
          f"takeoff {f.get('takeoff')} {f.get('flag','')}{f.get('note','')} weeks {f.get('weekly_medians','')}")
