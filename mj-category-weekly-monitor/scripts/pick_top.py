"""Pick the top-N variation groups for the month (Xiyou sales, merged by variation) that sit in the node's sub-BSR top K.
Usage: python3 pick_top.py --config CFG --sales SALES_PULL_DIR --snapshot SNAP.json [--write]
Prints the proposal; --write replaces cfg.tracked (keeps name/keyword of ASINs already tracked).
cfg.exclude_asins: groups that are in the node but not the same product (e.g. ab mats among floor mats) are skipped.
New entries get a placeholder name/keyword: review and edit them in the config before the daily pull."""
import json, glob, os, sys, argparse
sys.path.insert(0, os.path.dirname(__file__))
from cfg import load_cfg, save_cfg
ap = argparse.ArgumentParser(); ap.add_argument("--config", required=True); ap.add_argument("--sales", required=True)
ap.add_argument("--snapshot", required=True); ap.add_argument("--write", action="store_true"); A = ap.parse_args()
cfg = load_cfg(A.config); snap = json.load(open(A.snapshot))
ok = {}
for r in snap["rows"]:
    if r["subrank"] <= cfg.get("top_bsr_max", 50):
        ok[r["asin"]] = min(ok.get(r["asin"], 999), r["subrank"]); ok[r["parent"]] = min(ok.get(r["parent"], 999), r["subrank"])
f = sorted(glob.glob(os.path.join(A.sales, "**", "raw", "get_category_sales_ranking_*.json"), recursive=True))[0]
data = json.load(open(f))["data"]; L = data["list"]
old = {t["asin"]: t for t in cfg.get("tracked", [])}
sel = []
for x in L:
    a = x["asinInfo"]; kids = x["metrics"]["variation"].get("matchedAsins", [])
    ids = [a["primaryAsin"]] + [m["asin"] for m in kids]
    hit = [ok[i] for i in ids if i in ok]
    if not hit: continue
    if set(ids) & set(cfg.get("exclude_asins", [])): print("剔除（config exclude_asins）:", a["primaryAsin"], a["brand"]); continue
    kids_sorted = sorted(kids, key=lambda m: m["sales"] or 0, reverse=True) or [{"asin": a["primaryAsin"], "sales": None}]
    top = kids_sorted[0]["asin"]
    same = [i for i in ids if i in old]  # group already tracked under another child: keep that child so history continues
    if same and top not in old: top = same[0]
    t = old.get(top, {"asin": top, "brand": a["brand"], "name": f"{a['brand']} {top}（待改名）", "keyword": None, "siblings": []})
    t = dict(t, rank=len(sel) + 1, primary=a["primaryAsin"], group_sales=x["metrics"]["sales"]["value"], subbsr=min(hit), image_url=a.get("imageUrl"))
    if top not in old:  # siblings help detect variation split/merge; keep the 3 best-selling other children
        t["siblings"] = [{"asin": m["asin"], "name": f"{a['brand']} {m['asin']}", "short": m["asin"][-4:]} for m in kids_sorted[1:4]]
    sel.append(t)
# Xiyou sometimes returns null sales for a whole group for the month (EASEGO 2026-10): such groups drop out of the
# sales-desc list. Keep tracked groups that are missing from the list but still in the node's sub-BSR top K,
# ranked by last month's group sales.
seen = {i for x in L for i in [x["asinInfo"]["primaryAsin"]] + [m["asin"] for m in x["metrics"]["variation"].get("matchedAsins", [])]}
for a, t in old.items():
    if a in seen or t.get("primary") in seen: continue
    sb = min([ok[i] for i in (a, t.get("primary")) if i in ok] or [999])
    if sb > cfg.get("top_bsr_max", 50) or not t.get("group_sales"): continue
    print(f"西柚当月无销量数据，按上月销量保留: {a} {t['name']} 小类BSR {sb}")
    sel.append(dict(t, subbsr=sb))
sel = sorted(sel, key=lambda t: -(t.get("group_sales") or 0))[:cfg.get("top_n", 15)]
for i, t in enumerate(sel): t["rank"] = i + 1
for t in sel:
    print(f"{t['rank']:>2} {t['asin']} {t['brand'][:12]:12} 组销量 {t['group_sales']:>6} 小类BSR {t['subbsr']:>3} {'(新)' if t['asin'] not in old else ''} {t['name']}")
dropped = [a for a in old if a not in {t['asin'] for t in sel}]
print("掉出前列:", dropped or "无")
if len(sel) < cfg.get("top_n", 15): print(f"只有 {len(sel)} 个满足条件：需要拉第 2 页销量榜（page=2）")
if A.write:
    cfg["tracked"] = sel; cfg["rank_month"] = data["dateRange"]["fromDate"][:7]; save_cfg(cfg, A.config); print("config updated")
