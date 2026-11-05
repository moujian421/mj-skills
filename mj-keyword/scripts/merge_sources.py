#!/usr/bin/env python3
"""合并卖家精灵 / 西柚 / ABA 原始数据，算门槛线并分流，输出 build_sheets.py 的骨架输入。

用法:
    python3 merge_sources.py WORK_DIR OUT_DIR [--attr "folding,3 wheel,for home"] [--tail 8]

WORK_DIR 里放原始返回（文件名前缀决定来源，内容可以是工具原样返回的 JSON，也可以只是 items/list 数组）:
    ss_*.json   卖家精灵 keyword_miner 的返回；也接受 tool-results 落盘文件（.txt 但内容是 JSON）
    xy_*.json   西柚 get_keyword_info 的返回（含 abaReport）
    ac_*.json   亚马逊下拉框拓词，amazon_autocomplete.py --json 的输出（可选，一个种子词一份）
    aba_names.json  可选：{"ASIN": "品牌或产品类型"}，用来给 ABA Top1 ASIN 加注

输出到 OUT_DIR:
    skeleton.json   {"meta":{...}, "threshold":{...}, "ad":[...], "all_keywords":[...], "excluded":[...], "neg":[]}
                    ad 里每个词带 ss/xy/aba 指标和 route（分流结果），category/priority/use/note 留空待填
    routing.csv     每个词的分流结果和原因，方便人工过一遍
stdout 打印门槛线、各路线词数、需要查西柚的词数。

分流规则（见 SKILL.md 2.1）:
    excluded_hard  月购买量为 1 或为空，且没有 ABA 排名（卖家精灵 searchRank 为空）→ 硬性未收录；
                   例外：含 --attr 核心属性词的词不受此限制，照常进入下面的门槛分流。
                   被排除但带其他保留信号（相关度/广告竞品/竞价）的词，会在 stdout 的
                   hard_excluded_with_signals 里列出来，供人工复核；这些词也写进 skeleton 的
                   watch_keywords，build_sheets.py 会检查词组否定是否误伤它们
    门槛 = 有 ABA 排名、排名最靠后的 N 个词（默认 8）的月搜索量中位数 ÷ 2
    main        搜索量 ≥ 门槛 → 正常流程
    keep_long   低于门槛或为空，但含核心属性词 / 相关度≥60 / 广告竞品≥10 / 有建议竞价 → 保留，归 B 长尾
    excluded    其余 → 不收录，报告里列出
    ac_only     只在亚马逊下拉框出现、卖家精灵没有的词 → 放进 ad 待分类（没有卖家精灵指标，不参与门槛）

下拉框（ac_*.json）只做两件事：给卖家精灵的词标上"下拉框出现"（算一条保留信号），
以及补进卖家精灵漏掉的词。它不改变硬性未收录规则。
"""
import csv, json, statistics, sys
from pathlib import Path


def load(p):
    t = Path(p).read_text()
    try:
        d = json.loads(t)
    except json.JSONDecodeError:
        start = t.find("{")
        d = json.loads(t[start:])
    if isinstance(d, list):
        return d
    data = d.get("data", d)
    if isinstance(data, list):
        return data
    return data.get("items") or data.get("list") or []


