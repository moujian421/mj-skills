"""首饰盒调研图表：从 recovered.json（agy 原始返回）直接画图，数字不经模型转抄。
规则（用户 2026-10-27）：销量/销售额用柱状图；搜索量的月度变化用折线；销量占比用折线；
图例放图外、数值标注加白底不压线；左右放不下就上下排；不用双纵轴。"""
import json, csv, sys, os, datetime, collections, glob
import numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
D = sys.argv[1]; OUT = D + '/charts'; os.makedirs(OUT, exist_ok=True)
for f in ['/System/Library/Fonts/Hiragino Sans GB.ttc', '/System/Library/Fonts/STHeiti Medium.ttc']:
    if os.path.exists(f): font_manager.fontManager.addfont(f)
plt.rcParams.update({'font.family': ['Hiragino Sans GB', 'STHeiti'], 'axes.unicode_minus': False,
    'figure.facecolor': '#fcfcfb', 'axes.facecolor': '#fcfcfb', 'axes.edgecolor': '#c3c2b7',
    'axes.labelcolor': '#52514e', 'xtick.color': '#52514e', 'ytick.color': '#52514e', 'text.color': '#0b0b0b',
    'axes.grid': True, 'axes.grid.axis': 'y', 'axes.axisbelow': True, 'grid.color': '#e9e8e4', 'grid.linewidth': 0.6,
    'axes.spines.top': False, 'axes.spines.right': False, 'axes.titlesize': 12, 'axes.titleweight': 'bold',
    'font.size': 9.5, 'legend.frameon': False})
C = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948']
GRAY = '#b9b8b2'; BOX = dict(boxstyle='round,pad=0.15', fc='#fcfcfb', ec='none', alpha=0.9)
REC = json.load(open(D + '/_data/recovered.json'))
for p in glob.glob(D + '/_data/rD/raw/*.json'):  # 补拉的品牌代表 ASIN
    REC.append({'server': 'xydc-mcp', 'tool': 'brand_top_asin', 'args': {}, 'data': json.load(open(p))})
CAT = 'us_202609_59P_vlxekm'; NODE = '16350291'
def find(server, tool, **kw):
    for r in REC:
        if r['server'] != server or r['tool'] != tool: continue
        a = r['args']; a2 = a.get('request', a)
        if all((a.get(k) if k in a else a2.get(k)) == v for k, v in kw.items()): return r['data']
    raise SystemExit(f'missing {server}/{tool} {kw}')
data = lambda x: x.get('data', x) if isinstance(x, dict) else x
def save(fig, n, src):
    fig.text(0.01, 0.004, '数据来源：' + src + '（采集日期 2026-10-26）', fontsize=8, color='#7a7973')
    fig.tight_layout(rect=(0, 0.02, 1, 1)); fig.savefig(f'{OUT}/fig{n}.png', dpi=160); plt.close(fig)
def ym(s): return s[2:7]
def ticks(ax, labels, step, rot=0):
    ax.set_xticks(range(0, len(labels), step)); ax.set_xticklabels(labels[::step], rotation=rot)
def lab(ax, x, y, s, dy=6, fs=8):
    ax.annotate(s, (x, y), xytext=(0, dy), textcoords='offset points', ha='center', va='bottom', fontsize=fs, bbox=BOX)
def slab(ax, ys, fmt, idxs=None, fs=8):
    """折线标注：谷底点标在下方，其余标在上方，避免压线。"""
    n = len(ys)
    for i in (range(n) if idxs is None else idxs):
        nb = [ys[j] for j in (i-1, i+1) if 0 <= j < n]
        lo, hi = ax.get_ylim() if ax.get_ylim()[1] > 1 else (0, max(ys) or 1)
        below = bool(nb) and ys[i] < min(nb) and (ys[i] - lo) > 0.18 * (hi - lo)
        ax.annotate(fmt(ys[i]), (i, ys[i]), xytext=(0, -9 if below else 7), textcoords='offset points',
                    ha='center', va='top' if below else 'bottom', fontsize=fs, bbox=BOX, zorder=5)
