#!/usr/bin/env python3
"""从西柚原始返回里，逐个广告活动算出判断匹配方式要用的指标，并给出初判。

用法: python3 -I frame.py PULL_DIR [PULL_DIR ...] [--syn syn.json] [--out frame.csv]
PULL_DIR 是 oc_pull.sh 的输出目录（里面有 raw/index.json）。会读取：
  get_parent_asin_ad_campaigns          活动清单
  get_parent_asin_ad_campaign_detail    展示位分布
  get_parent_asin_ad_keywords（带 campaign_id，可多页）  活动内的词
  get_asin_keywords（可选）  目标 ASIN 近 7 天全部词，用来判断相关性（有自然流量 = 相关）

--syn 同义词表（Claude 按品类写，可选）：
  {"groups": {"ab": ["abs", "abdominal", "abdominales", "abb"], "machine": ["maquina"]},
   "core": ["ab", "machine"]}
  groups: 词根 → 同义写法（词形变化 ing、ed、复数已自动归并，不用写）
  core:   本品的核心词根；含任一核心词根的词也算“相关”
只打印每个活动一行的摘要；逐词明细写到 --out 的 CSV。初判只是线索，最终由 Claude 判断。
"""
import csv, json, os, re, sys
from collections import defaultdict
from itertools import combinations

SEED_COVER = 0.85    # 广泛、词组：种子词根覆盖的流量占比下限
PHRASE_SEQ = 0.95    # 词组：连续包含种子词根的流量占比下限（插词、换序的超过 5% 就算广泛）
RELATED_CLOSE = 0.70  # 自动紧密：相关词流量占比下限
MANY = 10            # 词数达到这个数才按“种子词根、紧密、宽泛”三分

def load(dirs):
    out = defaultdict(list)
    for d in dirs:
        idx = json.load(open(os.path.join(d, 'raw', 'index.json')))
        items = idx if isinstance(idx, list) else idx.get('files', idx.get('items', []))
        for it in items:
            f = os.path.join(d, 'raw', it['file'])
            if not f.endswith('.json') or not os.path.exists(f):
                continue
            try:
                j = json.load(open(f))
            except Exception:
                continue
            out[it['tool']].append((it.get('args') or it.get('params') or {}, j.get('data', j)))
    return out

VOWEL = set('aeiouy')

def stem(w):
    """轻量词形归并：复数、-ing、-ed 归到同一词根（不追求语言学准确，只求同根同形）。"""
    w = w.lower().strip("'")
    if w.endswith("'s"):
        w = w[:-2]
    if len(w) <= 3:
        return w
    if w.endswith('ies') and len(w) > 4:
        w = w[:-3] + 'y'
    elif w.endswith('sses'):
        w = w[:-2]
    elif w.endswith('es') and w[:-2].endswith(('s', 'x', 'ch', 'sh', 'z')):
        w = w[:-2]
    elif w.endswith('s') and not w.endswith(('ss', 'us', 'is')):
        w = w[:-1]
    for suf in ('ing', 'ed'):
        if w.endswith(suf) and len(w) - len(suf) >= 3 and set(w[:-len(suf)]) & VOWEL:
            w = w[:-len(suf)]
            if len(w) > 3 and w[-1] == w[-2] and w[-1] not in 'lsz':
                w = w[:-1]          # running → run
            elif w.endswith(('at', 'iz', 'bl')):
                w = w + 'e'         # rotating → rotate
            break
    return w

STOP = {'for', 'and', 'with', 'the', 'a', 'an', 'of', 'to', 'in', 'on', 'at', 'by', 'de', 'para', 'en', 'la',
        'el', 'los', 'las', 'y', 'con', 'woman', 'women', 'man', 'men', 'kid', 'home', 'adult', 'best', 'new'}

class Norm:
    def __init__(self, syn):
        self.map = {}
        for root, alts in (syn.get('groups') or {}).items():
            r = stem(root)
            for a in [root] + list(alts):
                self.map[stem(a)] = r
        self.core = {self.map.get(stem(c), stem(c)) for c in syn.get('core') or []}

    def toks(self, s):
        out = []
        for t in re.findall(r"[a-z0-9áéíóúñäöüß']+", s.lower()):
            st = stem(t)
            out.append(self.map.get(st, st))
        return out