def num(x):
    if x in (None, ""):
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def main():
    args = sys.argv[1:]
    work, out = Path(args[0]), Path(args[1])
    out.mkdir(parents=True, exist_ok=True)
    attrs = []
    tail = 8
    if "--attr" in args:
        attrs = [a.strip().lower() for a in args[args.index("--attr") + 1].split(",") if a.strip()]
    if "--tail" in args:
        tail = int(args[args.index("--tail") + 1])
    names = {}
    if (work / "aba_names.json").exists():
        names = json.loads((work / "aba_names.json").read_text())

    ss, months = {}, set()
    for p in sorted(work.glob("ss_*")):
        for it in load(p):
            k = (it.get("keyword") or "").strip().lower()
            if not k:
                continue
            if it.get("month"):
                months.add(it["month"])
            ss[k] = {
                "searches": num(it.get("searches")), "purchases": num(it.get("purchases")),
                "purchase_rate": num(it.get("purchaseRate")), "search_rank": num(it.get("searchRank")),
                "relevancy": num(it.get("relevancy")), "products": num(it.get("products")),
                "ad_products": num(it.get("adProducts")), "bid": num(it.get("bid")),
                "bid_min": num(it.get("bidMin")), "bid_max": num(it.get("bidMax")),
                "monopoly": num(it.get("monopolyClickRate")), "cn": it.get("keywordCn", ""),
            }

    xy, aba, aba_period = {}, {}, set()
    for p in sorted(work.glob("xy_*")):
        for it in load(p):
            k = (it.get("searchTerm") or "").strip().lower()
            if not k:
                continue
            rep = it.get("abaReport") or {}
            cpc = (it.get("costPerClick") or {}).get("value")
            xy[k] = {"weekly": num(rep.get("weeklySearchVolume")), "rank": num(rep.get("searchFrequencyRank")),
                     "cvr": num(it.get("clickConversionRate")), "difficulty": num(it.get("competitiveDifficulty")),
                     "cpc": num(cpc)}
            tops = rep.get("topAsins") or []
            if tops:
                if rep.get("reportFromDate"):
                    aba_period.add(f'{rep["reportFromDate"]}~{rep.get("reportToDate", "")}')
                clicks = [num(t.get("clickShare")) for t in tops[:3]]
                convs = [num(t.get("conversionShare")) for t in tops[:3]]
                a1 = tops[0]["asin"]
                aba[k] = {
                    "top1": f"{a1}（{names[a1]}）" if a1 in names else a1,
                    "top1_click": clicks[0], "top1_conv": convs[0],
                    "top3_click": round(sum(c for c in clicks if c is not None), 3),
                    "top3_conv": None if any(c is None for c in convs) else round(sum(convs), 3),
                }

    ac, ac_failed = {}, {}
    for p in sorted(work.glob("ac_*")):
        d = json.loads(Path(p).read_text())
        seed = d.get("keyword", p.stem)
        if d.get("failed_requests"):
            ac_failed[seed] = f'{d["failed_requests"]}/{d.get("requests", "?")}'
        for k in d.get("all_keywords", []):
            k = k.strip().lower()
            if k:
                ac.setdefault(k, []).append(seed)

    # 门槛：同一来源（卖家精灵）的排名和搜索量。
    # 卖家精灵对小词给一个"最低档"搜索量（常见 140），这个值不是真实搜索量，取样时要跳过，
    # 否则样本全是最低档、门槛退化成"最低档÷2"，分流等于没做。
    vals = [v["searches"] for v in ss.values() if v["searches"]]
    floor = min(vals) if vals else None
    ranked_all = sorted([(v["search_rank"], v["searches"]) for v in ss.values()
                         if v["search_rank"] and v["searches"]], reverse=True)
    ranked = [x for x in ranked_all if x[1] > floor][:tail] if floor is not None else []
    if ranked:
        threshold = statistics.median([s for _, s in ranked]) / 2
        threshold_note = f"跳过最低档 {floor:.0f} 后，取排名最靠后的 {len(ranked)} 个词"
    else:
        threshold = 0
        threshold_note = f"样本全是最低档 {floor}，门槛不可用，只执行硬性规则" if floor else "没有带 ABA 排名的词，门槛不可用"

    def signals(k, v):
        out = []
        hit = [a for a in attrs if a in k]
        if hit:
            out.append("含核心属性词 " + "/".join(hit))
        if (v["relevancy"] or 0) >= 60:
            out.append(f"相关度 {v['relevancy']:.0f}")
        if (v["ad_products"] or 0) >= 10:
            out.append(f"广告竞品 {int(v['ad_products'])}")
        if v["bid"]:
            out.append(f"有建议竞价 ${v['bid']}")
        if k in ac:
            out.append("亚马逊下拉框出现")
        return out

    rows, ad, excluded, flagged = [], [], [], []
    for k, v in sorted(ss.items(), key=lambda kv: -(kv[1]["searches"] or 0)):
        s = v["searches"]
        has_attr = any(a in k for a in attrs)
        if (v["purchases"] is None or v["purchases"] == 1) and v["search_rank"] is None and not has_attr:
            sig = signals(k, v)
            why = "月购买量为1或空且无ABA排名（硬性未收录）"
            if sig:
                why += "；有保留信号：" + "，".join(sig)
                flagged.append({"keyword": k, "signals": sig})
            rows.append([k, "excluded_hard", why])
            excluded.append(k)
            continue
        if s is not None and s >= threshold:
            route, why = "main", f"月搜索 {int(s)} ≥ 门槛 {threshold:.0f}"
        else:
            reasons = signals(k, v)
            base = "搜索量为空" if s is None else f"月搜索 {int(s)} < 门槛 {threshold:.0f}"
            if reasons:
                route, why = "keep_long", base + "；保留：" + "，".join(reasons)
            else:
                route, why = "excluded", base + "；无相关度/广告竞争信号"
        rows.append([k, route, why])
        if route == "excluded":
            excluded.append(k)
            continue
        rec = {"keyword": k, "cn": v.pop("cn", ""), "category": "", "priority": "", "use": "", "note": "",
               "route": route, "ss": v, "xy": xy.get(k, {}), "aba": aba.get(k, {}), "ac": k in ac}
        if route == "keep_long":
            rec["priority"] = "B 长尾测试"
            rec["note"] = "搜索量数据缺失或偏低，按广告竞争判断"
        ad.append(rec)

    ac_only = sorted(k for k in ac if k not in ss)
    for k in ac_only:
        rows.append([k, "ac_only", "只在亚马逊下拉框出现（种子词：" + " / ".join(ac[k]) + "），卖家精灵无数据"])
        ad.append({"keyword": k, "cn": "", "category": "", "priority": "", "use": "",
                   "note": "只在亚马逊下拉框出现，卖家精灵无数据", "route": "ac_only",
                   "ss": {}, "xy": xy.get(k, {}), "aba": aba.get(k, {}), "ac": True})

    meta = {"ss_months": sorted(months), "aba_period": sorted(aba_period),
            "threshold_rule": f"有ABA排名、排名最靠后的{len(ranked)}个词（跳过最低档）的月搜索量中位数÷2",
            "threshold_note": threshold_note, "ss_floor": floor,
            "threshold": round(threshold, 1)}
    skeleton = {"meta": meta, "threshold": {"value": round(threshold, 1), "tail_samples": ranked},
                "ad": ad, "neg": [], "all_keywords": list(ss) + ac_only, "excluded": excluded,
                "watch_keywords": [f["keyword"] for f in flagged],
                # 全部拓词的月搜索量和 ABA 排名，词根表、属性分析、否词命中量都用它
                "volumes": {k: v["searches"] for k, v in ss.items()},
                "ranks": {k: v["search_rank"] for k, v in ss.items()}}
    (out / "skeleton.json").write_text(json.dumps(skeleton, ensure_ascii=False, indent=1))
    with open(out / "routing.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["关键词", "分流", "原因"])
        w.writerows(rows)
    need_xy = [r["keyword"] for r in ad if not r["xy"]]
    print(json.dumps({
        "keywords": len(ss), "threshold": meta["threshold"], "threshold_note": threshold_note,
        "ss_floor": floor, "threshold_samples": ranked,
        "routes": {r: sum(1 for x in rows if x[1] == r) for r in ("main", "keep_long", "excluded", "excluded_hard", "ac_only")},
        "autocomplete": {"keywords": len(ac), "also_in_ss": sum(1 for k in ac if k in ss),
                         "ac_only": len(ac_only), "ac_only_sample": ac_only[:20],
                         "seeds_with_failed_requests": ac_failed},
        "hard_excluded_with_signals": flagged,
        "ss_months": meta["ss_months"], "aba_period": meta["aba_period"],
        "missing_xydc": len(need_xy), "missing_xydc_sample": need_xy[:20],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
