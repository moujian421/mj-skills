#!/usr/bin/env python3
"""逐周对比搜索词：找出“之前出单、现在不出单”的词，以及新出单的词。

输入：领星 ad_campaign_search_term_report（group_type=query）每周一个原始返回文件，按时间从早到晚排列。
     文件可以是 oc_pull 的 raw/*.json，也可以是 MCP 工具结果落盘的 .txt（都是 {"data":{"data":[...]}}）。

用法：
  python3 st_weekly.py --weeks W1.json W2.json ... --labels 9/21 9/28 ... \
      [--exclude-baseline 3]   # 大促周在基准期里剔除（1 开始的序号，可多个）
      [--core "home gym flooring" "gym flooring" ...]  # 额外打印这些核心词的逐周走势
      [--out RUN/st_weekly.json]

规则：
  基准期 = 除最后一周外、未被剔除的各周；本周 = 最后一周。
  丢单/下滑词：基准期合计订单 >= 2，且本周订单 <= 基准期周均订单的一半。
  新出单词：基准期订单 = 0，本周订单 >= 1。
只打印统计和前 25 行，完整结果写 --out。
"""
import argparse, collections, json

F = ('spends', 'sales', 'orders', 'clicks', 'impressions')


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def load(path):
    d = json.load(open(path))
    rows = d['data']['data'] if isinstance(d.get('data'), dict) else d['data']
    agg = collections.defaultdict(collections.Counter)
    for r in rows:
        q = r.get('query')
        if not q:
            continue  # 第一行是汇总行
        for k in F:
            agg[q][k] += num(r.get(k))
    return agg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--weeks', nargs='+', required=True)
    ap.add_argument('--labels', nargs='+')
    ap.add_argument('--exclude-baseline', nargs='*', type=int, default=[])
    ap.add_argument('--core', nargs='*', default=[])
    ap.add_argument('--out')
    a = ap.parse_args()
    weeks = [load(p) for p in a.weeks]
    labels = a.labels or [f'W{i+1}' for i in range(len(weeks))]
    n = len(weeks)
    base_idx = [i for i in range(n - 1) if (i + 1) not in a.exclude_baseline]

    print('== 每周合计（花费/销售额/订单/点击/ACoS）')
    for lab, w in zip(labels, weeks):
        t = collections.Counter()
        for c in w.values():
            t.update(c)
        acos = f"{t['spends']/t['sales']*100:.0f}%" if t['sales'] else '∞'
        print(f"{lab}: {t['spends']:.0f} / {t['sales']:.0f} / {t['orders']:.0f} / {t['clicks']:.0f} / {acos}  ({len(w)} 个词)")

    terms = set().union(*[w.keys() for w in weeks])
    series = lambda q, k: [int(weeks[i].get(q, {}).get(k, 0)) for i in range(n)]
    lost, new = [], []
    for q in terms:
        bo = sum(weeks[i].get(q, {}).get('orders', 0) for i in base_idx)
        co = weeks[-1].get(q, {}).get('orders', 0)
        row = {'term': q, 'orders': series(q, 'orders'), 'clicks': series(q, 'clicks'),
               'impr': series(q, 'impressions'), 'spend': series(q, 'spends')}
        if bo >= 2 and co <= bo / max(len(base_idx), 1) / 2:
            row['base_orders'] = bo
            lost.append(row)
        elif bo == 0 and co >= 1:
            new.append(row)
    lost.sort(key=lambda r: -r['base_orders'])
    new.sort(key=lambda r: -r['orders'][-1])

    print(f"\n== 丢单/下滑词 {len(lost)} 个（基准期 {[labels[i] for i in base_idx]}）：订单 | 点击 | 曝光")
    for r in lost[:25]:
        print(f"{r['term'][:42]} | o {r['orders']} | clk {r['clicks']} | imp {r['impr']}")
    print(f"\n== 新出单词 {len(new)} 个")
    for r in new[:15]:
        print(f"{r['term'][:42]} | o {r['orders']} | clk {r['clicks']}")
    if a.core:
        print('\n== 核心词逐周走势：曝光 | 点击 | 订单 | 销售额 | 花费')
        for q in a.core:
            print(f"{q} | imp {series(q,'impressions')} | clk {series(q,'clicks')} | o {series(q,'orders')} | sa {series(q,'sales')} | sp {series(q,'spends')}")
    if a.out:
        json.dump({'labels': labels, 'lost': lost, 'new': new}, open(a.out, 'w'), ensure_ascii=False, indent=1)
        print('\n完整结果:', a.out)


if __name__ == '__main__':
    main()
