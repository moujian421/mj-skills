import json,sys,collections,glob
sys.path.insert(0,'.')
from lines import *
P=json.load(open("products_xydc.json")); R=json.load(open("rank_result.json")); CY=json.load(open("cat_yoy.json"))
W=lambda v:f"{v/1e4:.1f}"
pct=lambda a,b:(f"{a/b-1:+.0%}" if b else "新品")
def ytd(i,y,upto=9): return sum(v for k,v in mrev(i).items() if k.startswith(str(y)) and int(k[5:])<=upto)
def ytdu(i,y): return sum(v for k,v in munits(i).items() if k.startswith(str(y)) and int(k[5:])<=9)
out=[]
# brand
T26=sum(ytd(i,2026) for i in P.values()); T25=sum(ytd(i,2025) for i in P.values())
U26=sum(ytdu(i,2026) for i in P.values()); U25=sum(ytdu(i,2025) for i in P.values())
S26=sum(mrev(i).get('2026-09',0) for i in P.values()); S25=sum(mrev(i).get('2025-09',0) for i in P.values())
SU26=sum(munits(i).get('2026-09',0) for i in P.values()); SU25=sum(munits(i).get('2025-09',0) for i in P.values())
act=lambda y,mm:sum(1 for i in P.values() if any(mrev(i).get(f"{y}-{m:02d}",0)>0 for m in mm))
out.append("| 指标 | 今年 1–9 月 | 去年 1–9 月 | 同比 | 今年 9 月 | 去年 9 月 | 同比 |\n|---|---|---|---|---|---|---|")
out.append(f"| 估算销售额（万美元） | {W(T26)} | {W(T25)} | {pct(T26,T25)} | {W(S26)} | {W(S25)} | {pct(S26,S25)} |")
out.append(f"| 估算销量（件） | {U26:,} | {U25:,} | {pct(U26,U25)} | {SU26:,} | {SU25:,} | {pct(SU26,SU25)} |")
out.append(f"| ASP（美元） | {T26/U26:.1f} | {T25/U25:.1f} | {pct(T26/U26,T25/U25)} | {S26/SU26:.1f} | {S25/SU25:.1f} | {pct(S26/SU26,S25/SU25)} |")
out.append(f"| 有销量的变体组 | {act(2026,range(1,10))} | {act(2025,range(1,10))} | {pct(act(2026,range(1,10)),act(2025,range(1,10)))} | {act(2026,[9])} | {act(2025,[9])} | {pct(act(2026,[9]),act(2025,[9]))} |")
out.append("")
# lines
L=collections.defaultdict(list)
for i in P.values(): L[line_of(i)].append(i)
cats=collections.defaultdict(set)
for i in P.values():
    c=i.get('internalCategoryTree') or {}; path=[p['categoryName']['original'] for p in c.get('path',[])]
    if len(path)>=2: cats[line_of(i)].add(path[-1])
JUD={}
out.append("| 品线 | 包含类目（西柚） | 今年估算销售额 | 占品牌 | 去年同期 | 同比 | 小类前 100 销量同比 | 品线销量同比 |\n|---|---|---|---|---|---|---|---|")
order=sorted(L,key=lambda l:(l=="其他",-sum(ytd(i,2026) for i in L[l])))
for l in order:
    a=sum(ytd(i,2026) for i in L[l]); b=sum(ytd(i,2025) for i in L[l]); ua=sum(ytdu(i,2026) for i in L[l]); ub=sum(ytdu(i,2025) for i in L[l])
    cs="、".join(sorted(cats[l])[:4])+("等" if len(cats[l])>4 else "") if l!="其他" else "堆肥桶、喂鸟器、披萨炉、园艺等"
    cy=f"{CY[l]:+.0%}" if l in CY else "—"
    out.append(f"| {l} | {cs} | {W(a)} | {a/T26:.0%} | {W(b)} | {pct(a,b)} | {cy} | {pct(ua,ub)} |")
out.append(f"| **合计** | | **{W(T26)}** | **100%** | **{W(T25)}** | **{pct(T26,T25)}** | | |")
out.append("")
# main products per line
for l in [x for x in order if x!="其他"]:
    out.append(f"### {l}")
    out.append("| ASIN | 产品 | 上架 | 今年 ASP | 评分/评分数 | 履约 | 今年估算销售额 | 同比 | 去年 9 月小类排名 | 今年 9 月小类排名 |\n|---|---|---|---|---|---|---|---|---|---|")
    for a,r in R.items():
        if r['line']!=l: continue
        i=P[a]; t=(i['title'] or '').replace('|','/')
        name=t.replace('EAST OAK','').replace('East Oak','').strip(' ,')[:34]
        asp=ytd(i,2026)/max(ytdu(i,2026),1)
        out.append(f"| {a} | {name} | {(i.get('streetDate') or '')[:7]} | {asp:.0f} | {i.get('stars')}/{i.get('ratings')} | {i.get('fulfillmentType')} | {W(ytd(i,2026))} | {pct(ytd(i,2026),ytd(i,2025))} | {r['r_sep25'] or '—'} | {r['r_sep26'] or '无排名'}{r['yoy_flag']} |")
    out.append("")
    hdr="| ASIN | "+" | ".join(f"{m}月" for m in range(1,10))+" |\n|---|"+"---|"*9
    out.append("逐月小类排名（月中位数，⬆️⬇️ 为异动；下一行为销售额环比）\n\n"+hdr)
    for a,r in R.items():
        if r['line']!=l: continue
        rows=[x for x in r['rows'] if x['m']>='2026-01']
        out.append(f"| {a} | "+" | ".join(f"{x['rank'] or '—'}{x['flag']}" for x in rows)+" |")
        out.append("| 环比 | "+" | ".join((f"{x['mom']:+.0%}" if x['mom'] is not None else "—") for x in rows)+" |")
    out.append("")
open("tables.md","w").write("\n".join(out))
