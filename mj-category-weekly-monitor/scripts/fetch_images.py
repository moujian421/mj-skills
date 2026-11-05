"""Download 200px main images into the category image cache (skips files that exist).
Usage: python3 fetch_images.py --dir IMG_DIR --asins A1 A2 ... [--snapshot SNAP.json] [--map URLS.json] [--sales SALES_PULL_DIR]
URL sources in order: --map {asin:url}, snapshot rows, Xiyou sales ranking (primary image). Prints ASINs still missing;
for those, query SellerSprite product_research (includeBrands, returnFields asin,imageUrl) and pass the result via --map."""
import json, os, sys, glob, argparse, urllib.request
ap = argparse.ArgumentParser(); ap.add_argument("--dir", required=True); ap.add_argument("--asins", nargs="+", required=True)
ap.add_argument("--snapshot"); ap.add_argument("--map"); ap.add_argument("--sales"); A = ap.parse_args()
os.makedirs(A.dir, exist_ok=True); url = {}
if A.sales:
    for f in glob.glob(os.path.join(A.sales, "**", "raw", "get_category_sales_ranking_*.json"), recursive=True):
        for x in json.load(open(f))["data"]["list"]:
            for m in x["metrics"]["variation"].get("matchedAsins", []) + [{"asin": x["asinInfo"]["primaryAsin"]}]:
                url.setdefault(m["asin"], x["asinInfo"].get("imageUrl"))
if A.snapshot:
    for r in json.load(open(A.snapshot))["rows"]:
        if r.get("image"): url[r["asin"]] = r["image"]
if A.map: url.update(json.load(open(A.map)))
missing = []
for a in A.asins:
    f = os.path.join(A.dir, a + ".jpg")
    if os.path.exists(f) and os.path.getsize(f) > 1000: continue
    u = url.get(a)
    if not u: missing.append(a); continue
    u = u.replace("_AC_UL320_", "_AC_US200_")
    try:
        urllib.request.urlretrieve(u, f)
        if open(f, "rb").read(3) != b"\xff\xd8\xff": os.remove(f); missing.append(a)
    except Exception: missing.append(a)
print(json.dumps({"cached": len(A.asins) - len(missing), "missing": missing}))
