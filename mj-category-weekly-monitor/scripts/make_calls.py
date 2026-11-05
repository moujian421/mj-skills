"""Write calls.txt for oc_pull.sh (batch-offload) for one stage.
Usage: python3 make_calls.py STAGE --config CFG --out CALLS.txt --date YYYY-MM-DD --task "user's original words" [options]
Stages:
  snapshot     SellerSprite node list, current data (no month; variation=Y, 5 pages x 100) - free, weekly
  sales_rank   Xiyou category sales ranking for --month (top 30, ~30 credits) - monthly top-N refresh
  daily        Xiyou daily info/bsr/traffic/ad_change/keyword for tracked + risers (+ info only for siblings); --asins FILE limits it
  riser_bsr    Xiyou daily BSR for candidate ASINs listed in --asins FILE (one per line)
  new_listing  SellerSprite node list, current data, newest listings first, sub rank <= pool_max_rank (free) - weekly new-listing candidates
  riser_extra  Xiyou listing changes + basic info for confirmed new risers (--asins FILE)
  daily_snap   SellerSprite node list page 1 with titles (free) - daily monitor
  daily_sorftime Sorftime category_products (BestSeller top 100) - daily monitor fallback
  daily_price  Xiyou info_trends, last 6 days, for --asins FILE (~1 credit each) - daily monitor
  daily_ads    Xiyou ad_change_trends, last 6 days, for --asins FILE - daily monitor
  market_ss    SellerSprite market_research_statistics for 24 months ending --month (free)
  market_xy    Xiyou market size trends + category keywords (~33 credits)
"""
import json, sys, argparse, datetime as dt, os
sys.path.insert(0, os.path.dirname(__file__))
from cfg import load_cfg, pull_range, all_items, weeks

