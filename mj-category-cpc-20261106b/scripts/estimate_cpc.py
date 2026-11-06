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
BIG_WS, SMALL_WS = 10000, 5000  # 大词/小词周搜阈值
XY_TOP = 2.0  # 抢顶部 ≈ 2×西柚CPC（GF2、PM1 两个点）
LOW_P = 50  # 低客单阈值：P 低于它才用西柚 CPC 做下限
PRICE_BAND = (0.7, 1.43)  # 大词中位价 ÷ 小词中位价在这个范围内，才算同一价位，可以借大词 C
LOW_TIER = 0.7  # 词下中位价 < 0.7×同形态 P：词 C 被低价带抬高，V 可能虚高（只预警）
HIGH_PRICE = 1.5  # 我方售价 ≥ 1.5×词下中位价：我方 CVR 会低于 C（只预警）


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
    ap.add_argument("--c-ref", type=float, help="可选，手动指定大词参考转化率（小数）；不填就用 --info 里周搜≥1万的词按搜索量加权")
    ap.add_argument("--out")
    a = ap.parse_args()

    info = {}
    for f in a.info:
        for r in load(f)["list"]:
            info[r["searchTerm"].lower()] = r
    # 大词参考 C：周搜 ≥1 万的词按搜索量加权（PM1：长尾词西柚 C 3.4–4.7%，实际广告 CVR 9–20%，大词 C 10.7% 才对）
    wv = lambda r: ((r.get("abaReport") or {}).get("weeklySearchVolume") or 0)
    big = [r for r in info.values() if wv(r) >= BIG_WS and r.get("clickConversionRate")]
    # 每个词前 20 竞品的价格中位数，用来判断大词和小词是不是同一价位（核桃砧板 2026-11-06：
    # 大词 wood cutting board 中位价 $30 是竹砧板，walnut 词 $62，换大词 C 后 CPC 估成 $2.6，实际 $0.96）
    med_by_kw = {}
    for pair in a.asin:
        k_, p_ = pair.split("=", 1)
        ps_ = [x["asinInfo"].get("price") or 0 for x in load(p_)["list"]]
        ps_ = [p for p in ps_ if p]
        if ps_: med_by_kw[k_.strip().lower()] = S.median(ps_)

    def c_ref_for(kw):
        """小词可参考的大词 C：只用有前 20 价格、且中位价和小词相差不超过 ±30% 的大词。"""
        if a.c_ref: return a.c_ref, None
        m0 = med_by_kw.get(kw)
        ok = [r for r in big if m0 and r["searchTerm"].lower() in med_by_kw
              and PRICE_BAND[0] <= med_by_kw[r["searchTerm"].lower()] / m0 <= PRICE_BAND[1]]
        if ok:
            return sum(float(r["clickConversionRate"]) * wv(r) for r in ok) / sum(wv(r) for r in ok), None
        return None, ("大词价位和它不可比（或没拉大词的前 20），未改 C" if big else None)

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
        same_hi = None
        if same is not None:  # 只用同形态竞品算 P；同形态内仍剔除 >2×中位价的大件（PM1：Stakt $94–128）
            S_ = [x for x in A if x["asin"].upper() in same]
            ad_s = sum(T(x)["advertising"] for x in S_)
            same_share = ad_s / ad
            sp = [price(x) for x in S_ if price(x)]
            smed = S.median(sp) if sp else 0
            K_ = [x for x in S_ if price(x) <= 2 * smed]
            ad_k = sum(T(x)["advertising"] for x in K_)
            same_hi = 1 - ad_k / ad_s if ad_s else 0
            p_ad = (sum(price(x) * T(x)["advertising"] for x in S_) / ad_s) if ad_s else a.price  # 基准：同形态全部
            p_adj = (sum(price(x) * T(x)["advertising"] for x in K_) / ad_k) if ad_k else a.price  # 微调：再剔大件
        p_adj = p_adj if same is not None else p_ad

        r = info.get(kw)
        if not r or not r.get("clickConversionRate"):
            res.append(dict(keyword=kw, error="get_keyword_info 里没有这个词或没有转化率"))
            continue
        C_raw = C = float(r["clickConversionRate"])
        xy = float(r["costPerClick"]["value"]) if r.get("costPerClick") else None
        aba = r.get("abaReport") or {}
        top = aba.get("topAsins") or []
        cs = sum(float(t["clickShare"]) for t in top)
        vs = sum(float(t["conversionShare"]) for t in top)
        flags = []
        # ---- 基准（不动）：西柚原始 C × P，0.22V / 0.40V ----
        V = p_ad * C
        gap = p_ad / a.price
        # ---- 微调参考（PM1 2026-11-06，单独输出，不覆盖基准）----
        notes = []
        C_adj = C
        c_ref, why_not = c_ref_for(kw) if wv(r) < SMALL_WS else (None, None)
        if c_ref and C < 0.5 * c_ref:  # 小词 C 失真：改用同价位大词的 C
            C_adj = c_ref
            notes.append(f"小词C {C_raw:.1%}→同价位大词C {c_ref:.1%}")
        elif why_not and C < 0.5 * max(float(x["clickConversionRate"]) for x in big):
            flags.append(f"小词C偏低，但{why_not}：低C多半是价位高的真实转化")
        if med and med < LOW_TIER * p_ad:
            flags.append(f"词下中位价${med:.0f}不到同形态P的{LOW_TIER:.0%}，词C被低价带抬高，V和基准CPC可能虚高")
        if med and a.price >= HIGH_PRICE * med:
            flags.append(f"我方售价是词下中位价的{a.price / med:.1f}倍，我方CVR会明显低于C")
        if same_hi: notes.append(f"同形态大件占{same_hi:.0%}已剔，P ${p_ad:.0f}→${p_adj:.0f}")
        V_adj = p_adj * C_adj
        mixed = (same_share is not None and same_share < 0.35) or gap >= 2 or (same is None and hi_ad >= 0.3) or p_adj >= LOW_P
        mid_a, head_a = K_MID * V_adj, K_HEAD * V_adj
        if xy and not mixed and (xy > mid_a or XY_TOP * xy > head_a):  # 低客单：西柚 CPC 当下限
            mid_a, head_a = max(mid_a, xy), max(head_a, XY_TOP * xy)
            notes.append(f"低客单，西柚CPC当下限（靠后≥${xy}、抢顶部≥{XY_TOP:g}×西柚）")
        row = dict(
            keyword=kw, weekly_search=aba.get("weeklySearchVolume"), difficulty=r.get("competitiveDifficulty"),
            P_ad=round(p_ad, 2), P_ad_before_clean=round(p_ad_raw, 2), price_median=round(med, 2), price_min=min(prices) if prices else None,
            price_max=max(prices) if prices else None, ad_share_from_2x_median_price=round(hi_ad, 2),
            asins_with_ads=f"{n_ad}/{len(A)}", ad_traffic_share=round(ad / tot, 2),
            xy_cvr=round(C, 4), top3_cvr=round(C * vs / cs, 4) if cs else None,
            xy_cpc=xy, V=round(V, 2), xy_cpc_over_V=round(xy / V, 3) if xy and V else None,
            cpc_mid=round(K_MID * V, 2), cpc_head=round(K_HEAD * V, 2),
            cpc_mid_dynamic=round(K_MID * V * DYN, 2),
            adj=dict(notes=notes, C=round(C_adj, 4), P=round(p_adj, 2), V=round(V_adj, 2),
                     cpc_mid=round(mid_a, 2), cpc_head=round(head_a, 2)) if notes else None,
            same_form_ad_share=round(same_share, 2) if same_share is not None else None,
            same_form_hi_price_ad_share=round(same_hi, 2) if same_hi is not None else None,
        )
        if V >= 12: flags.append("V≥$12 高CPC类目")
        if xy and V and p_ad >= LOW_P and xy > 0.3 * V:  # 核桃砧板：西柚 0.41V，实际 0.21V
            flags.append("西柚CPC高于公式（P≥$50）：点估计用基准，西柚只当放开抢位的情境，不凭竞品多/旺季往西柚靠")
        if row["xy_cpc_over_V"] is not None and row["xy_cpc_over_V"] < 0.2: flags.append("西柚CPC可能低估(<0.2V)")
        if same_share is not None and same_share < 0.35:
            flags.append(f"同形态竞品只占广告流量{same_share:.0%}，混合需求词：已用同形态算P，西柚CPC偏高" + ("；同形态无人投广告，靠后位置会很便宜" if same_share == 0 else ""))
        if same is None and hi_ad >= 0.3: flags.append(f"高价大件占广告流量{hi_ad:.0%}，已剔除>2×中位价ASIN重算P（原${p_ad_raw:.0f}）；西柚CPC可能偏高")
        if gap >= 2: flags.append(f"竞品广告加权价是我方{gap:.1f}倍，词可能不对口")
        elif gap >= 1.4: flags.append(f"竞品广告加权价是我方{gap:.1f}倍，我方承受CPC能力弱")
        row["flags"] = flags
        def acos_of(cc, m, h):
            cvrs = {"指定": a.cvr} if a.cvr else {k: cc * v for k, v in CVR_RATIO.items()}
            return {n: dict(cvr=round(cv, 4), acos_mid=round(m / (a.price * cv), 3), acos_head=round(h / (a.price * cv), 3))
                    for n, cv in cvrs.items()}
        row["acos"] = acos_of(C, row["cpc_mid"], row["cpc_head"])
        if row["adj"]: row["adj"]["acos"] = acos_of(C_adj, mid_a, head_a)
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
        j = r.get("adj")
        if j:
            h = j["acos"].get("指定") or j["acos"]["头部产品"]
            print(f"  ↳ 微调参考：{'；'.join(j['notes'])} → V ${j['V']} | 靠后${j['cpc_mid']} 抢顶部${j['cpc_head']} | "
                  f"CVR {h['cvr']:.1%} 时 ACoS 靠后{h['acos_mid']:.0%} / 抢顶部{h['acos_head']:.0%}")


if __name__ == "__main__":
    main()