def legend_below(ax, ncol=4, **kw):
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.13), ncol=ncol, fontsize=8, **kw)
def bar_line(ax, cats, bars, line, bar_lab, line_lab, title, unit='%'):
    """同一纵轴（%）：柱=商品数占比，折线=销量占比。"""
    x = np.arange(len(cats))
    ax.bar(x, bars, 0.55, color=C[0], label=bar_lab)
    ax.plot(x, line, color=C[1], lw=2, marker='o', ms=6, label=line_lab, zorder=3)
    ax.set_ylim(0, max(max(bars), max(line)) * 1.25)
    slab(ax, list(line), lambda v: f'{v:.1f}{unit}')
    ax.set_xticks(x); ax.set_xticklabels(cats, fontsize=8.5); ax.set_title(title); legend_below(ax, 2)

# fig1 销量/销售额：全部柱状图，上下三张
ms = data(find('xydc-mcp', 'get_category_market_size_trends', categoryId=CAT))['trends']
lb = [ym(t['localDate']) for t in ms]; sales = [t['sales']['value']/1e4 for t in ms]; rev = [float(t['salesRevenue']['value'])/1e4 for t in ms]
st = [x.split('=') for x in data(find('sorftime-mcp', 'category_trend', node_id=NODE, trend_index='SalesCount'))]
fig, axs = plt.subplots(3, 1, figsize=(10, 9))
axs[0].bar(range(len(sales)), sales, color=C[0], width=0.7); axs[0].set_title('西柚 首饰盒类目 月销量（万件）'); ticks(axs[0], lb, 3)
axs[1].bar(range(len(rev)), rev, color=C[1], width=0.7); axs[1].set_title('西柚 首饰盒类目 月销售额（万美元）'); ticks(axs[1], lb, 3)
for ax, v in ((axs[0], sales), (axs[1], rev)):
    for i in (lb.index('24-12'), lb.index('25-12')): lab(ax, i, v[i], f'{v[i]:.1f}', dy=2)
    ax.set_ylim(0, max(v) * 1.15)
sl = [a[2:] for a, b in st]; sv = [int(b)/1e4 for a, b in st]
axs[2].bar(range(len(sv)), sv, color=C[2], width=0.7); ticks(axs[2], sl, 2); axs[2].set_ylim(0, max(sv)*1.15)
axs[2].set_title('Sorftime 节点 16350291 Top100 月销量（万件；含旅行包/戒指盒；2026-10 截至 26 日）')
save(fig, 1, '西柚、Sorftime')

# fig2 季节系数（系数不是销量，柱状）
se = data(find('xydc-mcp', 'get_category_seasonality', categoryId=CAT))['monthInfos']
col = {'peak': C[1], 'shoulder': C[3], 'off': C[0]}; nm = {'peak': '旺季', 'shoulder': '次旺/过渡', 'off': '平淡季'}
fig, ax = plt.subplots(figsize=(9, 4.2))
vals = [float(m['monthlySalesMultiplier']) for m in se]
ax.bar([f"{m['month']}月" for m in se], vals, color=[col[m['seasonType']] for m in se], width=0.65)
for i, v in enumerate(vals): lab(ax, i, v, f'{v:.2f}', dy=2)
ax.axhline(1, color=GRAY, lw=1, ls='--'); ax.set_ylim(0, max(vals)*1.15); ax.set_title('西柚 首饰盒 1–12 月销量季节系数（1.0 = 全年月均）')
ax.legend(handles=[Patch(color=col[k], label=nm[k]) for k in ('peak', 'shoulder', 'off')], loc='upper center', bbox_to_anchor=(0.5, -0.1), ncol=3)
save(fig, 2, '西柚')

# fig3 搜索量月度折线 + Google 5 年 + Google 近 24 个月
cur = data(find('xydc-mcp', 'get_keyword_aba_trends', start_week='2025-10-26'))['entities']
prv = {e['searchTerm']: e['trends'] for e in data(find('xydc-mcp', 'get_keyword_aba_trends', start_week='2024-10-27'))['entities']}
def monthly(tr):
    m = collections.OrderedDict()
    for t in tr:
        k = t['reportFromDate'][:7]; m[k] = m.get(k, 0) + (t['weeklySearchVolume'] or 0)
    ks = list(m)[1:-1]  # 去掉首尾不完整月
    return ks, [m[k] for k in ks]
