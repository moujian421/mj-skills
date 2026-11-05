"""Build the riser review tab spec from data/<slug>/riser_reviews.json (newest entries first).
Usage: python3 emit_risers.py --config CFG --reviews REVIEWS.json --run RUN --date YYYY-MM-DD
REVIEWS.json: {"entries": [{"date","asin","brand","product","basic","weeks","takeoff","timeline","effect","summary","grade"}],
               "common": "共性总结（每次运行由 Claude 更新）", "method_note": "筛选口径补充（可空）", "not_listed": "未列入/观察名单说明（可空）"}"""
import json, os, sys, argparse
sys.path.insert(0, os.path.dirname(__file__))
from cfg import load_cfg
ap = argparse.ArgumentParser(); ap.add_argument("--config", required=True); ap.add_argument("--reviews", required=True)
ap.add_argument("--run", required=True); ap.add_argument("--date", required=True); A = ap.parse_args()
cfg = load_cfg(A.config); R = json.load(open(A.reviews)); rr = cfg["riser_rule"]
E = sorted(R["entries"], key=lambda e: e["date"], reverse=True)
header = ["ASIN", "品牌", "产品", "主图", "基本信息", "小类排名（周中位）", "起飞时间", "动作时间线", "效果", "打法总结", "分级", "录入日期"]
rows, styles, images = [], [], []
gc = {"A": "#E2EFDA", "B": "#FFF2CC"}
for i, e in enumerate(E, 2):
    icon = {"fast": "🚀 快速 ", "gradual": "📈 渐进 ", "new": "🆕 冲榜 "}.get(e.get("type"), "")
    rows.append([e["asin"], e["brand"], e["product"], "", e["basic"], e["weeks"], e["takeoff"], e["timeline"], e["effect"], e["summary"], icon + e["grade"], e["date"]])
    styles += [{"range": f"A{i}", "font_weight": "bold", "background_color": "#DDEBF7"},
               {"range": f"J{i}:K{i}", "background_color": gc.get(e["grade"][:1], "#F2F2F2")}]
    images.append({"cell": f"D{i}", "asin": e["asin"]})
n = len(rows) + 1
common_row = n + 1
rows.append([R.get("common", "")] + [""] * 11)
styles.append({"range": f"A{common_row}:L{common_row}", "font_weight": "bold", "background_color": "#FFF2CC", "vertical_alignment": "middle"})
gr = rr.get("gradual", {})
nr = rr.get("new", {})
foot = (f"说明：只排查头部跟踪以外的商品。候选来自卖家精灵当前数据：节点 {cfg['node_id']} 小类 BSR 前 {rr['pool_max_rank']} 每周快照初筛（比上周改善 ≥15% 或比 3~4 周前改善 ≥20%），"
        f"加上架 {cfg.get('new_listing_days', 90)} 天内、小类前 {rr['pool_max_rank']} 的新链接；再用西柚每日小类 BSR 确认，快速/渐进上升只算上一周中位在 {rr['pool_max_rank']} 名内的，三类："
        f"🚀 快速上升=上一周（周一至周日）中位数对比上上周和上上上周合计 14 天的中位数，改善 ≥{int(rr['min_improve_ratio']*100)}% 且至少上升 {rr['min_places']} 名（基准在 {rr['min_places_if_base_le']} 名以内时至少 {rr['min_places_small']} 名），"
        f"上一周至少 {rr['persist_days']} 天排名好于基准的 {rr['persist_factor']} 倍；基准期若是一次下跌（比之前两周差 20% 以上），改用下跌前的水平做基准，只是回到原水平的不算；"
        f"📈 渐进上升=连续 ≥{gr.get('min_weeks',3)} 周周中位不变差（允许 ≤{int(gr.get('rebound',0.05)*100)}% 反弹）、其中至少 {gr.get('min_clear_weeks',2)} 周明显改善，从起点累计改善 ≥{int(gr.get('min_improve_ratio',0.2)*100)}%（名次门槛同上），"
        f"上一周至少 {rr['persist_days']} 天好于起点的 {gr.get('persist_factor',0.9)} 倍，近 4 周每日排名趋势稳定（R² ≥{gr.get('min_r2',0.4)}）。"
        f"🆕 新品冲榜=基准期（上上周和上上上周）无排名或在 {rr['watch_from_rank']} 名外，上一周至少 {nr.get('min_days',3)} 天进入前 {nr.get('top',50)}；只有 1~2 天进入的也列出，标“新品冲榜，下周复核”。"
        f"上一周含大促日且去掉大促日后不达标的，标“大促周，下周复核”；基准在 {rr['watch_from_rank']} 名外、上一周进入 {rr['watch_from_rank']} 名内的列入观察名单。"
        "分级：A=自然流量得分比基准期高 20% 以上（自然流量接上了）；B=主要靠价格或广告撑；B-低参考=几乎没有搜索流量。"
        "排除：变体组拆分/合并造成的排名跳动、自身断货恢复。" + R.get("method_note", "") + R.get("not_listed", "") +
        f"数据来源西柚（价格 / Deal / 促销 / 评分数 / BSR / 流量得分 / 核心词排名 / 新增广告 / 标题主图改动），流量得分为相对值。更新日期 {A.date}。")
spec = {"tab": cfg["sheet"]["tabs"]["risers"], "header": [header], "rows": rows, "footer": foot, "ncols": 12,
        "base_styles": [{"range": f"D2:D{n}", "horizontal_alignment": "center", "vertical_alignment": "middle"}, {"range": f"F2:G{n}", "horizontal_alignment": "center"},
                        {"range": f"K2:L{n}", "horizontal_alignment": "center"}],
        "styles": styles, "images": images, "merges": [{"range": f"A{common_row}:L{common_row}"}],
        "col_sizes": [{"range": "A:A", "size": 120}, {"range": "B:B", "size": 100}, {"range": "C:C", "size": 180}, {"range": "D:D", "size": 120}, {"range": "E:E", "size": 190},
                      {"range": "F:F", "size": 150}, {"range": "G:G", "size": 150}, {"range": "H:H", "size": 480}, {"range": "I:I", "size": 320}, {"range": "J:J", "size": 320},
                      {"range": "K:K", "size": 80}, {"range": "L:L", "size": 100}],
        "row_height": 260, "footer_height": 130, "freeze": {"rows": 1, "cols": 2}, "check_col": 0}
json.dump(spec, open(os.path.join(A.run, "spec_risers.json"), "w"), ensure_ascii=False)
print("riser review spec:", len(E), "entries")
