#!/usr/bin/env python3
"""把分好类的关键词 JSON 转成飞书可写入的 CSV + 样式 JSON，并检查词组否定是否误伤广告词。

用法:
    python3 build_sheets.py input.json OUT_DIR

input.json 结构（缺失的指标填 null）:
{
  "meta": {
    "ad_sheet": "类目广告词库", "neg_sheet": "类目否词库",
    "protected_roots": ["umbrella", "cooler", "phone holder"],   # 自家卖点/自带配件，不可做词组否定
    "ad_note": "表底说明…", "neg_note": "表底说明…", "attr_note": "表底说明…",
    "attr_sheet": "类目属性分析",
    "volume_tiers": [[10000, "大词"], [50000, "中词"], [200000, "小词"]],   # 按 ABA 排名分档，超出最后一档=长尾；无排名再分"无ABA·有月搜"和"无量·待验"（只在下拉框）
    "attributes": {"材质": {"竹 bamboo": ["bamboo"], "塑料 plastic": ["plastic", "poly"]},
                   "尺寸": {"大号 large": ["large", "big", "xl", "extra large"]}}
                   # 维度 -> 值 -> 写法；写法按整词匹配并兼容末尾 s，以 "re:" 开头则按正则匹配
  },
  "volumes": {"kw": 1234},                  # merge_sources.py 输出：全部拓词的月搜索量，算否词命中量和属性分析
  "ranks": {"kw": 56789},                   # merge_sources.py 输出：全部拓词的 ABA 排名
  "ad": [{
    "keyword": "golf push cart", "cn": "高尔夫手推车",
    "category": "核心品类/同义词", "priority": "A1 首批核心",
    "use": "标题/Highlight/五点自然覆盖；精准/词组广告", "note": "…",
    "highlight": false,                     # true = 整行黄底（被复核升级/降级的词）
    "ac": true,                             # 是否在亚马逊下拉框出现（merge_sources.py 自动填）
    "ss":  {"searches":49946,"purchases":709,"purchase_rate":0.0142,"search_rank":27565,
            "relevancy":100,"products":3160,"ad_products":50,"bid":3.03,"bid_min":2.27,
            "bid_max":3.79,"monopoly":0.3633},          # 卖家精灵（月）
    "xy":  {"weekly":7298,"rank":26377,"cvr":0.0509,"difficulty":54,"cpc":1.33},  # 西柚（周）
    "aba": {"top1":"B0GZ3WLYNG（EASEGO）","top1_click":0.223,"top1_conv":0.184,
            "top3_click":0.363,"top3_conv":0.274}       # ABA（周）
  }],
  "all_keywords": ["…"],                    # 可选：全部拓词（merge_sources.py 会输出），用来查漏；
                                            # 已被词组否定挡住的拓词自动算已分类，单独计数
  "watch_keywords": ["…"],                  # 可选：merge 输出的被硬规则排除但带保留信号的词，检查词组否定是否误伤
  "excluded": ["…"],                        # 可选：决定不收录的词
  "neg": [{
    "keyword":"electric","match":"词组否定","status":"建议启用","sku":"GC1 / GC2",
    "reason":"电动、遥控或电池需求","searches":null,"rank":null,"bid":null,
    "examples":"可不填：词组否定会按全部拓词自动算命中词数、命中量和示例"
  }]
}

输出: ad.csv, neg.csv, attr.csv（有 attributes 时）, *_note.csv, styles.json，并在 stdout 打印
行数、筛选范围、备注行号，以及词组否定的冲突警告。
"""
import csv, json, re, sys
from pathlib import Path

PRIO_ORDER = ["A1 首批核心", "A2 补充核心", "B 长尾测试", "C 竞品测试", "C 低预算探索"]
PRIO_BG = {"A1 首批核心": "#D9F2DF", "A2 补充核心": "#EAF7EE", "B 长尾测试": "#FFF4E5",
           "C 竞品测试": "#F3EEFB", "C 低预算探索": "#F2F3F5"}
STATUS_BG = {"建议启用": "#D9F2DF", "按搜索词报告启用": "#FFF4E5"}
NA = "n.a."

