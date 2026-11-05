#!/usr/bin/env python3
"""进类目前预估 CPC 和 ACoS（只用西柚数据）。

用法:
  python3 -I estimate_cpc.py --info KW_INFO.json [--info 更多.json] \
      --asin "关键词=ASIN_ANALYSIS.json" [--asin ...] \
      --price 119.99 [--cvr 0.045] [--same ASIN1,ASIN2,...] [--out result.json]

--info  : get_keyword_info 的原始返回（可多个文件）
--asin  : get_keyword_asin_analysis 的原始返回，每个词一个文件（返回里不带关键词，所以用 词=路径 指定）
--price : 我方计划售价（广告客单价）
--cvr   : 可选，我方预计广告 CVR（小数）；不填就按头部/中部/新品三档折算
--same  : 可选，人工按标题标出的同形态竞品 ASIN（逗号分隔）。给了就只用它们算 P，并检查同形态广告流量占比
系数来源和回测见 SKILL.md。
"""
import argparse, json, statistics as S

# 按目标搜索顶部展示份额(TOS)分档：靠后 TOS<3% ≈0.22V；抢顶部 TOS 10–30% ≈0.40V；3–10% 取中间
K_MID, K_HEAD, DYN = 0.22, 0.40, 1.5
CVR_RATIO = {"头部产品": 1.0, "中部产品": 0.6, "新品期": 0.3}


def load(p):
    d = json.load(open(p))
    return d.get("data", d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--info", action="append", required=True)
    ap.add_argument("--asin", action="append", required=True)
    ap.add_argument("--price", type=float, required=True)
    ap.add_argument("--cvr", type=float)
    ap.add_argument("--same", help="同形态竞品 ASIN，逗号分隔")
    ap.add_argument("--out")
    a = ap.parse_args()

    info = {}
    for f in a.info:
        for r in load(f)["list"]:
            info[r["searchTerm"].lower()] = r

    same = set(x.strip().upper() for x in a.same.split(",")) if a.same else None
    res = []
    for pair in a.asin:
        kw, path = pair.split("=", 1)
        kw = kw.strip().lower()
        A = load(path)["list"]
        T = lambda x: x["trafficSummary"]["traffic"]
        price = lambda x: x["asinInfo"].get("price") or 0
        tot = sum(T(x)["total"] for x in A) or 1
        ad = sum(T(x)["advertising"] for x in A) or 1
        p_ad = sum(price(x) * T(x)["advertising"] for x in A) / ad
        prices = [price(x) for x in A if price(x)]
        med = S.median(prices) if prices else 0
        hi_ad = sum(T(x)["advertising"] for x in A if med and price(x) > 2 * med) / ad
        n_ad = sum(1 for x in A if T(x)["advertising"] > 0)
        p_ad_raw = p_ad
        if hi_ad >= 0.3:  # 高价大件污染：剔除 >2×中位价的 ASIN 后重算 P
            keep = [x for x in A if price(x) <= 2 * med]
            ad_k = sum(T(x)["advertising"] for x in keep) or 1
            p_ad = sum(price(x) * T(x)["advertising"] for x in keep) / ad_k
        same_share = None
        if same is not None:  # 只用同形态竞品算 P
            S_ = [x for x in A if x["asin"].upper() in same]
            ad_s = sum(T(x)["advertising"] for x in S_)
            same_share = ad_s / ad
            p_ad = (sum(price(x) * T(x)["advertising"] for x in S_) / ad_s) if ad_s else a.price

        r = info.get(kw)
        if not r or not r.get("clickConversionRate"):
            res.append(dict(keyword=kw, error="get_keyword_info 里没有这个词或没有转化率"))
            continue
        C = float(r["clickConversionRate"])
        xy = float(r["costPerClick"]["value"]) if r.get("costPerClick") else None
        aba = r.get("abaReport") or {}
        top = aba.get("topAsins") or []
        cs = sum(float(t["clickShare"]) for t in top)
        vs = sum(float(t["conversionShare"]) for t in top)
        V = p_ad * C
        row = dict(
            keyword=kw, weekly_search=aba.get("weeklySearchVolume"), difficulty=r.get("competitiveDifficulty"),
            P_ad=round(p_ad, 2), P_ad_before_clean=round(p_ad_raw, 2), price_median=round(med, 2), price_min=min(prices) if prices else None,
            price_max=max(prices) if prices else None, ad_share_from_2x_median_price=round(hi_ad, 2),
            asins_with_ads=f"{n_ad}/{len(A)}", ad_traffic_share=round(ad / tot, 2),
            xy_cvr=round(C, 4), top3_cvr=round(C * vs / cs, 4) if cs else None,
            xy_cpc=xy, V=round(V, 2), xy_cpc_over_V=round(xy / V, 3) if xy and V else None,
            cpc_mid=round(K_MID * V, 2), cpc_head=round(K_HEAD * V, 2),
            cpc_mid_dynamic=round(K_MID * V * DYN, 2),
            same_form_ad_share=round(same_share, 2) if same_share is not None else None,
        )
        flags = []
        if V >= 12: flags.append("V≥$12 高CPC类目")
        if row["xy_cpc_over_V"] is not None and row["xy_cpc_over_V"] < 0.2: flags.append("西柚CPC可能低估(<0.2V)")
        if same_share is not None and same_share < 0.35:
            flags.append(f"同形态竞品只占广告流量{same_share:.0%}，混合需求词：已用同形态算P，西柚CPC偏高" + ("；同形态无人投广告，靠后位置会很便宜" if same_share == 0 else ""))
        if same is None and hi_ad >= 0.3: flags.append(f"高价大件占广告流量{hi_ad:.0%}，已剔除>2×中位价ASIN重算P（原${p_ad_raw:.0f}）；西柚CPC可能偏高")
        gap = p_ad / a.price
        if gap >= 2: flags.append(f"竞品广告加权价是我方{gap:.1f}倍，词可能不对口")
        elif gap >= 1.4: flags.append(f"竞品广告加权价是我方{gap:.1f}倍，我方承受CPC能力弱")
        row["flags"] = flags
        cvrs = {"指定": a.cvr} if a.cvr else {k: C * v for k, v in CVR_RATIO.items()}
        acos = {}
        for name, cv in cvrs.items():
            vpc = a.price * cv
            acos[name] = dict(cvr=round(cv, 4), acos_mid=round(row["cpc_mid"] / vpc, 3),
                              acos_head=round(row["cpc_head"] / vpc, 3))
        row["acos"] = acos
        res.append(row)

    out = json.dumps(res, ensure_ascii=False, indent=1)
    if a.out:
        open(a.out, "w").write(out)
    for r in res:
        if "error" in r:
            print(r["keyword"], "|", r["error"]); continue
        print(f"{r['keyword']} | 周搜{r['weekly_search']} | P_ad ${r['P_ad']} 中位${r['price_median']} | C {r['xy_cvr']:.1%} 头部前3 {r['top3_cvr'] or 0:.1%} | "
              f"V ${r['V']} | 西柚CPC ${r['xy_cpc']} ({r['xy_cpc_over_V']}V) | 靠后(TOS<3%)${r['cpc_mid']} 抢顶部(TOS10-30%)${r['cpc_head']} | {'；'.join(r['flags']) or '-'}")
        for k, v in r["acos"].items():
            print(f"    {k}: CVR {v['cvr']:.1%} → ACoS 靠后{v['acos_mid']:.0%} / 抢顶部{v['acos_head']:.0%}")


if __name__ == "__main__":
    main()
