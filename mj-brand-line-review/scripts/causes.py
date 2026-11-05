import json,sys,statistics as st,collections,math,datetime as dt
sys.path.insert(0,'.')
from rank_lib import load_raw
idx=load_raw(["test/agy","round1/agy","round1/agy_retry","round1b/agy"])
R=json.load(open("rank_result.json")); N=json.load(open("nodes.json"))
def daily(ra,nodes):
    out={}
    for t in idx[(ra,'get_asin_bsr_trends')]['trends']:
        vs={v['categoryId']:v['rank'] for v in t.get('values') or [] if v.get('rank')}
        for n in nodes:
            if n in vs: out[t['date']]=vs[n]; break
    return out
def num(x):
    try: return float(x)
    except: return None
ev=[]
for a,r in R.items():
    ra,nodes=N[a]; d=daily(ra,nodes)
    info={t['date']:t for t in idx[(ra,'get_asin_info_trends')]['trends']}
    rows=r['rows']
    for i,x in enumerate(rows):
        if not x['flag']: continue
        r1,r2=rows[i-1]['rank'],x['rank']; mid=math.sqrt(r1*r2)
        days=sorted(k for k in d if k>=rows[i-1]['m'] and k<x['m']+'-32')
        # turning point: first day 3-day median crosses mid
        tp=None
        for j in range(2,len(days)):
            w=st.median(d[k] for k in days[j-2:j+1])
            if (x['flag']=='⬇️' and w>mid) or (x['flag']=='⬆️' and w<mid): tp=days[j-2]; break
        tp=tp or x['m']+'-01'
        T=dt.date.fromisoformat(tp)
        def win(a_,b_): return [info.get(str(T+dt.timedelta(days=k))) for k in range(a_,b_)]
        bef,aft=[w for w in win(-21,-1) if w],[w for w in win(0,21) if w]
        def summ(W):
            p=[num(w['priceDistribution'].get('display')) for w in W]; pv=[v for v in p if v]
            return dict(price=round(st.median(pv),2) if pv else None,noprice=sum(1 for v in p if not v),
                        deal=sum(1 for w in W if w['priceDistribution'].get('deal')),coupon=sum(1 for w in W if w['priceDistribution'].get('coupon')),
                        ratings=(W[0].get('ratings'),W[-1].get('ratings')) if W else None,stars=(W[0].get('stars'),W[-1].get('stars')) if W else None)
        ev.append(dict(asin=a,line=r['line'],month=x['m'],flag=x['flag'],r=f"{r1}→{r2}",mom=x['mom'],tp=tp,before=summ(bef),after=summ(aft)))
json.dump(ev,open("events.json","w"),ensure_ascii=False,indent=1)
for e in ev: print(e['line'],e['asin'],e['month'],e['flag'],e['r'],'mom',e['mom'],'tp',e['tp'],'| B',e['before'],'| A',e['after'])