AD_COLS = [  # (表头, 取值函数, 数字格式, 分组)
    ("关键词", lambda r: r["keyword"], None, "base"),
    ("中文需求", lambda r: r.get("cn", ""), None, "base"),
    ("词组类别", lambda r: r["category"], None, "base"),
    ("优先级", lambda r: r["priority"], None, "base"),
    ("量级（ABA排名）", lambda r: tier(r), None, "base"),
    ("推荐用途", lambda r: r.get("use", ""), None, "base"),
    ("月搜索量", lambda r: r["ss"].get("searches"), "#,##0", "ss"),
    ("月购买量", lambda r: r["ss"].get("purchases"), "#,##0", "ss"),
    ("购买率", lambda r: r["ss"].get("purchase_rate"), "0.00%", "ss"),
    ("ABA排名", lambda r: r["ss"].get("search_rank"), "#,##0", "ss"),
    ("相关度", lambda r: r["ss"].get("relevancy"), "0.0", "ss"),
    ("商品数", lambda r: r["ss"].get("products"), "#,##0", "ss"),
    ("广告竞品数", lambda r: r["ss"].get("ad_products"), "#,##0", "ss"),
    ("建议竞价 USD", lambda r: r["ss"].get("bid"), "$0.00", "ss"),
    ("最低建议 USD", lambda r: r["ss"].get("bid_min"), "$0.00", "ss"),
    ("最高建议 USD", lambda r: r["ss"].get("bid_max"), "$0.00", "ss"),
    ("点击集中度", lambda r: r["ss"].get("monopoly"), "0.0%", "ss"),
    ("使用说明", lambda r: r.get("note", ""), None, "base"),
    ("亚马逊下拉框", lambda r: "✅" if r.get("ac") else "—", None, "ac"),
    ("西柚周搜索量", lambda r: r.get("xy", {}).get("weekly"), "#,##0", "xy"),
    ("西柚ABA排名", lambda r: r.get("xy", {}).get("rank"), "#,##0", "xy"),
    ("点击转化率", lambda r: r.get("xy", {}).get("cvr"), "0.0%", "xy"),
    ("竞争难度", lambda r: r.get("xy", {}).get("difficulty"), "0", "xy"),
    ("西柚建议竞价 USD", lambda r: r.get("xy", {}).get("cpc"), "$0.00", "xy"),
    ("单均广告费估算 USD", lambda r: (round(r["xy"]["cpc"] / r["xy"]["cvr"], 1)
        if r.get("xy", {}).get("cpc") and r.get("xy", {}).get("cvr") else None), "$0.00", "xy"),
    ("ABA Top1 点击ASIN", lambda r: r.get("aba", {}).get("top1"), None, "aba"),
    ("Top1 点击份额", lambda r: r.get("aba", {}).get("top1_click"), "0.0%", "aba"),
    ("Top1 转化份额", lambda r: r.get("aba", {}).get("top1_conv"), "0.0%", "aba"),
    ("Top3 点击份额合计", lambda r: r.get("aba", {}).get("top3_click"), "0.0%", "aba"),
    ("Top3 转化份额合计", lambda r: r.get("aba", {}).get("top3_conv"), "0.0%", "aba"),
]
HDR_BG = {"base": "#1F4E79", "ss": "#1F4E79", "ac": "#5B4A9E", "xy": "#0E7C66", "aba": "#B35C00",
          "attr": "#4E6E1F"}
NEG_COLS = ["否定关键词", "匹配方式", "启用状态", "适用SKU", "否定原因",
            "月搜索量（卖家精灵）", "ABA排名", "建议竞价 USD（卖家精灵）",
            "命中拓词数", "命中词月搜索量合计", "命中词示例（月搜索量）"]
TIER_BG = {"大词": "#FDE2E2", "中词": "#FFF0D9", "小词": "#FFF9DB", "长尾": "#F2F3F5", "无ABA·有月搜": "#FFFFFF", "无量·待验": "#FFFFFF"}
TIERS = [[10000, "大词"], [50000, "中词"], [200000, "小词"]]
ATTRS = {}


def tier(r):
    """量级按 ABA 排名分档：优先卖家精灵 searchRank，没有再用西柚 ABA 排名。"""
    rank = (r.get("ss") or {}).get("search_rank") or (r.get("xy") or {}).get("rank")
    if not rank:
        return "无ABA·有月搜" if (r.get("ss") or {}).get("searches") else "无量·待验"
    for limit, name in TIERS:
        if rank <= limit:
            return name
    return "长尾"


def attr_pats(values):
    out = []
    for val, pats in values.items():
        for pt in pats:
            if pt.startswith("re:"):
                out.append((val, re.compile(pt[3:])))
            else:
                out.append((val, re.compile(r"(^|[\s-])" + re.escape(pt.lower()) + r"(e?s)?($|[\s-])")))
    return out


