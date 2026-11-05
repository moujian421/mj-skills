#!/usr/bin/env python3
"""词根表现：把含同一个词根（场景、材质、人群等修饰词）的搜索词合起来看，按活动拆开。否词前用。

输入：领星 ad_campaign_search_term_report 原始返回（不要用 group_type=query，要保留 campaign_name），建议 60–90 天。
     可以用 search_type=query + search_text=<词根> 只拉含该词根的搜索词。
用法：
  python3 root_stats.py FILE.json [FILE2.json ...] --roots garage outdoor kids --target 0.30
  python3 root_stats.py FILE.json --auto 15 --target 0.30     # 不给词根时，列出花费最高的 15 个单词词根
输出：每个词根的合计（花费、点击、订单、销售额、ACoS），再按活动拆开，标出 ACoS 高于目标的活动。
判断（规则见 rules.md §4）：词根合计和在某活动里都差、且该活动里含词根的搜索词没有好的 → 可以在该活动用词根做词组否定；
     只有个别搜索词差 → 只精确否定那几个词；在某活动里表现好 → 那个活动不否。
"""
import argparse, collections, json, re

NUM = lambda x: float(x) if x not in (None, '', '-', '--') else 0.0
STOP = set('for the and with of to in a an on by x'.split())


def rows(paths):
    for p in paths:
        d = json.load(open(p))
        r = d['data']['data'] if isinstance(d.get('data'), dict) else d['data']
        for x in r:
            if x.get('query'):
                yield x


def toks(q):
    return set(re.findall(r'[a-z0-9]+', q.lower())) - STOP


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('files', nargs='+')
    ap.add_argument('--roots', nargs='*', default=[])
    ap.add_argument('--auto', type=int, default=0)
    ap.add_argument('--target', type=float, default=0.30)
    a = ap.parse_args()
    data = list(rows(a.files))
    roots = [r.lower() for r in a.roots]
    if not roots:
        sp = collections.Counter()
        for x in data:
            for t in toks(x['query']):
                sp[t] += NUM(x.get('spends'))
        roots = [t for t, _ in sp.most_common(a.auto or 15)]
    acos = lambda c: f"{c['spends']/c['sales']*100:.0f}%" if c['sales'] else ('∞' if c['spends'] else '-')
    for root in roots:
        tot, by_camp, terms = collections.Counter(), collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
        for x in data:
            if root not in toks(x['query']) and root not in x['query'].lower():
                continue
            c = x.get('campaign_name') or '?'
            for k in ('spends', 'clicks', 'orders', 'sales'):
                v = NUM(x.get(k)); tot[k] += v; by_camp[c][k] += v; terms[(c, x['query'])][k] += v
        if not tot['clicks']:
            print(f'\n## {root}: 无数据'); continue
        print(f"\n## 词根 {root}：花费 ${tot['spends']:.0f} 点击 {tot['clicks']:.0f} 订单 {tot['orders']:.0f} 销售额 ${tot['sales']:.0f} ACoS {acos(tot)}  （{len(terms)} 个搜索词×活动）")
        for c, v in sorted(by_camp.items(), key=lambda kv: -kv[1]['spends']):
            bad = (v['sales'] == 0 and v['spends'] > 0) or (v['sales'] and v['spends'] / v['sales'] > a.target)
            good_terms = [q for (cc, q), t in terms.items() if cc == c and t['sales'] and t['spends'] / t['sales'] <= a.target]
            print(f"  {'✗' if bad else '✓'} {c} | ${v['spends']:.0f} / {v['clicks']:.0f} 点击 / {v['orders']:.0f} 单 / ACoS {acos(v)}"
                  + (f" | 其中达标的词: {', '.join(good_terms[:3])}" if bad and good_terms else ''))


if __name__ == '__main__':
    main()
