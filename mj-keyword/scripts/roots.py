#!/usr/bin/env python3
"""词根表：把全部拓词切成单词 / 双词词根，统计每个词根命中多少词、月搜索量合计，供两件事用：
  1. 提炼属性维度（材质、尺寸、形状、功能…）：看量大的修饰词根，归纳成 attributes 字典
  2. 找词组否定词根：看"命中词全都不相关"的短词根；--classified 给出后会统计命中了多少广告词库的词

用法:
    python3 roots.py OUT/skeleton.json OUT/roots.csv --seed "cutting board" [--classified OUT/classified.json] [--top 120]

输出 roots.csv（全部词根），stdout 打印按月搜索量合计排序的前 --top 个（一行一个，便于阅读）。
单复数简单归并（boards→board）；数字尺寸另外汇总成 <数字尺寸 AxB>、<英寸数字> 两个伪词根。
"""
import argparse, csv, json, re
from collections import defaultdict

STOP = {"a", "an", "the", "and", "or", "of", "to", "in", "on", "de", "para", "by", "&", "-"}
LEAD_OK = {"for", "with"}   # "for meat" "with handle" 这类双词片段保留，信息量大


def norm(t):
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss") and not t.endswith("us"):
        return t[:-1]
    return t


def toks(k):
    return [norm(t) for t in re.findall(r"[a-z0-9]+(?:x[0-9]+)?|&", k.lower())]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--seed", default="")
    ap.add_argument("--classified")
    ap.add_argument("--top", type=int, default=120)
    a = ap.parse_args()
    d = json.load(open(a.src))
    vol = d.get("volumes", {})
    kws = sorted({k.lower() for k in d.get("all_keywords", [])})
    seed = set(toks(a.seed))
    seed_phrase = " ".join(toks(a.seed))
    ad = set()
    if a.classified:
        c = json.load(open(a.classified))
        ad = {r["keyword"].lower() for r in c.get("ad", [])}

    hits = defaultdict(set)
    surface = defaultdict(lambda: defaultdict(int))
    for k in kws:
        raw = re.findall(r"[a-z0-9]+(?:x[0-9]+)?|&", k)
        t = [norm(x) for x in raw]
        for i, w in enumerate(t):
            if w in STOP or w in seed or w in LEAD_OK:
                continue
            hits[w].add(k)
            surface[w][raw[i]] += 1
        for i in range(len(t) - 1):
            g = f"{t[i]} {t[i + 1]}"
            if g == seed_phrase or t[i + 1] in STOP or t[i + 1] in LEAD_OK or (t[i] in STOP and t[i] not in LEAD_OK):
                continue
            if t[i] in seed and t[i + 1] in seed:
                continue
            hits[g].add(k)
            surface[g][f"{raw[i]} {raw[i + 1]}"] += 1
        for i in range(len(t) - 2):  # with/for 开头的三词短语，如 with juice groove
            if t[i] in LEAD_OK and t[i + 2] not in STOP:
                hits[" ".join(t[i:i + 3])].add(k)
        if re.search(r"\bset of \d+|\b\d+\s*(pack|pcs|piece|pc)\b|\b(set|pack)\b", k):
            hits["<套装数量 set/pack>"].add(k)
        if re.search(r"\b\d+(\.\d+)?\s*(x|by)\s*\d+", k):
            hits["<数字尺寸 AxB>"].add(k)
        if re.search(r"\b\d+(\.\d+)?\s*(inch|inches|in|\")(\b|$)", k):
            hits["<英寸数字>"].add(k)

    rows = []
    for r, ks in hits.items():
        if len(ks) < 2:
            continue
        v = sum(vol.get(k) or 0 for k in ks)
        top = sorted(ks, key=lambda k: -(vol.get(k) or 0))[:5]
        shown = max(surface[r], key=surface[r].get) if surface.get(r) else r
        rows.append({"root": shown, "n_words": len(r.split()), "hits": len(ks), "volume": int(v),
                     "in_ad": len(ks & ad) if ad else "",
                     "examples": "; ".join(f"{k}({int(vol[k]) if vol.get(k) else 'n.a.'})" for k in top)})
    rows.sort(key=lambda x: -x["volume"])
    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["root", "n_words", "hits", "volume", "in_ad", "examples"])
        w.writeheader()
        w.writerows(rows)
    print(f"拓词 {len(kws)} 个，词根 {len(rows)} 个（命中≥2 词），已写 {a.out}")
    print("词根 | 命中词数 | 月搜索量合计" + (" | 命中广告词库" if ad else "") + " | 代表词")
    for r in rows[:a.top]:
        print(f"{r['root']} | {r['hits']} | {r['volume']:,}" + (f" | {r['in_ad']}" if ad else "") + f" | {r['examples'][:110]}")


if __name__ == "__main__":
    main()