fig, axs = plt.subplots(4, 1, figsize=(10, 15), gridspec_kw={'height_ratios': [1, 1.15, 1, 1]})
for k, e in enumerate(cur):
    ks, vs = monthly(prv.get(e['searchTerm'], []) + e['trends'])
    if e['searchTerm'] == 'jewelry box':
        axs[0].plot(range(len(vs)), [v/1e4 for v in vs], color=C[0], lw=2, marker='o', ms=4)
        for i in (ks.index('2024-12'), ks.index('2025-12')): lab(axs[0], i, vs[i]/1e4, f'{vs[i]/1e4:.1f}')
        axs[0].set_ylim(0, max(vs)/1e4*1.2); ticks(axs[0], [x[2:] for x in ks], 2); axs[0].set_title('“jewelry box” ABA 月搜索量（万次，按周汇总；首尾不完整月已去掉）')
    else:
        axs[1].plot(range(len(vs)), [v/1e3 for v in vs], color=C[k % 8], lw=1.8, marker='o', ms=3, label=e['searchTerm'])
        ticks(axs[1], [x[2:] for x in ks], 2)
axs[1].set_title('其他 7 个核心词 ABA 月搜索量（千次）'); legend_below(axs[1], 4)
g = data(find('sellersprite-mcp', 'google_trend', keyword='jewelry box'))['items']
gl = [datetime.datetime.utcfromtimestamp(i['time']/1000).strftime('%y-%m') for i in g]; gv = [i['value'] for i in g]
axs[2].plot(range(len(gv)), gv, color=C[2], lw=1.8); ticks(axs[2], gl, 6); axs[2].set_ylim(0, 105)
axs[2].set_title('Google Trends “jewelry box” 美国热度，近 5 年（0–100）')
g24, l24 = gv[-24:], gl[-24:]
axs[3].plot(range(24), g24, color=C[2], lw=2, marker='o', ms=4)
slab(axs[3], g24, lambda v: str(v), fs=7.5)
ticks(axs[3], l24, 1, rot=45); axs[3].set_ylim(0, 110); axs[3].set_title('Google Trends “jewelry box” 近 24 个月逐月热度')
save(fig, 3, '西柚、卖家精灵')

# fig4 品牌份额（带代表 ASIN）上 + Top3 品牌占比折线 下
br = data(find('xydc-mcp', 'get_category_brand_market_size', categoryId=CAT))['list']
asin = {}
def add(b, a, s):
    if b and (b.lower() not in asin or s > asin[b.lower()][1]): asin[b.lower()] = (a, s)
for r in REC:
    if r['tool'] == 'get_category_sales_ranking' and r['args'].get('categoryId') == CAT or r['tool'] == 'brand_top_asin':
        for x in data(r['data'])['list']: add(x['asinInfo']['brand'], x['asinInfo']['primaryAsin'], x['metrics']['sales']['value'] or 0)
    if r['tool'] == 'get_category_new_release_opportunity_trends' and r['args'].get('categoryId') == CAT:
        for x in data(r['data'])['list']: add(x.get('brand'), x['primaryAsin'], 0)
def blabel(b):
    if b['brand'].lower() == 'generic': a = '多个无品牌商品'
    else: a = asin.get(b['brand'].lower(), ('?',))[0]
    return f"{b['brand']}  {a}  ${float(b['priceDistribution']['weightedAvg']):.0f}"