def attr_of(kw, pats):
    found = []
    for val, rx in pats:
        if rx.search(kw.lower()) and val not in found:
            found.append(val)
    # 命中子类（如 "木·枫木"）就不再标父类（"木"）
    parents = {v.split("·")[0] for v in found if "·" in v}
    return "、".join(v for v in found if v not in parents)
# 列宽按表头名设置，增减列时不会错位
AD_WIDTHS = {"关键词": 230, "中文需求": 150, "关键词类型": 100, "属性组合": 150, "语种/拼写": 80,
             "词组类别": 110, "优先级": 110, "量级（ABA排名）": 90, "推荐用途": 300,
             "使用说明": 340, "ABA Top1 点击ASIN": 230}
NOTE_ROW_HEIGHT = 110


def col(i):  # 0 -> A, 26 -> AA
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def v(x):
    if x is None or x == "":
        return NA
    if isinstance(x, float) and x.is_integer():
        return int(x)
    return x


def cell(x, fmt):
    """数值列缺数据显示 n.a.；文字列留空即可。"""
    if fmt is None:
        return "" if x is None else x
    return v(x)


def border():
    return {"style": "solid", "weight": "thin", "color": "#E1E4E8"}


def phrase_conflicts(neg, ad):
    """词组否定词根如果按整词出现在广告词里，就会误伤。"""
    out = []
    for n in neg:
        if n["match"] != "词组否定":
            continue
        pat = re.compile(r"(^|\s)" + re.escape(n["keyword"].lower()) + r"(\s|$)")
        hits = [a["keyword"] for a in ad if pat.search(a["keyword"].lower())]
        if hits:
            out.append((n["keyword"], hits))
    return out


STOP = {"for", "with", "and", "the", "a", "an", "of", "to", "in", "on", "de", "para"}


def contains_phrase(text, phrase):
    return re.search(r"(^|\s)" + re.escape(phrase) + r"(\s|$)", text) is not None


def redundant_exact(neg):
    """精准否定如果已经包含某个词组否定的词根，就是多余的（词组否定已经挡住了它）。"""
    roots = [n["keyword"].lower() for n in neg if n["match"] == "词组否定"]
    out = []
    for n in neg:
        if n["match"] == "词组否定":
            continue
        k = n["keyword"].lower()
        hit = [r for r in roots if contains_phrase(k, r)]
        if hit:
            out.append({"exact": n["keyword"], "covered_by": hit})
    # 词组否定之间也可能互相包含（如 electric 和 electric golf cart），长的那个多余
    for n in neg:
        if n["match"] != "词组否定":
            continue
        k = n["keyword"].lower()
        hit = [r for r in roots if r != k and contains_phrase(k, r)]
        if hit:
            out.append({"phrase": n["keyword"], "covered_by": hit})
    return out


# 修饰词、颜色、促销词做词组否定会误伤正常的购买词，不作为词根建议
GENERIC_MODIFIERS = {"cheap", "best", "men", "mens", "women", "womens", "light", "lightweight",
                     "clearance", "sale", "new", "top", "premium", "small", "large", "big",
                     "black", "white", "red", "blue", "pink", "green", "grey", "gray"}


def phrase_suggestions(neg, ad, all_kw, protected, min_hits=3):
    """从精准否定里找可以合并成词组否定的最短词根，作为建议，需人工确认语义。
    条件：
      - 只看启用状态为「建议启用」的精准否定（「按搜索词报告启用」的是混合意图，不能整类否掉）
      - 片段为 1～2 个词，首尾不是虚词，不是通用修饰词，不是受保护词根（自家卖点/自带配件）
      - 至少覆盖 min_hits 个精准否定
      - 全部拓词里，凡是含这个片段的词都已经在否词库里（没有任何一个要投或待定的词会被误伤）
    """
    neg_l = {n["keyword"].lower() for n in neg}
    exact = [n["keyword"].lower() for n in neg if n["match"] != "词组否定" and n["status"] == "建议启用"]
    roots = {n["keyword"].lower() for n in neg if n["match"] == "词组否定"}
    # 「按搜索词报告启用」的否定是混合意图，词组否定若覆盖它们就等于强行启用，所以也算冲突
    mixed = {n["keyword"].lower() for n in neg if n["status"] != "建议启用"}
    pool = [k for k in set(all_kw) | {a["keyword"].lower() for a in ad} if k not in neg_l or k in mixed]
    cand = {}
    for k in exact:
        w = k.split()
        grams = set(w) | {" ".join(w[i:i + 2]) for i in range(len(w) - 1)}
        for g in grams:
            t = g.split()
            if t[0] in STOP or t[-1] in STOP or len(g) < 3:
                continue
            if any(x in GENERIC_MODIFIERS for x in t) or any(contains_phrase(g, pr) or contains_phrase(pr, g) for pr in protected):
                continue
            cand.setdefault(g, set()).add(k)
    out = []
    for g, ks in cand.items():
        if len(ks) < min_hits or g in roots or any(contains_phrase(a, g) for a in pool):
            continue
        out.append({"root": g, "would_replace": sorted(ks), "count": len(ks)})
    out.sort(key=lambda x: (len(x["root"].split()), -x["count"]))
    seen, best = set(), []
    for o in out:
        key = tuple(o["would_replace"])
        if key in seen:
            continue
        seen.add(key)
        best.append(o)
    return best[:15]


