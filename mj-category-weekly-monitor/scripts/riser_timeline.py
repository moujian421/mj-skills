"""Daily timeline + weekly summary for risers, to write the action review.
Usage: python3 riser_timeline.py --config CFG --run RUN --date D --asins A1 A2 ... [--extra-dirs ...]
Prints per ASIN: weekly medians (sub rank, organic/ad traffic, core keyword rank), grade, flags, then the daily table.
Grade: A = organic traffic score of the recent week >= 1.2x the two base weeks (natural traffic caught up);
       B = rise carried by price/ads; B-低参考 = organic score averages < 5 (almost no search traffic).
Flags: 断货恢复 (base weeks had >=3 days without price) and 变体组变化 (rating count changes >=30% in a day)."""
import json, os, sys, argparse, statistics as st, datetime as dt
sys.path.insert(0, os.path.dirname(__file__))
from cfg import load_cfg, last_complete_sunday, raw_index, run_dirs, trends
ap = argparse.ArgumentParser(); ap.add_argument("--config", required=True); ap.add_argument("--run", required=True)
ap.add_argument("--date", required=True); ap.add_argument("--asins", nargs="+", required=True); ap.add_argument("--extra-dirs", nargs="*", default=[])
A = ap.parse_args(); cfg = load_cfg(A.config); idx = raw_index(A.extra_dirs + run_dirs(A.run))
end = last_complete_sunday(A.date); rs = end - dt.timedelta(days=6); b0 = rs - dt.timedelta(days=14)
def T(a, t): return trends(idx[(a, t)]) if (a, t) in idx else {}
out = {}
for a in A.asins:
    inf, bs, tr, kw, ch, ad = (T(a, t) for t in ["get_asin_info_trends", "get_asin_bsr_trends", "get_asin_traffic_trends", "get_asin_keyword_rank_trends", "get_asin_info_change_trends", "get_asin_ad_change_trends"])
    rows = []
    for d in sorted(set(inf) | set(bs)):
        p = inf.get(d, {}).get("priceDistribution", {})
        sub = next((v.get("rank") for v in bs.get(d, {}).get("values", []) if v["categoryId"] == cfg["node_id"]), None)
        pos = {x["displayPosition"]: x.get("totalRank") for x in kw.get(d, {}).get("displayPositions", [])}
        c = ch.get(d, {}); chg = []
        if c.get("current", {}).get("title") and c["current"]["title"] != c.get("previous", {}).get("title"): chg.append("标题改")
        if c.get("current", {}).get("image", {}).get("url") and c["current"]["image"]["url"] != c.get("previous", {}).get("image", {}).get("url"): chg.append("主图改")
        s = tr.get(d, {}).get("summaryTrafficScore", {}); ps = tr.get(d, {}).get("positionTrafficScore", {})
        rows.append(dict(d=d, sub=sub, price=p.get("display"), deal=p.get("deal") or "", prime=p.get("prime") or "", strike=p.get("strikethrough") or "",
                         promo=",".join(str(x)[:30] for x in (p.get("coupon") or []) + (p.get("promotion") or [])), rat=inf.get(d, {}).get("ratings"),
                         org=s.get("organic"), adv=s.get("advertising"), sp=ps.get("sp"), sb=ps.get("sb"), sbv=ps.get("sbv"), kor=pos.get("or"), ksp=pos.get("sp"),
                         newad="+".join(x["campaignType"].upper() for x in ad.get(d, {}).get("added", [])), chg="/".join(chg)))
    def win(s_, e_): return [r for r in rows if s_.isoformat() <= r["d"] <= e_.isoformat()]
    def m(R, k, f=st.mean):
        v = [r[k] for r in R if isinstance(r[k], (int, float))]; return round(f(v)) if v else None
    base, rec = win(b0, rs - dt.timedelta(days=1)), win(rs, end)
    ob, orc = m(base, "org"), m(rec, "org")
    grade = "B-低参考" if (orc or 0) < 5 and (ob or 0) < 5 else ("A" if ob and orc and orc >= ob * 1.2 else "B")
    flags = []
    if sum(1 for r in base if not r["price"]) >= 3: flags.append("断货恢复（基准期有断货，上升可能只是恢复）")
    rat = [(r["d"], r["rat"]) for r in rows if r["rat"]]
    if any(abs(b - a) / a >= 0.3 for (_, a), (_, b) in zip(rat, rat[1:])): flags.append("变体组变化（评分数单日变动≥30%）")
    wk = []
    for i in range(5, -1, -1):
        s_ = rs - dt.timedelta(days=7 * i); R = win(s_, s_ + dt.timedelta(days=6))
        wk.append({"week": f"{s_.month}/{s_.day}", "sub_med": m(R, "sub", st.median), "org": m(R, "org"), "adv": m(R, "adv"), "sp": m(R, "sp"), "kw_or_med": m(R, "kor", st.median)})
    out[a] = {"grade": grade, "flags": flags, "weeks": wk, "days": rows}
    print(f"===== {a} 分级 {grade} {'；'.join(flags)}")
    for w in wk: print(f"  {w['week']:>6} 小类中位 {w['sub_med']}  自然 {w['org']}  广告 {w['adv']}(SP {w['sp']})  核心词自然位中位 {w['kw_or_med']}")
    print("  date   sub  price  deal  prime strike promo                | rat | org  adv(sp/sb/sbv) | kwOR kwSP | newad chg")
    for r in rows[-49:]:
        print(f"  {r['d'][5:]} {str(r['sub']):>4} {str(r['price']):>6} {r['deal']:>5} {r['prime']:>5} {r['strike']:>6} {r['promo'][:20]:20} | {str(r['rat']):>4} | {str(r['org']):>4} {str(r['adv']):>4}({r['sp']}/{r['sb']}/{r['sbv']}) | {str(r['kor']):>4} {str(r['ksp']):>4} | {r['newad']} {r['chg']}")
json.dump(out, open(os.path.join(A.run, "riser_timeline.json"), "w"), ensure_ascii=False)