fig, axs = plt.subplots(2, 1, figsize=(10, 11), gridspec_kw={'height_ratios': [2.2, 1]})
names = [blabel(b) for b in br][::-1]; sh = [float(b['sales']['ratio'])*100 for b in br][::-1]
axs[0].barh(names, sh, color=C[0], height=0.65)
for i, v in enumerate(sh): axs[0].text(v + 0.15, i, f'{v:.1f}%', va='center', fontsize=8)
axs[0].set_title('西柚 Top20 品牌近 30 天销量份额（品牌｜代表 ASIN｜加权均价）'); axs[0].grid(axis='x'); axs[0].grid(axis='y', visible=False)
axs[0].set_xlim(0, max(sh)*1.15); axs[0].tick_params(axis='y', labelsize=8.5)
t3 = [x.split('=') for x in data(find('sorftime-mcp', 'category_trend', node_id=NODE, trend_index='Top3BrandSalesAmountShare'))]
xl = [a[2:] for a, b in t3]; yv = [float(b) for a, b in t3]
axs[1].plot(range(len(yv)), yv, color=C[1], lw=2, marker='o', ms=4)
slab(axs[1], yv, lambda v: f'{v:.1f}%', idxs=[yv.index(max(yv)), yv.index(min(yv)), len(yv)-1])
ticks(axs[1], xl, 2); axs[1].set_ylim(0, 42); axs[1].set_title('Sorftime 节点 Top100：Top3 品牌销售额占比（%）')
save(fig, 4, '西柚、Sorftime')
print('代表ASIN', {b['brand']: asin.get(b['brand'].lower(), ('-',))[0] for b in br})

# fig5 卖家所属地 / 配送方式：上下，柱=商品数占比，折线=销量占比
cn = data(find('sellersprite-mcp', 'market_seller_country_distribution', month='202609'))
ty = data(find('sellersprite-mcp', 'market_seller_type_concentration', month='202609'))
fig, axs = plt.subplots(2, 1, figsize=(9, 8))
bar_line(axs[0], [x['label'] for x in cn], [x['products'] for x in cn], [x['unitsRatio']*100 for x in cn], '商品数占比（%）', '销量占比（%）', '卖家所属地')
bar_line(axs[1], [{'NA': 'FBM/其他', 'FBA': 'FBA', 'Amazon自营': '亚马逊自营'}.get(x['label'], x['label']) for x in ty],
         [x['asinRatio']*100 for x in ty], [x['unitsRatio']*100 for x in ty], '商品数占比（%）', '销量占比（%）', '配送方式')
save(fig, 5, '卖家精灵（节点 Top100，2026-09）')

# fig6 上架时间（柱=商品数，折线=销量占比） + 新品销量占比折线
ld = data(find('sellersprite-mcp', 'market_listing_date_distribution', month='202609'))
nr = data(find('xydc-mcp', 'get_category_new_release_opportunity_trends', categoryId=CAT))['trends']
fig, axs = plt.subplots(2, 1, figsize=(10, 8.6))
bar_line(axs[0], ['≤'+x['label'] if x['label'] != '3年以上' else x['label'] for x in ld], [x['products'] for x in ld], [x['unitsRatio']*100 for x in ld],
         '商品数（个，Top100 即 %）', '销量占比（%）', '卖家精灵 节点 Top100 上架时间分布（2026-09）')
nl = [ym(t['localDate']) for t in nr]; nv = [float(t['newRelease']['sales']['ratio'])*100 for t in nr]
axs[1].plot(range(len(nv)), nv, color=C[2], lw=2, marker='o', ms=3.5); ticks(axs[1], nl, 3); axs[1].set_ylim(0, 14)
slab(axs[1], nv, lambda v: f'{v:.1f}%', idxs=[nl.index(k) for k in ('25-01', '24-07', '26-03', '26-05', '26-08')])
axs[1].set_title('西柚 首饰盒类目 新品销量占比（%）')
save(fig, 6, '卖家精灵、西柚')

