#!/usr/bin/env python3
"""活动层级的预警分档（按 ACoS），规则见 references/rules.md §4 第 2 关和 §4b。

输入：领星 ad_campaign_report 原始返回（按组合或名称筛选），四个时间段各一个文件。
用法：
  python3 risk_flags.py --cur 本周.json --prev 上周.json --d30 近30天.json --d60 近60天.json --target 0.30 [--cvr 0.0412]
--cvr 不给时用 60 天文件的汇总行算（订单/点击）。只评在投活动。
分档：
  ⏸ 暂停·降价后再开：30/60 天 ACoS ≤ 目标，14 天 ACoS > 目标×2（0 单的达到门槛：点击 ≥ 1.5/CVR 或花费 ≥ 1.5×目标CPA）
  🟠 预警·需你判断：30/60 天 ACoS ≤ 目标，14 天 ACoS 在目标×1.3–2，或 14 天 0 单、点击 ≥ 1/CVR 但没到门槛
  ⛔ 长期差：14/30/60 天 ACoS 都 > 目标×1.5（0 单的点击够）→ 直接暂停
"""
import argparse, json

NUM = lambda x: float(x) if x not in (None, '', '-', '--') else 0.0


def load(p):
    d = json.load(open(p))
    r = d['data']['data'] if isinstance(d.get('data'), dict) else d['data']
    return r[0], {x['campaign_id']: x for x in r[1:] if x.get('campaign_id')}


def kp(r):
    return NUM(r.get('spends')), NUM(r.get('clicks')), NUM(r.get('orders')), NUM(r.get('sales'))


def acos(s):
    return s[0] / s[3] if s[3] else (float('inf') if s[0] else None)


def fmt(a):
    return '-' if a is None else ('∞' if a == float('inf') else f'{a*100:.0f}%')


def main():
    ap = argparse.ArgumentParser()
    for k in ('cur', 'prev', 'd30', 'd60'):
        ap.add_argument('--' + k, required=True)
    ap.add_argument('--target', type=float, default=0.30)
    ap.add_argument('--cvr', type=float)
    a = ap.parse_args()
    _, cur = load(a.cur); _, prev = load(a.prev); _, d30 = load(a.d30); t60, d60 = load(a.d60)
    cvr = a.cvr or (NUM(t60.get('orders')) / NUM(t60.get('clicks')))
    aov = NUM(t60.get('sales')) / max(NUM(t60.get('orders')), 1)
    zero_clk = 1.5 / cvr                      # 0 单门槛：点击 ≥ 1.5/CVR
    zero_spend = 1.5 * aov * a.target         # 或花费 ≥ 1.5 × 目标 CPA（目标 CPA = 60 天单均价 × 目标 ACoS）
    hit0 = lambda clk, sp: clk >= zero_clk or sp >= zero_spend
    T = a.target
    out = {'⏸ 暂停·降价后再开': [], '🟠 预警·需你判断': [], '⛔ 长期差·直接暂停': []}
    for k, r in cur.items():
        if r.get('state') != 'enabled':
            continue
        x, y = kp(r), kp(prev.get(k, {}))
        s14 = tuple(x[i] + y[i] for i in range(4)); s30 = kp(d30.get(k, {})); s60 = kp(d60.get(k, {}))
        a14, a30, a60 = acos(s14), acos(s30), acos(s60)
        if a14 is None:
            continue
        long_ok = all(v is not None and v <= T * 1.1 for v in (a30, a60))  # 长期达标，允许 10% 误差
        zero = s14[2] == 0
        tier = None
        if long_ok:
            if (zero and hit0(s14[1], s14[0])) or (not zero and a14 > 2 * T):
                tier = '⏸ 暂停·降价后再开'
            elif (zero and s14[1] >= 1 / cvr) or (not zero and a14 > 1.3 * T):
                tier = '🟠 预警·需你判断'  # 0 单且点击 < 1/CVR 属于样本太少，不预警
        elif (a30 is not None and a30 > 1.5 * T and a60 is not None and a60 > 1.5 * T
              and hit0(s60[1], s60[0]) and a14 > 1.5 * T):
            tier = '⛔ 长期差·直接暂停'
        if tier:
            out[tier].append((s14[0], f"{r['name']} | 14天 ${s14[0]:.0f} {s14[1]:.0f}点击 {s14[2]:.0f}单 ACoS {fmt(a14)} | 30天 {fmt(a30)} | 60天 {fmt(a60)}"))
    print(f'目标 ACoS {T*100:.0f}%，0 单门槛：点击 ≥ {zero_clk:.0f} 或花费 ≥ ${zero_spend:.0f}（60 天 CVR {cvr*100:.2f}%，单均价 ${aov:.0f}）')
    for tier, lst in out.items():
        print(f'\n{tier}：' + ('无' if not lst else ''))
        for _, line in sorted(lst, reverse=True):
            print('  ' + line)


if __name__ == '__main__':
    main()