def contains_seq(t, r):
    n = len(r)
    return any(t[i:i + n] == r for i in range(len(t) - n + 1))

def seed_roots(terms):
    """在高流量词的词根里找 1–3 个词根的组合，使“同时包含这些词根（任意顺序）”的流量占比 >= SEED_COVER；
    取词根最多、覆盖最高的组合。返回 (组合, 覆盖率, 连续覆盖率) 或 (None, 最高单词根覆盖, 0)。"""
    total = sum(w for _, w in terms) or 1
    freq = defaultdict(float)
    for t, w in terms:
        for g in set(t):
            if g not in STOP:
                freq[g] += w
    cand = [g for g, _ in sorted(freq.items(), key=lambda x: -x[1])[:12]]
    best = None
    for n in (3, 2, 1):
        for combo in combinations(cand, n):
            s = set(combo)
            cov = sum(w for t, w in terms if s <= set(t)) / total
            if cov >= SEED_COVER and (best is None or cov > best[1]):
                best = (list(combo), cov)
        if best:
            break
    if not best:
        top = max(freq.values()) / total if freq else 0
        return None, top, 0
    combo, cov = best
    # 连续覆盖：按最高流量词里的出现顺序排好种子，看有多少流量的词连续包含它
    order = combo
    for t, _ in sorted(terms, key=lambda x: -x[1]):
        if set(combo) <= set(t):
            order = sorted(combo, key=t.index)
            break
    seq = sum(w for t, w in terms if contains_seq(t, order)) / total if len(order) > 1 else cov
    return order, cov, seq

def multi_seeds(terms, max_groups=4):
    """贪心：每次挑一个 2 词根组合（任意顺序），覆盖剩余流量最多的，最多 max_groups 组。
    合计覆盖 >= SEED_COVER 时返回 [(组合, 新增覆盖)...]，否则 None。用来识别“一个活动里放了几个手动广泛词”。"""
    total = sum(w for _, w in terms) or 1
    freq = defaultdict(float)
    for t, w in terms:
        for g in set(t):
            if g not in STOP:
                freq[g] += w
    cand = [g for g, _ in sorted(freq.items(), key=lambda x: -x[1])[:15]]
    pairs = [set(c) for c in combinations(cand, 2)]
    left = list(terms); picked = []; covered = 0
    for _ in range(max_groups):
        best, bw = None, 0
        for pr in pairs:
            w = sum(x for t, x in left if pr <= set(t))
            if w > bw:
                best, bw = pr, w
        if not best or bw / total < 0.05:
            break
        picked.append((sorted(best), bw / total)); covered += bw / total
        left = [(t, x) for t, x in left if not best <= set(t)]
        if covered >= SEED_COVER:
            return picked
    return None

