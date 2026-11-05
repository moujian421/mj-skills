#!/usr/bin/env python3
"""算好评 / 中评 / 差评里各标签的占比，生成飞书要写的几张表，打印简报。

用法:
    python3 stats.py WORK TAXONOMY.md [--asof 2026-10-30] [--min-variant 30]

口径（写进飞书「说明」里，不要改）:
- 分组：好评 = 4–5 星，中评 = 3 星，差评 = 1–2 星。
- 占比 = 该组里提到这个标签的评论数 ÷ 该组评论总数。一条评论可以有多个标签，所以同组各标签占比相加会超过 100%。
- 提及构成 = 该标签的提及次数 ÷ 该组同方向（负面或正面）的全部提及次数（饼图用，相加 = 100%）。
- 排名也在同一组、同一方向内部排。
- 分母只算打标成功的评论；没打上任何标签的评论（只写 "good" 之类）也算在分母里。

输出 WORK/feishu/ 下：detail.json, taxonomy.json, share.json, l1.json, split.json, brief.md
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from tag_reviews import OTHER_NEG, OTHER_POS, load_taxonomy  # noqa: E402

GROUPS = [("好评", (4, 5)), ("中评", (3,)), ("差评", (1, 2))]


def group_of(star):
    for g, s in GROUPS:
        if star in s:
            return g
    return "未知"


def share_rows(reviews, meta, group_name):
    """排名和提及构成在同一方向（正 / 负）内部计算。"""
    n = len(reviews)
    cnt = Counter(p for r in reviews for p in r["_tags"])
    out = []
    for pol in ("负", "正"):
        part = [(t, k) for t, k in cnt.most_common() if meta[t]["pol"] == pol]
        total_mentions = sum(k for _, k in part)
        for rank, (tag, k) in enumerate(part, 1):
            out.append({"分组": group_name, "正负": pol, "一级分类": meta[tag]["l1"], "标签": tag,
                        "评论数": k, "组内评论数": n, "占比(%)": round(k * 100 / n, 1) if n else 0,
                        "提及构成(%)": round(k * 100 / total_mentions, 1) if total_mentions else 0,
                        "排名": rank})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("taxonomy")
    ap.add_argument("--asof", default=date.today().isoformat())
    ap.add_argument("--min-variant", type=int, default=30, help="变体拆分只列评论数不少于这个值的变体")
    a = ap.parse_args()
    work = Path(a.work)
    out = work / "feishu"
    out.mkdir(exist_ok=True)

    tax = load_taxonomy(a.taxonomy)
    meta = {t["tag"]: t for t in tax}
    meta[OTHER_NEG] = {"tag": OTHER_NEG, "pol": "负", "l1": "其他", "def": "标签库外的问题", "not": "—"}
    meta[OTHER_POS] = {"tag": OTHER_POS, "pol": "正", "l1": "其他", "def": "标签库外的优点", "not": "—"}

    revs = {json.loads(l)["id"]: json.loads(l) for l in open(work / "reviews.jsonl")}
    tags = {json.loads(l)["id"]: json.loads(l) for l in open(work / "tags.jsonl")}
    rows = []
    for i, r in revs.items():
        t = tags.get(i)
        if not t:
            continue
        r = dict(r, _tags=[p["tag"] for p in t["points"]], _t=t, _g=group_of(r["star"]))
        rows.append(r)
    untagged = len(revs) - len(rows)

    # 明细
    detail = []
    for r in rows:
        t = r["_t"]
        neg = [p for p in t["points"] if meta[p["tag"]]["pol"] == "负"]
        pos = [p for p in t["points"] if meta[p["tag"]]["pol"] == "正"]
        detail.append({
            "评论ID": r["id"], "ASIN": r["asin"], "日期": r["date"], "星级": r["star"], "分组": r["_g"],
            "变体": r["variant"], "VP": r["verified"], "Vine": r["vine"],
            "图片/视频": "视频" if r["video"] else ("图片" if r["image"] else ""),
            "英文标题": r["title"], "英文正文": r["content"], "中文翻译": t["zh"], "摘要": t["summary"],
            "负面标签": [p["tag"] for p in neg], "正面标签": [p["tag"] for p in pos],
            "一级分类": sorted({meta[p["tag"]]["l1"] for p in t["points"]}),
            "依据": "；".join(f"{p['tag']}：{p['quote']}" for p in t["points"]),
            "建议新标签": t.get("new_tag", ""),
        })

    # 占比汇总（分组 + 全部）
    by_g = defaultdict(list)
    for r in rows:
        by_g[r["_g"]].append(r)
    share = []
    for g, _ in GROUPS:
        share += share_rows(by_g[g], meta, g)
    share += share_rows(rows, meta, "全部")

    # 一级分类汇总
    l1 = []
    for g, _ in GROUPS:
        grp = by_g[g]
        # 一条评论在同一个（正负, 一级分类）下只算一次
        c = Counter(k for r in grp for k in {(meta[t]["pol"], meta[t]["l1"]) for t in r["_tags"]})
        for (pol, name), k in c.most_common():
            l1.append({"分组": g, "正负": pol, "一级分类": name, "评论数": k, "组内评论数": len(grp),
                       "占比(%)": round(k * 100 / len(grp), 1) if grp else 0})

    # 拆分：ASIN、变体、近 12 个月、VP/Vine
    cut = (date.fromisoformat(a.asof) - timedelta(days=365)).isoformat()
    dims = defaultdict(list)
    asins = {r["asin"] for r in rows}
    for r in rows:
        if len(asins) > 1:
            dims[("ASIN", r["asin"])].append(r)
        dims[("时间", "近12个月" if r["date"] >= cut else "12个月以前")].append(r)
        dims[("评论类型", "Vine" if r["vine"] else ("VP" if r["verified"] else "非VP非Vine"))].append(r)
        if r["variant"]:
            dims[("变体", r["variant"])].append(r)
    split = []
    for (dim, val), rs in sorted(dims.items()):
        if dim == "变体" and len(rs) < a.min_variant:
            continue
        sub = defaultdict(list)
        for r in rs:
            sub[r["_g"]].append(r)
        for g, _ in GROUPS:
            for x in share_rows(sub[g], meta, g):
                split.append(dict(x, 维度=dim, 维度值=val))

    tax_rows = [{"一级分类": t["l1"], "标签": t["tag"], "正负": t["pol"], "定义": t["def"], "不归入": t["not"]}
                for t in tax]
    for name, data in [("detail", detail), ("taxonomy", tax_rows), ("share", share), ("l1", l1), ("split", split)]:
        (out / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1))

    # 简报（Claude 读这个写结论，不读明细）
    def top(g, pol, k=10):
        return [x for x in share if x["分组"] == g and x["正负"] == pol][:k]

    lines = [f"# 评论打标简报（截至 {a.asof}）", "",
             f"打标评论 {len(rows)} 条（未打标 {untagged}）：" +
             "，".join(f"{g} {len(by_g[g])}" for g, _ in GROUPS), ""]
    for g, pol, title in [("差评", "负", "差评里的问题"), ("好评", "正", "好评里的卖点"),
                          ("好评", "负", "好评里的槽点"), ("差评", "正", "差评里仍被认可的点"),
                          ("中评", "负", "中评里的问题")]:
        lines.append(f"## {title}（{g}，{len(by_g[g])} 条）")
        lines += [f"- {x['标签']}（{x['一级分类']}）：{x['评论数']} 条，{x['占比(%)']}%" for x in top(g, pol)]
        lines.append("")
    oth = sum(1 for r in rows for t in r["_tags"] if t in (OTHER_NEG, OTHER_POS))
    allp = sum(len(r["_tags"]) for r in rows)
    lines.append(f"其他标签占全部提及 {round(oth * 100 / allp, 1) if allp else 0}%（超过 8% 要补标签库后重跑）")
    sug = Counter(d["建议新标签"] for d in detail if d["建议新标签"])
    if sug:
        lines.append("建议新标签：" + "，".join(f"{k}×{v}" for k, v in sug.most_common(15)))
    (out / "brief.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
