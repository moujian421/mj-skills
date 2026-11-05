import json,glob,os,statistics as st,collections
def load_raw(dirs):
    idx={}
    for d in dirs:
        for f in sorted(glob.glob(d+"/raw/*.json")):
            tool=os.path.basename(f).split('__')[1][:-5]
            dd=json.load(open(f)).get('data') if isinstance(json.load(open(f)),dict) else None
            if isinstance(dd,dict) and 'asin' in dd: idx[(dd['asin'],tool)]=dd
    return idx
def leaves(b):
    names={c['categoryId']:c['name'] for c in b['categoryTree']}
    days=collections.Counter(); ranks=collections.defaultdict(list)
    for t in b['trends']:
        for v in t.get('values') or []:
            days[v['categoryId']]+=1; ranks[v['categoryId']].append(v['rank'])
    return {c:(names.get(c,c),days[c],int(st.median(ranks[c]))) for c in days}
def monthly(b,cid):
    m=collections.defaultdict(list)
    for t in b['trends']:
        for v in t.get('values') or []:
            if v['categoryId']==cid and v.get('rank'): m[t['date'][:7]].append((t['date'],v['rank']))
    return m