def main():
    args = sys.argv[1:]
    opts = {'--out': 'frame.csv', '--syn': None}
    for k in list(opts):
        if k in args:
            i = args.index(k); opts[k] = args[i + 1]; del args[i:i + 2]
    syn = json.load(open(opts['--syn'])) if opts['--syn'] else {}
    N = Norm(syn)
    data = load(args)

    camps = {}
    for _, d in data['get_parent_asin_ad_campaigns']:
        for c in d.get('campaigns', []):
            camps[c['id']] = c
    pos = {}
    for _, d in data['get_parent_asin_ad_campaign_detail']:
        c = d.get('campaign', {})
        tot = (d.get('summary') or {}).get('traffic') or 0
        pos[c.get('id')] = ({p['position']: p.get('traffic', 0) for p in d.get('positions', [])}, tot)
    kw = defaultdict(dict)
    pages = defaultdict(lambda: [0, set()])   # cid → [总词数, 已拉页]
    for a, d in data['get_parent_asin_ad_keywords']:
        c = d.get('campaign') or {}
        cid = c.get('id') or a.get('campaign_id')
        if not cid:
            continue
        for k in d.get('keywords', []):
            kw[cid][k['keyword']] = k
        pages[cid][0] = d.get('total') or pages[cid][0]
        pages[cid][1].add(d.get('page') or 1)
    more = [(cid, sorted(p[1]), p[0]) for cid, p in pages.items() if len(kw[cid]) < p[0]]
    organic = {}
    for _, d in data['get_asin_keywords']:
        for r in d.get('list', []):
            ts = (r.get('trafficSummary') or {}).get('traffic') or {}
            organic[r['searchTerm'].lower()] = ts.get('organic') or 0
    has_rel = bool(organic) or bool(N.core)

    def related(k, t):
        if organic.get(k['keyword'].lower(), 0) > 0:
            return True
        return bool(N.core & set(t))

    rows, summ = [], []
    order = sorted(camps.values(), key=lambda c: -c.get('traffic', 0))
    for n, c in enumerate(order, 1):
        cid = c['id']
        ks = sorted(kw.get(cid, {}).values(), key=lambda k: -k.get('adTraffic', 0))
        terms = [(N.toks(k['keyword']), k.get('adTraffic', 0)) for k in ks]
        tot = sum(w for _, w in terms) or 1
        nk = len(ks)
        p, ptot = pos.get(cid, ({}, 0))
        ptot = ptot or sum(p.values()) or 1
        top1 = (ks[0]['adTraffic'] / tot) if ks else 0
        vols = [(k.get('marketMetrics') or {}).get('weeklySearchVolume') for k in ks]
        lowvol = sum(1 for v in vols if v is not None and v < 1000) / nk if nk else 0
        relflags = [related(k, t) for k, (t, _) in zip(ks, terms)]
        rel = sum(w for f, (_, w) in zip(relflags, terms) if f) / tot if has_rel else None
        off = [k['keyword'] for k, f in zip(ks, relflags) if has_rel and not f]
        offn = len(off) / nk if nk else 0
        asin_like = sum(1 for k in ks if re.search(r'\bb0[0-9a-z]{8}\b', k['keyword'].lower()))
        shared = sum(1 for k in ks if len(k.get('campaigns') or []) > 1)
        seed, cov, seq = seed_roots(terms) if terms else (None, 0, 0)
        # 不相关词是否集中在同一个“外来”词根上（手动投竞品词、跨类词的信号）
        offw = [(t, w) for (t, w), f in zip(terms, relflags) if has_rel and not f]
        off_seed = seed_roots(offw)[0] if len(offw) >= 3 else None
        seedtxt = ' + '.join(seed) if seed else ''

        # 初判（线索，不是结论）
        if nk == 0:
            guess = '无词（可能只在详情页或前 3 页以外展示）'
        elif nk <= 3 and (top1 >= 0.8 or len({' '.join(t) for t, _ in terms}) == 1):
            guess = f'精准：{ks[0]["keyword"]}'
        elif nk <= 3:
            guess = '少量词：多个精准，或低量词组、广泛'
        elif seed and (rel is None or rel >= 0.3 or len(seed) >= 2):
            if len(seed) >= 2 and seq >= PHRASE_SEQ:
                sd = ' '.join(seed)
                guess = f'词组：{sd}' if (lowvol >= 0.2 or nk > 15) else f'词组：{sd}，或同词根多个精准（长尾少）'
            elif len(seed) == 1:
                guess = f'广泛或词组：{seedtxt}（单词根无法区分）'
            else:
                guess = f'广泛：{seedtxt}'
            if guess.startswith('词组') and seq < 0.999:
                guess += '（连续 {:.0%}，语序天然固定时广泛也可能）'.format(seq)
        elif nk >= 4 and (ms := multi_seeds(terms)) and (rel is None or rel >= 0.3):
            # 种子也解释不了的不相关词（零散怪词、跨类、外语、无关品牌）多，说明更像自动紧密
            unexp = sum(1 for (t, _), fl in zip(terms, relflags)
                        if has_rel and not fl and not any(set(g) <= set(t) for g, _ in ms)) / nk
            guess = ('多个广泛词：' if unexp < 0.1 else f'自动（紧密）或多个广泛词（种子解释不了的不相关词 {unexp:.0%}）：') \
                + '；'.join(f'{" + ".join(g)} {v:.0%}' for g, v in ms)
        elif nk < MANY:
            guess = ('非本品词为主：商品定位、自动，或手动投竞品词、跨类词' if rel is not None and rel < 0.3
                     else '多个手动词（精准或混合）')
        elif rel is not None and rel >= RELATED_CLOSE:
            guess = '自动（紧密）' if offn < 0.2 else f'自动（紧密为主，含宽泛长尾：不相关词 {offn:.0%} 个数、{1 - rel:.0%} 流量）'
        elif off_seed:
            guess = f'手动投非本品词（{" + ".join(off_seed)}）或商品定位，可能混自动'
        elif rel is None:
            guess = '自动（紧密或宽泛，缺相关性数据）'
        else:
            guess = '自动（宽泛）' if rel >= 0.3 else '自动（宽泛）或商品定位（同类、关联）'
        if c['type'] in ('sb', 'sbv') and guess.startswith('自动'):
            # 品牌广告没有自动投放，但有“主题定位”（按品牌和落地页自动扩词）：词散而相关 = 多个手动词（多为广泛）；词散而不相关 = 品类或商品定位
            guess = ('多个手动关键词（多为广泛），或主题定位' if rel is None or rel >= RELATED_CLOSE
                     else '主题定位、品类或商品定位，或多个短头词广泛')
        if rel is not None and rel < 0.3 and guess.startswith(('词组', '广泛')):
            guess += '（非本品词：手动投竞品词、跨类词，或商品定位）'
        if asin_like:
            guess += '；含 ASIN 搜索词'

        posstr = ' '.join(f'{k}{v / ptot:.0%}' for k, v in sorted(p.items(), key=lambda x: -x[1]) if v / ptot >= 0.05)
        summ.append([n, c['type'].upper(), c['name'][-4:], c.get('traffic'), f"{c.get('shareOfParentAdTraffic', 0):.1%}",
                     c.get('avgDisplayHours'), c.get('variationCount'), nk, f'{top1:.0%}', f'{lowvol:.0%}',
                     (f'{seedtxt} {cov:.0%}' + (f' 连续{seq:.0%}' if len(seed) > 1 else '')) if seed else f'- 最高{cov:.0%}',
                     '-' if rel is None else f'{rel:.0%}', posstr, shared, guess,
                     ' | '.join(k['keyword'] for k in ks[:6]), ' | '.join(off[:6])])
        for k, (t, _), f in zip(ks, terms, relflags):
            rows.append([n, c['type'], c['name'][-4:], k['keyword'], ' '.join(t), k.get('adTraffic'),
                         f"{k.get('trafficShare', 0):.3f}", (k.get('marketMetrics') or {}).get('weeklySearchVolume'),
                         organic.get(k['keyword'].lower(), ''), 'Y' if f else ('N' if has_rel else ''),
                         len(k.get('campaigns') or []), ','.join(v['asin'] for v in k.get('variations') or [])])

    hdr = ['#', '类型', '编码', '流量', '父体占比', '日均展示h', '变体数', '词数', 'Top1占比', '周搜索量<1000词占比',
           '种子词根及覆盖', '相关词占比', '展示位', '跨活动词', '初判', '前6词', '前6个不相关词']
    print('\t'.join(hdr))
    for s in summ:
        print('\t'.join(str(x) for x in s))
    if more:
        print('\n需要翻页（活动, 已拉页, 总词数）:', more)
    big = [c for c in order if len(kw.get(c['id'], {})) >= MANY]
    if big:
        print('\n大活动高频词根（含该词根的流量占比，供写 --syn 同义词表）:')
        for c in big:
            ks = kw[c['id']].values()
            tot = sum(k.get('adTraffic', 0) for k in ks) or 1
            f = defaultdict(float)
            for k in ks:
                for g in set(N.toks(k['keyword'])):
                    if g not in STOP:
                        f[g] += k.get('adTraffic', 0)
            print(f"  {c['name'][-4:]}: " + ', '.join(f'{g} {v / tot:.0%}' for g, v in sorted(f.items(), key=lambda x: -x[1])[:15]))
    with open(opts['--out'], 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['#', '类型', '编码', '词', '归并后词根', '广告流量', '活动内占比', '周搜索量', '目标ASIN自然流量', '相关',
                    '同类型活动数', '变体'])
        w.writerows(rows)
    print(f'\n逐词明细: {opts["--out"]}（{len(rows)} 行）')

if __name__ == '__main__':
    main()
