#!/usr/bin/env python3
"""按本次的规则文件把 skeleton.json 预分类成 classified.json，之后人工复核再跑 build_sheets.py。

用法: python3 classify.py OUT/rules.py OUT/skeleton.json OUT/classified.json
规则文件写法见 references/rules_example_cutting_board.py（属性字典、品牌、外语、宽泛词、核心词、拼写变体、词组/精准否定）。
stdout 打印各优先级词数、宽泛词清单，以及"没命中任何属性、也不是品牌/核心/外语"的长尾词——这些要人工过目，
常常能发现漏掉的品牌、材质和否词，补进规则文件后重跑。
"""
import importlib.util, json, re, sys
spec = importlib.util.spec_from_file_location("rules", sys.argv[1])
rules = importlib.util.module_from_spec(spec); spec.loader.exec_module(rules)
ATTRIBUTES, BRANDS, FOREIGN, BROAD, CORE = rules.ATTRIBUTES, rules.BRANDS, rules.FOREIGN, rules.BROAD, rules.CORE
TYPOS, PHRASE_NEG, EXACT_NEG = getattr(rules, "TYPOS", set()), rules.PHRASE_NEG, rules.EXACT_NEG
SKU = getattr(rules, "SKU", "通用（未提供SKU）")
PROTECTED = getattr(rules, "PROTECTED_ROOTS", [])
ATTR_PRIORITY = getattr(rules, "ATTR_PRIORITY", list(ATTRIBUTES))
# 低价/批量意图词进「C 低预算探索」：规则文件可给 CHEAP，否则取属性里名字带"低价"的写法
CHEAP = getattr(rules, "CHEAP", [p for vals in ATTRIBUTES.values() for v, ps in vals.items() if "低价" in v for p in ps])

def has(k, p):
    if p.startswith("re:"):
        return re.search(p[3:], k) is not None
    return re.search(r"(^|[\s-])" + re.escape(p) + r"(e?s)?($|[\s-])", k) is not None

sk = json.load(open(sys.argv[2]))
vol = sk["volumes"]
phr = [p for p, _ in PHRASE_NEG]
exact = {k: (r, st) for k, r, st in EXACT_NEG}
ad, neg, review = [], [], []
for r in sk["ad"]:
    k = r["keyword"]
    if any(has(k, p) for p in phr):
        continue  # 被词组否定挡住，build_sheets 自动计入
    if k in exact:
        rs, st = exact[k]
        neg.append({"keyword": k, "match": "精准否定", "status": st, "sku": SKU, "reason": rs,
                    "searches": r["ss"].get("searches"), "rank": r["ss"].get("search_rank"), "bid": r["ss"].get("bid")})
        continue
    s = r["ss"].get("searches") or 0
    rel = r["ss"].get("relevancy")
    brand = next((b for b in BRANDS if has(k, b)), None)
    foreign = any(has(k, f) for f in FOREIGN)
    if re.search(r"[\u4e00-\u9fff]", k):
        r["lang"] = "中文"
    elif re.search(r"[\uac00-\ud7af]", k):
        r["lang"] = "韩语"
    elif foreign:
        r["lang"] = "葡语" if re.search(r"\b(tabua|carne)\b", k) else "西语"
    elif k in TYPOS:
        r["lang"] = "拼写错误"
    if brand:
        r["kw_type"] = "品牌词"
        r["brand"] = brand
        r.update(category="竞品品牌", priority="C 竞品测试", use="独立竞品精准广告；不写进自家标题、五点和后台词",
                 note=f"品牌：{brand}")
    elif foreign:
        r["kw_type_fallback"] = "核心词"  # 外语词没命中任何属性时，多半就是"菜板"的直接叫法
        r.update(category="核心品类/同义词" if s >= 2000 else "长尾/场景", priority="A2 补充核心" if s >= 2000 else "B 长尾测试",
                 use="精准广告", note="外语词（西语/中文），不写入英文文案")
    elif k in BROAD:
        r["kw_type"] = "宽泛词"
        r.update(category="宽泛/促销意图", priority="C 低预算探索", use="小额精准，不开宽泛匹配",
                 note="意图混杂（可能是拼盘/台面/原材料），待西柚反查首页同类占比后定级")
        review.append(k)
    elif k in TYPOS:
        r["kw_type"] = "核心词"
        r.update(category="核心品类/同义词", priority="A2 补充核心" if s >= 2000 else "B 长尾测试", use="精准广告", note="拼写变体，不写入文案")
    elif k in CORE:
        r["kw_type"] = "核心词"
        r.update(category="核心品类/同义词", priority="A1 首批核心" if s >= 2000 else ("A2 补充核心" if s > 0 else "B 长尾测试"),
                 use="标题/五点自然覆盖；精准/词组广告", note="")
    else:
        cheap = any(has(k, p) for p in CHEAP)
        if cheap:
            r.update(category="宽泛/促销意图", priority="C 低预算探索", use="小额精准，不开宽泛匹配",
                     note="低价/批量意图，转化和客单价可能偏低")
        elif r.get("route") == "keep_long" or r.get("route") == "ac_only":
            r.update(category="长尾/场景", priority="B 长尾测试", use="精准小额测试",
                     note=r.get("note") or "")
        elif s >= 10000:
            r.update(category="长尾/场景", priority="A2 补充核心", use="精准广告；属性与自家款一致时写入标题/五点",
                     note="属性大词：材质/尺寸等与自家款一致才投，不一致改精准否定")
        else:
            r.update(category="长尾/场景", priority="B 长尾测试", use="精准小额测试",
                     note="款式不符时改为精准否定")
    ad.append(r)

for p, rs in PHRASE_NEG:
    neg.append({"keyword": p, "match": "词组否定", "status": "建议启用", "sku": SKU, "reason": rs,
                "searches": vol.get(p), "rank": sk["ranks"].get(p), "bid": None})
attrs = {}
for dim, vals in ATTRIBUTES.items():
    attrs[dim] = vals
out = {"meta": {"ad_sheet": "类目广告词库", "neg_sheet": "类目否词库", "attr_sheet": "类目属性分析",
                "protected_roots": PROTECTED,
                "attributes": attrs, "attr_priority": ATTR_PRIORITY,
                "volume_tiers": [[10000, "大词"], [50000, "中词"], [200000, "小词"]]},
       "ad": ad, "neg": neg, "all_keywords": sk["all_keywords"], "excluded": sk["excluded"],
       "watch_keywords": sk["watch_keywords"], "volumes": sk["volumes"], "ranks": sk["ranks"]}
old = json.load(open(sys.argv[3])) if __import__("os").path.exists(sys.argv[3]) else {}
for k in ("ad_note", "neg_note", "attr_note"):  # 重跑时保留已写好的表底说明
    if old.get("meta", {}).get(k):
        out["meta"][k] = old["meta"][k]
json.dump(out, open(sys.argv[3], "w"), ensure_ascii=False, indent=1)
from collections import Counter
print("ad", len(ad), Counter(r["priority"] for r in ad))
print("neg", len(neg), "phrase", len(PHRASE_NEG))
print("review(宽泛/低相关度):", review)
# 没命中任何属性、也不是品牌/核心/外语的词，供人工过目
from itertools import chain
def anyattr(k):
    return any(has(k, p) for vals in ATTRIBUTES.values() for ps in vals.values() for p in ps)
res = [r["keyword"] for r in ad if r["category"] == "长尾/场景" and not anyattr(r["keyword"]) and "外语" not in r["note"]]
print(f"无属性长尾 {len(res)}:", "; ".join(res))