def duplicates(ad, neg):
    """同一个词在广告词库或否词库里重复，或者同时出现在两张表里。"""
    out, seen = [], {}
    for where, rows in (("广告词库", ad), ("否词库", neg)):
        for r in rows:
            k = r["keyword"].strip().lower()
            seen.setdefault(k, []).append(where)
    for k, w in seen.items():
        if len(w) > 1:
            out.append({"keyword": k, "in": w})
    return out


def plural_hints(neg, all_kw):
    """词组否定、精准否定不会自动覆盖复数或单数变体；拓词里有对应变体的话提示补上。"""
    negset = {n["keyword"].lower() for n in neg}
    roots = [n["keyword"].lower() for n in neg if n["match"] == "词组否定"]
    covered = lambda kw: kw in negset or any(contains_phrase(kw, r) for r in roots)
    hints = []
    for n in neg:
        k = n["keyword"].lower()
        variants = {k + "s", k[:-1]} if k.endswith("s") else {k + "s"}
        for var in variants:
            if var in negset:
                continue
            if n["match"] == "词组否定":
                pat = re.compile(r"(^|\s)" + re.escape(var) + r"(\s|$)")
                hit = [a for a in all_kw if pat.search(a) and not covered(a)]
            else:
                hit = [a for a in all_kw if a == var and not covered(a)]
            if hit:
                hints.append({"negative": n["keyword"], "variant": var, "examples": hit[:3]})
    return hints