# fig7 $25–60 段 Top10（销量柱 + 同比柱）
sr = data(find('xydc-mcp', 'get_category_sales_ranking', categoryId=CAT, pageSize=10))['list']
fig, axs = plt.subplots(2, 1, figsize=(10, 8))
xl = [f"{r['asinInfo']['brand']}\n{r['asinInfo']['primaryAsin']}" for r in sr]
new = [r['asinInfo']['streetDate'] >= '2025-10-01' for r in sr]; sv = [r['metrics']['sales']['value'] for r in sr]
axs[0].bar(range(10), sv, color=[C[1] if n else C[0] for n in new], width=0.65)
for i, v in enumerate(sv): lab(axs[0], i, v, f'{v:,}', dy=2)
axs[0].set_ylim(0, max(sv)*1.15); axs[0].set_xticks(range(10)); axs[0].set_xticklabels(xl, fontsize=7.5)
axs[0].set_title('西柚 $25–60 段 Top10：近 30 天销量（件）')
axs[0].legend(handles=[Patch(color=C[0], label='上架 ≥1 年'), Patch(color=C[1], label='上架 <1 年（新品）')], loc='upper right')
yo = [r['metrics']['sales']['yoy']['rate'] for r in sr]; yv = [float(v)*100 if v is not None else 0 for v in yo]
axs[1].bar(range(10), yv, color=[C[2] if v > 0 else C[7] for v in yv], width=0.65); axs[1].axhline(0, color='#52514e', lw=0.8)
for i, (v, o) in enumerate(zip(yv, yo)):
    axs[1].annotate('无去年数据' if o is None else f'{v:+.0f}%', (i, v), xytext=(0, 4 if v >= 0 else -12), textcoords='offset points', ha='center', fontsize=8, bbox=BOX)
axs[1].set_ylim(min(yv)-15, max(yv)*1.15); axs[1].set_xticks(range(10)); axs[1].set_xticklabels(xl, fontsize=7.5); axs[1].set_title('近 30 天销量同比（%）')
save(fig, 7, '西柚')

# fig8 价格带：月销量柱（堆叠）+ 销量占比折线 + 均价折线
pr = {x['priceType']: x for x in data(find('xydc-mcp', 'get_category_price_segment_trends', categoryId=CAT))['priceDistribution']}
nmap = {'lowPrice': '低价带 <$29', 'midPrice': '中价带 $29–65', 'highPrice': '高价带 >$65'}
lb = [ym(y['localDate']) for y in pr['lowPrice']['trends']]
S = {t: np.array([(y['sales']['value'] or 0) for y in x['trends']], float) for t, x in pr.items()}
tot = sum(S.values())
fig, axs = plt.subplots(3, 1, figsize=(10, 12))
bot = np.zeros(len(lb))
for k, t in enumerate(pr):
    axs[0].bar(range(len(lb)), S[t]/1e4, bottom=bot, color=C[k], width=0.72, label=nmap[t], edgecolor='#fcfcfb', linewidth=0.8); bot += S[t]/1e4
ticks(axs[0], lb, 3); axs[0].set_title('西柚 三档价格带 月销量（万件，堆叠）'); legend_below(axs[0], 3)
for k, t in enumerate(pr):
    sh = S[t]/tot*100; axs[1].plot(range(len(lb)), sh, color=C[k], lw=2, marker='o', ms=3, label=nmap[t])
    lab(axs[1], len(lb)-1, sh[-1], f'{sh[-1]:.0f}%', dy=6)
ticks(axs[1], lb, 3); axs[1].set_ylim(0, 80); axs[1].set_title('西柚 三档价格带 销量占比（%）'); legend_below(axs[1], 3)
ap = [x.split('=') for x in data(find('sorftime-mcp', 'category_trend', node_id=NODE, trend_index='AvgPrice'))]
axs[2].plot(range(len(ap)), [float(b) for a, b in ap], color=C[3], lw=2, marker='o', ms=3.5); ticks(axs[2], [a[2:] for a, b in ap], 2)
axs[2].set_ylim(10, 22); axs[2].set_title('Sorftime 节点 Top100 均价（美元，含低价旅行包等）')
save(fig, 8, '西柚、Sorftime')

# fig9 两家价格分布对照（解释口径差异）：西柚全类目分段占比折线 + 卖家精灵 节点 Top100 柱+折线
segs = []
for t in ('lowPrice', 'midPrice', 'highPrice'):
    r = float(pr[t]['sales']['recent']['ratio'])
    for d in pr[t]['priceDetails']:
        if t == 'highPrice': segs.append((f"${float(d['min']):.0f}+", r*100)); break
        segs.append((f"${float(d['min']):.0f}–{float(d['max']):.0f}", float(d['sales']['ratio'])*r*100))
