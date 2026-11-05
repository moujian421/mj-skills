"""Normalize a SellerSprite node list pull into a dated snapshot.
Usage: python3 snapshot.py --config CFG --pull OUT_DIR [OUT_DIR2 ...] --date YYYY-MM-DD --save SNAP_DIR
Snapshot rows: asin, parent, brand, units, price, image, subrank (rank inside the configured node), listed (YYYY-MM-DD, when returned)."""
import json, glob, os, sys, argparse, datetime as dt
sys.path.insert(0, os.path.dirname(__file__))
from cfg import load_cfg
ap = argparse.ArgumentParser(); ap.add_argument("--config", required=True); ap.add_argument("--pull", nargs="+", required=True)
ap.add_argument("--date", required=True); ap.add_argument("--save", required=True); A = ap.parse_args()
cfg = load_cfg(A.config); rows = {}
src = "sellersprite"
for o in A.pull:
    for f in sorted(glob.glob(os.path.join(o, "**", "raw", "product_research_*.json"), recursive=True)):
        d = json.load(open(f)); d = d.get("data", d)
        for x in d.get("items", []):
            r = [s.get("rank") for s in x.get("subcategories") or [] if s["code"] == cfg["node_id"]]
            if not r or not r[0]: continue
            rows[x["asin"]] = {"asin": x["asin"], "parent": x.get("parent") or x["asin"], "brand": x.get("brand"),
                               "units": x.get("units"), "price": x.get("price"), "image": x.get("imageUrl"), "subrank": r[0],
                               "listed": dt.datetime.utcfromtimestamp(x["availableDate"] / 1000).date().isoformat() if x.get("availableDate") else None}
if not rows:
    # SellerSprite down: Sorftime category_products (BestSeller top 100 only, so groups ranked > 100 are missing this week)
    import re
    for o in A.pull:
        for f in sorted(glob.glob(os.path.join(o, "**", "raw", "category_products_*.json"), recursive=True)):
            for x in json.load(open(f)).get("data", []):
                r = [e[2] for e in x.get("sub_category") or [] if len(e) > 2 and str(e[1]) == cfg["node_id"]]
                if not r or not r[0]: continue
                img = (x.get("main_image") or [None])[0]
                rows[x["asin"]] = {"asin": x["asin"], "parent": x.get("parent_asin") or x["asin"], "brand": x.get("brand"),
                                   "units": x.get("monthly_sales_volume"), "price": x.get("price"),
                                   "image": re.sub(r"\.jpg$", "._AC_US200_.jpg", img) if img else None, "subrank": r[0],
                                   "listed": x.get("online_date") or None}
    if rows: src = "sorftime"
os.makedirs(A.save, exist_ok=True)
out = os.path.join(A.save, A.date + ".json")
json.dump({"date": A.date, "source": src, "rows": list(rows.values())}, open(out, "w"), ensure_ascii=False)
groups = {}
for r in rows.values(): groups[r["parent"]] = min(groups.get(r["parent"], 999), r["subrank"])
print(f"snapshot {A.date} ({src}): {len(rows)} ASINs, {len(groups)} variation groups, {sum(1 for v in groups.values() if v<=100)} groups in sub-BSR top 100 -> {out}")