ap = argparse.ArgumentParser()
ap.add_argument("stage"); ap.add_argument("--config", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--date", required=True); ap.add_argument("--task", required=True)
ap.add_argument("--month"); ap.add_argument("--asins")
A = ap.parse_args()
cfg = load_cfg(A.config); xy = cfg["xiyou"]; L = []
def X(tool, p, intent): L.append(f'tools["xydc-mcp"]["{tool}"]({json.dumps(dict(p, user_task=A.task, intent_summary=intent), ensure_ascii=False)})')
def SS(tool, p): L.append(f'tools["sellersprite-mcp"]["{tool}"]({json.dumps(p, ensure_ascii=False)})')
prev_month = (dt.date.fromisoformat(A.date).replace(day=1) - dt.timedelta(days=1)).strftime("%Y-%m")
month = A.month or prev_month
s, e = pull_range(cfg, A.date)

if A.stage == "snapshot":
    for p in range(1, 6):
        # no "month": SellerSprite then returns current data (sub rank ~1 day old, units = last 30 days). With month=last month
        # every snapshot in the same month is identical and the prefilter finds nothing (found 2026-10-26).
        SS("product_research", {"request": {"marketplace": cfg["marketplace"], "nodeIdPath": cfg["node_path"],
            "nodeIdPathEqual": True, "variation": "Y", "order": {"field": "total_units", "desc": True}, "page": p, "size": 100,
            "returnFields": "asin,parent,brand,units,price,imageUrl,subcategories,availableDate"}})
elif A.stage == "sales_rank":
    X("get_category_sales_ranking", {"country": cfg["marketplace"], "categoryId": xy["categoryId"], "resourceId": xy["resourceId"], "reportPeriod": month,
      "orders": [{"field": "sales", "direction": "desc"}], "page": 1, "pageSize": 30}, f"取{month}类目销量榜（按变体组合并），按节点过滤后选头部{cfg['top_n']}")
elif A.stage == "daily":
    T = {"get_asin_info_trends": "拉每日价格、Deal、划线价、评分数，用于按周记录动作",
         "get_asin_bsr_trends": "拉每日小类BSR，用于按周计算效果",
         "get_asin_traffic_trends": "拉每日自然与广告流量得分，用于按周计算效果",
         "get_asin_ad_change_trends": "拉新增广告活动，识别广告加投"}
    only = {x.strip() for x in open(A.asins) if x.strip()} if A.asins else None  # --asins: pull just these (e.g. new risers)
    for a, it in all_items(cfg).items():
        if only is not None and a not in only: continue
        if it["role"] == "riser" and only is None and it.get("detected_week") and it["detected_week"] < weeks(cfg, A.date)[-2][1] and not it.get("recheck"):
            continue  # risers found in an earlier week: their row is cached in riser_rows.json (recheck=true ones are pulled again for the recheck)
        b = {"asin": a, "country": cfg["marketplace"], "start_date": s, "end_date": e}
        if it["role"] == "sibling":
            X("get_asin_info_trends", b, "拉同变体组兄弟链接的评分数，用于判断变体组拆分/合并"); continue
        for t, i in T.items(): X(t, b, i)
        if it.get("keyword"):
            X("get_asin_keyword_rank_trends", dict(b, keyword=it["keyword"]), "拉核心词自然位每日排名，用于按周计算效果")
elif A.stage == "riser_bsr":
    s3 = (dt.date.fromisoformat(A.date) - dt.timedelta(days=42)).isoformat()  # 6 weeks: fast rule, dip check, gradual streak
    for a in [x.strip() for x in open(A.asins) if x.strip()]:
        X("get_asin_bsr_trends", {"asin": a, "country": cfg["marketplace"], "start_date": s3, "end_date": e}, "拉每日小类BSR（6周），判断是否快速或渐进地稳定上升")
elif A.stage == "new_listing":
    # new-listing candidates: current data, newest 200 listings (the API ignores maxSubBsrRank, tested 2026-10-26);
    # riser_scan.py supplement keeps the ones listed within new_listing_days (default 90) and inside pool_max_rank
    for p in (1, 2):
        SS("product_research", {"request": {"marketplace": cfg["marketplace"], "nodeIdPath": cfg["node_path"], "nodeIdPathEqual": True,
            "variation": "Y", "order": {"field": "available_date", "desc": True},
            "page": p, "size": 100, "returnFields": "asin,parent,brand,units,price,imageUrl,subcategories,availableDate"}})
elif A.stage == "riser_extra":
    asins = [x.strip() for x in open(A.asins) if x.strip()]
    X("get_asin_info", {"asins": asins, "country": cfg["marketplace"]}, "查上升商品基本信息（标题、上架时间、价格、评分、配送）")
    s8 = (dt.date.fromisoformat(A.date) - dt.timedelta(days=70)).isoformat()
    for a in asins:
        X("get_asin_info_change_trends", {"asin": a, "country": cfg["marketplace"], "start_date": s8, "end_date": e}, "查标题、主图改动，识别排名上升前后的Listing优化")
elif A.stage == "daily_snap":
    # daily monitor: current node list, 2 pages by units. Top 20 groups sat within the first 35 rows (2026-10-26);
    # the 2nd page covers most of the sub-BSR top 100 for the daily rank history (riser pool)
    for p in (1, 2):
        SS("product_research", {"request": {"marketplace": cfg["marketplace"], "nodeIdPath": cfg["node_path"],
            "nodeIdPathEqual": True, "variation": "Y", "order": {"field": "total_units", "desc": True}, "page": p, "size": 100,
            "returnFields": "asin,parent,brand,title,units,price,imageUrl,subcategories"}})
elif A.stage == "daily_sorftime":
    # daily monitor fallback when SellerSprite is down: Sorftime BestSeller top 100 of the node, one call
    L.append(f'tools["sorftime-mcp"]["category_products"]({json.dumps({"amz_site": cfg["marketplace"], "node_id": cfg["node_id"]})})')
elif A.stage in ("daily_price", "daily_ads"):
    # daily monitor: last ~6 days (Xiyou lags ~2 days; the extra days give the baseline before the 2-day window)
    s6 = (dt.date.fromisoformat(A.date) - dt.timedelta(days=6)).isoformat()
    tool, intent = (("get_asin_info_trends", "拉近几天每日价格、Deal、Prime价、优惠券，判断近2天是否降价") if A.stage == "daily_price"
                    else ("get_asin_ad_change_trends", "拉近几天新增广告活动，补充降价竞品的其他动作"))
    for a in [x.strip() for x in open(A.asins) if x.strip()]:
        X(tool, {"asin": a, "country": cfg["marketplace"], "start_date": s6, "end_date": e}, intent)
elif A.stage == "market_ss":
    y, m = map(int, month.split("-"))
    ms = []
    for _ in range(24):
        ms.append(f"{y}{m:02d}"); m -= 1
        if m == 0: y, m = y - 1, 12
    for mo in reversed(ms):
        SS("market_research_statistics", {"request": {"marketplace": cfg["marketplace"], "nodeIdPath": cfg["node_path"], "month": mo}})
elif A.stage == "market_xy":
    b = {"country": cfg["marketplace"], "categoryId": xy["categoryId"], "resourceId": xy["resourceId"]}
    X("get_category_market_size_trends", b, "拉类目月度销量/销售额趋势，用于大盘月度表")
    X("get_category_keywords", dict(b, filters={"correlationTypes": ["high"]}, page=1, pageSize=60, includeTrend=True), "拉类目高相关关键词及月度趋势，用于核心词月度表")
else:
    sys.exit("unknown stage")
open(A.out, "w").write("\n".join(L) + "\n")
print(A.stage, len(L), "calls ->", A.out, f"(range {s}~{e})" if A.stage in ("daily", "riser_bsr") else "")