def main():
    data = json.load(open(sys.argv[1]))
    out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    meta = data.get("meta", {})
    global TIERS, AD_COLS
    TIERS = meta.get("volume_tiers", TIERS)
    attrs = meta.get("attributes", {})
    attr_p = {dim: attr_pats(vals) for dim, vals in attrs.items()}
    base = list(AD_COLS)
    order = [d for d in meta.get("attr_priority", []) if d in attr_p] + [d for d in attr_p if d not in meta.get("attr_priority", [])]
    dims_of = lambda r: [d for d in order if attr_of(r["keyword"], attr_p[d])]

    def kw_type(r):
        """关键词类型：品牌词/核心词/宽泛词由 classify.py 标好；其余取主属性（按 attr_priority 第一个命中的维度）。"""
        if r.get("kw_type"):
            return r["kw_type"]
        d = dims_of(r)
        return f"{d[0]}词" if d else r.get("kw_type_fallback", "其他长尾")

    j = [c[0] for c in base].index("中文需求") + 1
    if attr_p:
        base = base[:j] + [("关键词类型", kw_type, None, "base"),
                           ("属性组合", lambda r: "+".join(dims_of(r)) or "—", None, "base"),
                           ("语种/拼写", lambda r: r.get("lang", "英文"), None, "base")] + base[j:]
    ins = [c[0] for c in base].index("推荐用途") + 1
    AD_COLS = base[:ins] + [(f"属性·{dim}", (lambda r, pp=pp: attr_of(r["keyword"], pp) or "—"), None, "attr")
                            for dim, pp in attr_p.items()] + base[ins:]
    vol = {k.lower(): x for k, x in data.get("volumes", {}).items()}
    all_kw_l = [k.lower() for k in data.get("all_keywords", [])]
    ad = sorted(data["ad"], key=lambda r: (PRIO_ORDER.index(r["priority"]),
                                           -(r["ss"].get("searches") or 0)))
    neg = data["neg"]
    phr = [n for n in neg if n["match"] == "词组否定"]
    ex = sorted([n for n in neg if n["match"] != "词组否定"],
                key=lambda n: (n["status"] != "建议启用", n["reason"], -(n.get("searches") or 0)))
    neg = phr + ex

    # ---------- CSV ----------
    with open(out / "ad.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([c[0] for c in AD_COLS])
        for r in ad:
            w.writerow([cell(c[1](r), c[2]) for c in AD_COLS])
    with open(out / "neg.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(NEG_COLS)
        for n in neg:
            exact = n["match"] != "词组否定"
            if exact:
                cnt, tot, exs = "—", "—", n.get("examples", "")
            else:  # 词组否定：按全部拓词自动算会挡掉哪些词
                hs = sorted([k for k in all_kw_l if contains_phrase(k, n["keyword"].lower())],
                            key=lambda k: -(vol.get(k) or 0))
                cnt = len(hs)
                known = [vol[k] for k in hs if vol.get(k)]
                tot = int(sum(known)) if known else None
                exs = n.get("examples") or "; ".join(
                    f"{k}({int(vol[k]):,})" if vol.get(k) else f"{k}(n.a.)" for k in hs[:8]) + (f" …等 {len(hs)} 个" if len(hs) > 8 else "")
            w.writerow([n["keyword"], n["match"], n["status"], n.get("sku", ""), n["reason"],
                        v(n.get("searches")), v(n.get("rank")), v(n.get("bid")) if exact else "—", cnt, v(tot) if not exact else tot, exs])
    attr_rows = []
    if attrs:
        total = sum(vol.get(k) or 0 for k in all_kw_l) or 1
        ad_l = {r["keyword"].lower() for r in ad}
        for dim, pp in attr_p.items():
            per = {}
            for k in all_kw_l:
                for val in filter(None, attr_of(k, pp).split("、")):
                    per.setdefault(val, []).append(k)
            dim_kws = {k for ks in per.values() for k in ks}
            # 有子类（如 木·枫木）的父类，加一行"木（含细分合计）"，汇总父类 + 全部子类
            for parent in {v.split("·")[0] for v in per if "·" in v}:
                fam = set(per.get(parent, [])) | {k for v, ks in per.items() if v.startswith(parent + "·") for k in ks}
                per[f"{parent}（含细分合计）"] = sorted(fam)
            block = [[dim, "（维度合计）", len(dim_kws), int(sum(vol.get(k) or 0 for k in dim_kws)),
                      round(sum(vol.get(k) or 0 for k in dim_kws) / total, 4), len(dim_kws & ad_l), ""]]
            for val, ks in sorted(per.items(), key=lambda x: -sum(vol.get(k) or 0 for k in x[1])):
                vs = int(sum(vol.get(k) or 0 for k in ks))
                top = sorted(ks, key=lambda k: -(vol.get(k) or 0))[:5]
                block.append([dim, val, len(ks), vs, round(vs / total, 4), len(set(ks) & ad_l),
                              "; ".join(f"{k}({int(vol[k]):,})" if vol.get(k) else f"{k}(n.a.)" for k in top)])
            attr_rows.append(block)
        attr_rows.sort(key=lambda b: -b[0][3])
        with open(out / "attr.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["属性维度", "属性值", "命中拓词数", "月搜索量合计", "占全部拓词搜索量", "广告词库命中数", "代表词（月搜索量）"])
            for b in attr_rows:
                w.writerows(b)
    for name, key in (("ad_note.csv", "ad_note"), ("neg_note.csv", "neg_note"), ("attr_note.csv", "attr_note")):
        with open(out / name, "w", newline="") as f:
            csv.writer(f).writerow([meta.get(key, "")])

    # ---------- 样式 ----------
    na, nn = len(ad) + 1, len(neg) + 1
    last = col(len(AD_COLS) - 1)
    cs = [{"range": f"A1:{last}{na}", "word_wrap": "auto-wrap", "vertical_alignment": "middle",
           "font_size": 10, "font_color": "#1F2329", "horizontal_alignment": "left", "border": border()},
          {"range": f"A2:A{na}", "font_weight": "bold"},
         ]
    for i, (h, _, fmt, grp) in enumerate(AD_COLS):
        c = col(i)
        cs.append({"range": f"{c}1", "font_weight": "bold", "background_color": HDR_BG[grp],
                   "font_color": "#FFFFFF", "horizontal_alignment": "center"})
        if fmt:
            cs.append({"range": f"{c}2:{c}{na}", "number_format": fmt, "horizontal_alignment": "right"})
        if grp == "xy":
            cs.append({"range": f"{c}2:{c}{na}", "background_color": "#F2FAF8"})
        if grp == "aba":
            cs.append({"range": f"{c}2:{c}{na}", "background_color": "#FFF7EE"})
        if grp in ("ac", "attr"):
            cs.append({"range": f"{c}2:{c}{na}", "horizontal_alignment": "center"})
        if grp == "attr":
            cs.append({"range": f"{c}2:{c}{na}", "background_color": "#F5F9EF"})
    heads = [c[0] for c in AD_COLS]
    pcol = col(heads.index("优先级"))
    for h in ("关键词类型", "属性组合", "主属性", "词组类别", "优先级"):
        if h in heads:
            cc = col(heads.index(h))
            cs.append({"range": f"{cc}2:{cc}{na}", "horizontal_alignment": "center"})
    top3conv = col(heads.index("Top3 转化份额合计"))
    note_col = col(heads.index("使用说明"))
    tier_col = col(heads.index("量级（ABA排名）"))
    cs.append({"range": f"{tier_col}2:{tier_col}{na}", "horizontal_alignment": "center"})
    for i, r in enumerate(ad, 2):
        cs.append({"range": f"{pcol}{i}", "background_color": PRIO_BG[r["priority"]]})
        cs.append({"range": f"{tier_col}{i}", "background_color": TIER_BG.get(tier(r), "#FFFFFF")})
        if r.get("highlight"):  # 只标关键词和使用说明，避免盖掉优先级、量级和属性底色
            cs.append({"range": f"A{i}", "background_color": "#FFF8D6"})
            cs.append({"range": f"{note_col}{i}", "background_color": "#FFF8D6"})
        for j, c in enumerate(AD_COLS):
            if cell(c[1](r), c[2]) in (NA, "—"):
                cs.append({"range": f"{col(j)}{i}", "font_color": "#8F959E"})
        a = r.get("aba", {})
        if a.get("top3_click") and a.get("top3_conv") == 0:
            cs.append({"range": f"{top3conv}{i}", "font_color": "#D83931", "font_weight": "bold"})
    an = na + 2
    # 表底说明只合并到「使用说明」列，免得要横向滚动；必须自动换行，否则会被截断
    cs.append({"range": f"A{an}:{note_col}{an}", "font_size": 9, "font_color": "#646A73", "word_wrap": "auto-wrap",
               "vertical_alignment": "top", "horizontal_alignment": "left"})
    ad_sizes = [{"range": f"{col(i)}:{col(i)}", "size": AD_WIDTHS.get(h, 125 if h.startswith("属性·") else 95)} for i, h in enumerate(heads)]

    cs2 = [{"range": f"A1:K{nn}", "word_wrap": "auto-wrap", "vertical_alignment": "middle",
            "font_size": 10, "font_color": "#1F2329", "border": border()},
           {"range": "A1:K1", "font_weight": "bold", "background_color": "#1F4E79",
            "font_color": "#FFFFFF", "horizontal_alignment": "center"},
           {"range": f"A2:A{nn}", "font_weight": "bold"},
           {"range": f"B2:D{nn}", "horizontal_alignment": "center"},
           {"range": f"F2:G{nn}", "number_format": "#,##0", "horizontal_alignment": "right"},
           {"range": f"H2:H{nn}", "number_format": "$0.00", "horizontal_alignment": "right"},
           {"range": f"I2:J{nn}", "number_format": "#,##0", "horizontal_alignment": "right"}]
    for i, n in enumerate(neg, 2):
        cs2.append({"range": f"C{i}", "background_color": STATUS_BG.get(n["status"], "#FFFFFF")})
        if n["match"] == "词组否定":
            cs2.append({"range": f"B{i}", "background_color": "#FDE2E2", "font_weight": "bold"})
            cs2.append({"range": f"H{i}", "font_color": "#8F959E"})
            cs2.append({"range": f"I{i}:J{i}", "font_weight": "bold"})
    nn2 = nn + 2
    cs2.append({"range": f"A{nn2}:K{nn2}", "font_size": 9, "font_color": "#646A73", "word_wrap": "auto-wrap",
                "vertical_alignment": "top"})

    spec = {"styles": [
        {"name": meta.get("ad_sheet", "类目广告词库"), "cell_styles": cs,
         "cell_merges": [{"range": f"A{an}:{note_col}{an}"}], "col_sizes": ad_sizes,
         "row_sizes": [{"range": "1:1", "type": "auto"}, {"range": f"2:{na}", "type": "auto"},
                       {"range": f"{an}:{an}", "size": NOTE_ROW_HEIGHT}], "freeze": {"rows": 1, "cols": 1}},
        {"name": meta.get("neg_sheet", "类目否词库"), "cell_styles": cs2,
         "cell_merges": [{"range": f"A{nn2}:K{nn2}"}],
         "col_sizes": [{"range": "A:A", "size": 200}, {"range": "B:D", "size": 110},
                       {"range": "E:E", "size": 240}, {"range": "F:J", "size": 95}, {"range": "K:K", "size": 460}],
         "row_sizes": [{"range": "1:1", "type": "auto"}, {"range": f"2:{nn}", "type": "auto"},
                       {"range": f"{nn2}:{nn2}", "size": NOTE_ROW_HEIGHT}], "freeze": {"rows": 1, "cols": 1}}]}
    attr_n = sum(len(b) for b in attr_rows) + 1
    if attr_rows:
        cs3 = [{"range": f"A1:G{attr_n}", "word_wrap": "auto-wrap", "vertical_alignment": "middle",
                "font_size": 10, "font_color": "#1F2329", "border": border()},
               {"range": "A1:G1", "font_weight": "bold", "background_color": "#4E6E1F",
                "font_color": "#FFFFFF", "horizontal_alignment": "center"},
               {"range": f"C2:D{attr_n}", "number_format": "#,##0", "horizontal_alignment": "right"},
               {"range": f"E2:E{attr_n}", "number_format": "0.0%", "horizontal_alignment": "right"},
               {"range": f"F2:F{attr_n}", "number_format": "#,##0", "horizontal_alignment": "right"},
               {"range": f"A2:A{attr_n}", "font_weight": "bold"}]
        i = 2
        for b in attr_rows:
            cs3.append({"range": f"A{i}:G{i}", "background_color": "#EAF2DD", "font_weight": "bold"})
            i += len(b)
        an3 = attr_n + 2
        cs3.append({"range": f"A{an3}:G{an3}", "font_size": 9, "font_color": "#646A73", "word_wrap": "auto-wrap",
                    "vertical_alignment": "top"})
        spec["styles"].append({"name": meta.get("attr_sheet", "类目属性分析"), "cell_styles": cs3,
            "cell_merges": [{"range": f"A{an3}:G{an3}"}],
            "col_sizes": [{"range": "A:A", "size": 110}, {"range": "B:B", "size": 180}, {"range": "C:F", "size": 110},
                          {"range": "G:G", "size": 560}],
            "row_sizes": [{"range": "1:1", "type": "auto"}, {"range": f"2:{attr_n}", "type": "auto"},
                          {"range": f"{an3}:{an3}", "size": 80}], "freeze": {"rows": 1, "cols": 2}})
    json.dump(spec, open(out / "styles.json", "w"), ensure_ascii=False)
    # lark-cli styles-put 每次最多 1000 条 cell_styles：拆成 styles_NN.json 逐个提交
    for old in out.glob("styles_*.json"):
        old.unlink()
    n = 0
    for st in spec["styles"]:
        cs_all = st["cell_styles"]
        for i in range(0, max(len(cs_all), 1), 1000):
            n += 1
            part = dict(st, cell_styles=cs_all[i:i + 1000]) if i == 0 else {"name": st["name"], "cell_styles": cs_all[i:i + 1000]}
            json.dump({"styles": [part]}, open(out / f"styles_{n:02d}.json", "w"), ensure_ascii=False)

    conflicts = phrase_conflicts(phr, ad)
    dups = duplicates(ad, neg)
    redundant = redundant_exact(neg)
    protected = [p.lower() for p in meta.get("protected_roots", [])]
    all_kw = [k.lower() for k in data.get("all_keywords", [])] or [r["keyword"].lower() for r in ad + neg]
    plurals = plural_hints(neg, all_kw)
    suggest = phrase_suggestions(neg, ad, all_kw, protected)
    classified = {r["keyword"].lower() for r in ad + neg} | {k.lower() for k in data.get("excluded", [])}
    phrase_roots = [n["keyword"].lower() for n in phr]
    blocked = [k for k in data.get("all_keywords", []) if k.lower() not in classified
               and any(contains_phrase(k.lower(), r) for r in phrase_roots)]
    blocked_set = {k.lower() for k in blocked}
    unclassified = [k for k in data.get("all_keywords", []) if k.lower() not in classified and k.lower() not in blocked_set]
    # 5. 词组否定也不能误伤 watch_keywords（被硬规则排除、但带保留信号的相关词）
    watch = [w.lower() for w in data.get("watch_keywords", [])]
    watch_hits = []
    for r in phrase_roots:
        hit = [w for w in watch if contains_phrase(w, r)]
        if hit:
            watch_hits.append({"negative": r, "would_block": hit})
    # 9. 受保护词根校验：人工写的词组否定也不能碰自家卖点/配件
    # 只拦"等于或短于受保护词根"的词组否定（如 holder、cooler）；带限定词的更长短语（如 board holder）
    # 只挡更窄的一类，是否误伤由 phrase_conflicts / phrase_coverage 判断
    protected_hits = [{"negative": r, "protected": [pr for pr in protected if contains_phrase(pr, r)]}
                      for r in phrase_roots]
    protected_hits = [h for h in protected_hits if h["protected"]]
    # 影响面清单：每个词组否定在全部拓词里会挡掉哪些词，供人工逐条过目
    watch_set = set(watch)
    ad_set = {r["keyword"].lower() for r in ad}
    coverage = []
    for n in phr:
        r = n["keyword"].lower()
        hits = [k.lower() for k in data.get("all_keywords", []) if contains_phrase(k.lower(), r)]
        coverage.append((r, n["status"], hits))
    with open(out / "phrase_coverage.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["词组否定", "启用状态", "命中拓词数", "被挡掉的拓词", "标记"])
        for r, st, hits in sorted(coverage, key=lambda x: -len(x[2])):
            for h in hits or [""]:
                mark = "⚠ 在广告词库" if h in ad_set else ("⚠ 带保留信号" if h in watch_set else "")
                w.writerow([r, st, len(hits), h, mark])
    print(json.dumps({
        "ad_rows": len(ad), "neg_rows": len(neg), "phrase_negatives": len(phr),
        "priority_counts": {p: sum(1 for r in ad if r["priority"] == p) for p in PRIO_ORDER},
        "ad_filter_range": f"A1:{last}{na}", "ad_note_cell": f"A{an}",
        "neg_filter_range": f"A1:K{nn}", "neg_note_cell": f"A{nn2}",
        "attr_rows": attr_n - 1 if attr_rows else 0, "attr_filter_range": f"A1:G{attr_n}" if attr_rows else None,
        "attr_note_cell": f"A{attr_n + 2}" if attr_rows else None,
        "tier_counts": {t: sum(1 for r in ad if tier(r) == t) for t in ["大词", "中词", "小词", "长尾", "无ABA·有月搜", "无量·待验"]},
        "attr_coverage": {dim: sum(1 for r in ad if attr_of(r["keyword"], pp)) for dim, pp in attr_p.items()},
        "kw_type_counts": dict(__import__("collections").Counter(c[1](r) for r in ad for c in AD_COLS if c[0] == "关键词类型")),
        "phrase_conflicts": [{"negative": k, "would_block": h} for k, h in conflicts],
        "duplicates": dups,
        "redundant_negatives": redundant,
        "phrase_root_suggestions": suggest,
        "plural_hints": plurals,
        "watch_conflicts": watch_hits,
        "protected_violations": protected_hits,
        "blocked_by_phrase_count": len(blocked),
        "phrase_coverage_file": str(out / "phrase_coverage.csv"),
        "phrase_coverage_top": [{"negative": r, "blocks": len(h)} for r, _, h in sorted(coverage, key=lambda x: -len(x[2]))[:10]],
        "unclassified_count": len(unclassified),
        "unclassified_sample": unclassified[:30],
    }, ensure_ascii=False, indent=2))
    if conflicts:
        print("警告：词组否定会误伤广告词（phrase_conflicts），请改为精准否定后再写入。", file=sys.stderr)
    if watch_hits:
        print("警告：词组否定会挡住被硬规则排除、但带保留信号的相关词（watch_conflicts），请人工确认。", file=sys.stderr)
    if protected_hits:
        print("警告：词组否定碰到了受保护词根（protected_violations），请改为精准否定。", file=sys.stderr)
    if redundant:
        print("警告：有精准否定（或较长的词组否定）已被词组否定覆盖（redundant_negatives），请删掉多余的。", file=sys.stderr)
    if suggest:
        print("提示：有可以合并成词组否定的短词根（phrase_root_suggestions），确认语义后可替换多条精准否定。", file=sys.stderr)
    if dups:
        print("警告：有重复或同时出现在两张表的词（duplicates），请先处理。", file=sys.stderr)
    if plurals:
        print("提示：有单复数变体没被覆盖（plural_hints），量大的请补精准否定。", file=sys.stderr)
    if unclassified:
        print(f"提示：{len(unclassified)} 个拓词既没进两张表也不在 excluded 里（unclassified），请补判或列入未收录。", file=sys.stderr)


if __name__ == "__main__":
    main()
