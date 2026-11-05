"""Turn weekly_rows.json into a tab spec for write_tab.py.
Usage: python3 emit_weekly.py --config CFG --run RUN --date YYYY-MM-DD"""
import json, os, sys, argparse
sys.path.insert(0, os.path.dirname(__file__))
from cfg import load_cfg, weeks
ap = argparse.ArgumentParser(); ap.add_argument("--config", required=True); ap.add_argument("--run", required=True); ap.add_argument("--date", required=True)
A = ap.parse_args(); cfg = load_cfg(A.config)
R = json.load(open(os.path.join(A.run, "weekly_rows.json")))
show = [w for w in weeks(cfg, A.date) if w[3] == "show"]
pal = ["#DDEBF7", "#FCE4D6", "#E2EFDA", "#EDE2F6"]
wc = {w[0]: pal[i % 4] for i, w in enumerate(show)}
vc = {"❌": "#FCE4E4", "✅": "#E2EFDA", "⚠": "#FFF2CC", "➖": "#F2F2F2"}
header = ["周次", "周排名", "ASIN", "品牌", "产品", "主图", "动作", "效果"]
rows, styles, images = [], [], []
for i, r in enumerate(R, 2):
    rows.append([r["w"], r["rank"] if r["rank"] is not None else "—", r["asin"], r["brand"], r["name"], "",
                 "\n".join(f"{k}. {a}" for k, a in enumerate(r["acts"], 1)), "\n".join(r["eff"])])
    styles.append({"range": f"A{i}", "background_color": wc[r["w"]], "font_weight": "bold"})
    if r["riser"]:
        styles += [{"range": f"H{i}", "background_color": "#F4B183", "font_color": "#9C0006", "font_weight": "bold"},
                   {"range": f"B{i}", "font_color": "#9C0006", "font_weight": "bold"}]
    else:
        styles.append({"range": f"H{i}", "background_color": vc.get(r["eff"][0][0], "#FFFFFF")})
    images.append({"cell": f"F{i}", "asin": r["asin"]})
kwtxt = "；".join(f"{t}：{k}" for t, k in cfg.get("keyword_by_type", {}).items())
ris = cfg.get("risers", [])
foot = ("说明：数据来源西柚（价格/Deal/划线价/评分数/BSR/流量得分/核心词自然位/新增广告活动）。"
  f"跟踪对象=西柚 {cfg.get('rank_month','上月')} 类目销量榜（按变体组合并销量）中、属于亚马逊子类 {cfg['category_name']}（节点 {cfg['node_id']}）且小类 BSR 前 {cfg.get('top_bsr_max',50)} 的前 {cfg.get('top_n',15)} 个变体组，每组跟踪当月销量最高的子 ASIN；只列出当周有动作的 ASIN。"
  "周排名=当周周六、周日两天小类 BSR 的中位数，每周内按周排名从高到低排列。"
  + (f"另外加入 {len(ris)} 个排名上升商品（{'、'.join(x['brand']+' '+x['asin'] for x in ris)}），只在发现它的那一周（发现时的上一周）列一行，效果列以“🚀 重点：快速上升”“📈 重点：渐进上升”或“🆕 重点：新品冲榜”开头并用橙色底标出，第二行写起飞时间（渐进上升为上升起点）；头部跟踪商品不参与上升排查；打法总结见“{cfg['sheet']['tabs'].get('risers','排名上升-动作复盘')}”页签。" if ris else "")
  + f"统计期 {show[0][1]}~{show[-1][2]}（周一至周日）；效果=本周日均值对比上周日均值，周末动作另附次周效果；小类排名与核心词自然位写作“日均（最好~最差）”，日均四舍五入取整，[x/7天上榜]=当周只有 x 天抓到排名；自然流量为西柚流量得分（相对值）；"
  f"核心词按产品分：{kwtxt}；"
  "Prime 专享价=展示价与 Prime 价相同且低于原价，Prime 专享 Deal=Deal 价与 Prime 价相同；"
  "✅提升 ❌下滑 ➖持平、有升有降或小幅波动（任一指标变化 ≥15% 才算升/降；只有一项刚过线 15%~25% 且另一项反向时标小幅波动）；⚠️=异常动作（涨价≥20%、单日降价≥30%、停广告、划线价调整、评分数骤降、断货）；"
  "变体组判断：同品牌链接评分数相同（相差≤0.2%）视为同一变体组，组内成员变化记为拆分/合并，前后两周口径不同，效果标“⚠️ 变体拆分/合并，排名不可比”。"
  + (f"大促日：{'、'.join(cfg.get('promo_days', []))}。" if cfg.get("promo_days") else "")
  + f"拉取日期 {A.date}。")
n = len(rows) + 1
spec = {"tab": cfg["sheet"]["tabs"]["weekly"], "header": [header], "rows": rows, "footer": foot, "ncols": 8,
        "base_styles": [{"range": f"B2:B{n}", "horizontal_alignment": "center"}, {"range": f"F2:F{n}", "horizontal_alignment": "center", "vertical_alignment": "middle"}],
        "styles": styles, "images": images,
        "col_sizes": [{"range": "A:A", "size": 130}, {"range": "B:B", "size": 90}, {"range": "C:C", "size": 120}, {"range": "D:D", "size": 110}, {"range": "E:E", "size": 200},
                      {"range": "F:F", "size": 110}, {"range": "G:G", "size": 440}, {"range": "H:H", "size": 400}],
        "row_height": 110, "footer_height": 230, "freeze": {"rows": 1, "cols": 3}, "check_col": 2}
json.dump(spec, open(os.path.join(A.run, "spec_weekly.json"), "w"), ensure_ascii=False)
print("weekly spec:", len(rows), "rows,", sum(1 for r in R if r["riser"]), "riser rows ->", os.path.join(A.run, "spec_weekly.json"))