pdist = data(find('sellersprite-mcp', 'market_price_distribution', month='202609'))
fig, axs = plt.subplots(2, 1, figsize=(10, 9))
axs[0].plot(range(len(segs)), [v for k, v in segs], color=C[1], lw=2, marker='o', ms=5)
yy = [v for k, v in segs]; slab(axs[0], yy, lambda v: f'{v:.1f}%', idxs=[i for i, v in enumerate(yy) if v >= 4], fs=7.5)
axs[0].set_xticks(range(len(segs))); axs[0].set_xticklabels([k for k, v in segs], rotation=45, ha='right', fontsize=7.5)
axs[0].set_ylim(0, max(v for k, v in segs)*1.3)
axs[0].set_title('西柚 首饰盒类目（596 个主商品，只含桌面首饰盒）各价格段销量占比（%，近 30 天）')
bar_line(axs[1], ['$'+x['label'] for x in pdist], [x['products'] for x in pdist], [x['unitsRatio']*100 for x in pdist],
         '商品数（个，Top100 即 %）', '销量占比（%）', '卖家精灵 节点 16350291 销量 Top100（69 个为旅行包/戒指盒/礼品袋）价格段分布')
save(fig, 9, '西柚、卖家精灵')

# fig10 评论数分层（柱=商品数占比，折线=销量占比） + 平均评论数折线
rv = data(find('xydc-mcp', 'get_category_review_analysis', categoryId=CAT))['ratingsTrends']
fig, axs = plt.subplots(2, 1, figsize=(10, 8.4))
cats = [f"{x['ratings']['min']}–{x['ratings']['max']}" if x['ratings']['max'] is not None else f"{x['ratings']['min']}+" for x in rv]
bar_line(axs[0], cats, [float(x['primaryAsinCount']['ratio'])*100 for x in rv], [float(x['sales']['ratio'])*100 for x in rv],
         '商品数占比（%）', '销量占比（%）', '西柚 按评论数分层（近 30 天）')
ar = [x.split('=') for x in data(find('sorftime-mcp', 'category_trend', node_id=NODE, trend_index='AvgRatingCount'))]
yv = [float(b) for a, b in ar]
axs[1].plot(range(len(yv)), yv, color=C[2], lw=2, marker='o', ms=3.5); ticks(axs[1], [a[2:] for a, b in ar], 2)
slab(axs[1], yv, lambda v: f'{v:,.0f}', idxs=[yv.index(max(yv)), len(yv)-2])
axs[1].set_ylim(0, 3000); axs[1].set_title('Sorftime 节点 Top100 平均评论数（条）')
save(fig, 10, '西柚、Sorftime')

# fig11 A+/视频：上下
eb = {x['label']: x for x in data(find('sellersprite-mcp', 'market_ebc_distribution', month='202609'))}
cats = ['有A+有视频', '有A+无视频', '无A+有视频', '无A+无视频']
fig, axs = plt.subplots(2, 1, figsize=(9, 8))
for ax, pre, ttl in ((axs[0], '', '节点 Top100 全部商品'), (axs[1], '新品', '节点 Top100 中的新品')):
    bar_line(ax, cats, [eb.get(pre + c, {}).get('productsRatio', 0) for c in cats], [eb.get(pre + c, {}).get('unitsRatio', 0) for c in cats],
             '商品数占比（%）', '销量占比（%）', ttl + '：A+ 与主图视频覆盖')
save(fig, 11, '卖家精灵（节点 Top100，2026-09）')

# fig12 流量词：搜索量柱 + 转化率柱（非时间序列）
kw = data(find('xydc-mcp', 'get_category_keywords', categoryId=CAT))['list'][:15]
fig, axs = plt.subplots(2, 1, figsize=(10, 8.4), sharex=True)
lbk = [k['searchTerm'] for k in kw]; vol = [int(k['searchVolume'])/1e4 for k in kw]
axs[0].bar(range(15), vol, color=C[0], width=0.65)
for i, v in enumerate(vol): lab(axs[0], i, v, f'{v:.1f}', dy=2, fs=7.5)
axs[0].set_ylim(0, max(vol)*1.15); axs[0].set_title('西柚 Top15 流量词 月搜索量（万次）')
cv = [float(k['adjustedClickConversionRate'])*100 if k['adjustedClickConversionRate'] else None for k in kw]
axs[1].bar(range(15), [v or 0 for v in cv], color=[C[2] if v else GRAY for v in cv], width=0.65)
for i, v in enumerate(cv): lab(axs[1], i, v or 0, f'{v:.1f}%' if v else '无数据', dy=2, fs=7.5)
axs[1].set_ylim(0, 8.5); axs[1].set_title('点击转化率（%）'); axs[1].set_xticks(range(15)); axs[1].set_xticklabels(lbk, rotation=35, ha='right', fontsize=8)
save(fig, 12, '西柚')

