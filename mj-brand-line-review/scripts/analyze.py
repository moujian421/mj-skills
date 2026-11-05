import json,sys,statistics as st,collections,math
sys.path.insert(0,'.')
from rank_lib import load_raw
from lines import *
idx=load_raw(["test/agy","round1/agy","round1/agy_retry","round1b/agy"])
P=json.load(open("products_xydc.json")); M=json.load(open("main_asins.json")); N=json.load(open("nodes.json"))
MONTHS=[f"2025-{m:02d}" for m in range(1,13)]+[f"2026-{m:02d}" for m in range(1,10)]
def daily(ra,nodes):
    out={}
    for t in idx[(ra,'get_asin_bsr_trends')]['trends']:
        vs={v['categoryId']:v['rank'] for v in t.get('values') or [] if v.get('rank')}
        for n in nodes:
            if n in vs: out[t['date']]=vs[n]; break
    return out
def mrank(d):
    m=collections.defaultdict(list)
    for k,v in d.items(): m[k[:7]].append(v)
    return {k:(int(st.median(v)) if len(v)>=15 else None) for k,v in m.items()}
def flag(r1,r2):
    if not r1 or not r2: return ''
    ratio=r2/r1
    if (ratio>=1.5 or ratio<=1/1.5) and abs(r2-r1)>=3: return '⬇️' if r2>r1 else '⬆️'
    return ''
def persist(d,month,r2,worse):
    # new level held >=7 days in month
    vals=[v for k,v in d.items() if k.startswith(month)]
    return sum(1 for v in vals if (v>=r2*0.8 if worse else v<=r2*1.25))>=7
res={}
for l,As in M.items():
    for a in As:
        ra,nodes=N[a]; d=daily(ra,nodes); mr=mrank(d); rv=mrev(P[a])
        rows=[]
        for i,m in enumerate(MONTHS):
            r=mr.get(m); prev=mr.get(MONTHS[i-1]) if i else None
            f=flag(prev,r) if m>='2026-01' else ''
            if f and not persist(d,m,r,f=='⬇️'): f=''
            pv=rv.get(MONTHS[i-1],0) if i else 0
            rows.append(dict(m=m,rank=r,rev=round(rv.get(m,0)),mom=(round(rv.get(m,0)/pv-1,2) if pv else None),flag=f))
        yoy_flag=flag(mr.get('2025-09'),mr.get('2026-09'))
        res[a]=dict(line=l,rank_asin=ra,nodes=nodes,rows=rows,ytd26=round(sum(rv.get(f"2026-{m:02d}",0) for m in range(1,10))),ytd25=round(sum(rv.get(f"2025-{m:02d}",0) for m in range(1,10))),r_sep25=mr.get('2025-09'),r_sep26=mr.get('2026-09'),yoy_flag=yoy_flag,title=P[a]['title'])
json.dump(res,open("rank_result.json","w"),ensure_ascii=False,indent=1)
for a,r in res.items():
    ser=' '.join(f"{x['m'][2:]}:{x['rank']}{x['flag']}" for x in r['rows'] if x['m']>='2026-01')
    print(f"{r['line']} {a} YTD {r['ytd26']/1e4:.0f}/{r['ytd25']/1e4:.0f}万 9月排名 {r['r_sep25']}→{r['r_sep26']}{r['yoy_flag']} | {ser}")