# fig13 流量结构：上下
tf = data(find('xydc-mcp', 'get_asin_traffic'))['entities']
bmap = {}
for r in REC:
    if r['tool'] in ('get_category_sales_ranking', 'brand_top_asin') and (r['tool'] == 'brand_top_asin' or r['args'].get('categoryId') == CAT):
        for x in data(r['data'])['list']: bmap[x['asinInfo']['primaryAsin']] = x['asinInfo']['brand']
fig, axs = plt.subplots(2, 1, figsize=(10, 10))
xl = [f"{bmap.get(e['asin'], '?')}\n{e['asin']}" for e in tf]
o = [e['organicTrafficScoreRatio']*100 for e in tf]; a = [e['advertisingTrafficScoreRatio']*100 for e in tf]
axs[0].bar(range(len(o)), o, color=C[0], width=0.65, label='自然流量')
axs[0].bar(range(len(a)), a, bottom=o, color=C[1], width=0.65, label='广告流量', edgecolor='#fcfcfb', linewidth=1)
for i, e in enumerate(tf): axs[0].text(i, 102, f"{e['totalTrafficScore']:,}", ha='center', fontsize=7.5)
axs[0].set_xticks(range(len(xl))); axs[0].set_xticklabels(xl, fontsize=7); axs[0].set_ylim(0, 110); legend_below(axs[0], 2)
axs[0].set_title('10 款对标竞品 近 7 天流量结构（%，柱顶数字为流量总分）')
ads = [r['data'] for r in REC if r['tool'] == 'get_parent_asin_ad_overview' and r['server'] == 'xydc-mcp']
seg = ['organic', 'sp', 'sb', 'sbv']; sn = {'organic': '自然', 'sp': 'SP', 'sb': 'SB', 'sbv': 'SBV'}
xl = [f"{bmap.get(data(d)['scope']['inputAsin'], '?')}\n{data(d)['scope']['inputAsin']}" for d in ads]; bottom = np.zeros(len(ads))
for k, s in enumerate(seg):
    v = np.array([next((x['shareOfTotalScore'] for x in data(d)['trafficScoreDistribution'] if x['source'] == s), 0)*100 for d in ads])
    axs[1].bar(range(len(ads)), v, bottom=bottom, color=C[k], width=0.55, label=sn[s], edgecolor='#fcfcfb', linewidth=1); bottom += v
axs[1].set_xticks(range(len(xl))); axs[1].set_xticklabels(xl, fontsize=8); legend_below(axs[1], 4); axs[1].set_ylim(0, 105)
axs[1].set_title('5 个父体 流量来源结构（%，近 7 天）')
save(fig, 13, '西柚')

# fig14 差评标签
rows = list(csv.DictReader(open(D + '/差评打标-96条.csv', encoding='utf-8-sig')))
cnt = collections.Counter(t for r in rows for t in r['标签'].split('；') if t); items = cnt.most_common(); n = len(rows)
fig, ax = plt.subplots(figsize=(10, 5))
ax.barh([k for k, v in items][::-1], [v for k, v in items][::-1], color=C[7], height=0.6)
for i, (k, v) in enumerate(items[::-1]): ax.text(v + 0.6, i, f'{v} 次（{v/n:.0%}）', va='center', fontsize=8.5)
ax.set_title(f'{n} 条差评问题标签频次（6 款 $26–53 竞品，近一年 1–3 星；一条可多标）'); ax.grid(axis='x'); ax.grid(axis='y', visible=False)
ax.set_xlim(0, max(cnt.values())*1.25)
save(fig, 14, 'Sorftime（评论），Gemini Flash 打标、Claude 抽查')
print('ok')
