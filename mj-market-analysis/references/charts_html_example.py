"""把 14 张图导出成可交互 HTML（悬停看数值），数据直接取自 recovered.json，规则同 charts.py。"""
import json, csv, sys, os, datetime, collections, glob
D = sys.argv[1]; OUT = D + '/charts_html'; os.makedirs(OUT, exist_ok=True)
JS = open(D + '/_data/minichart.js').read()
REC = json.load(open(D + '/_data/recovered.json'))
for p in glob.glob(D + '/_data/rD/raw/*.json'):
    REC.append({'server': 'xydc-mcp', 'tool': 'brand_top_asin', 'args': {}, 'data': json.load(open(p))})
CAT = 'us_202609_59P_vlxekm'; NODE = '16350291'
C = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948']
def find(server, tool, **kw):
    for r in REC:
        if r['server'] != server or r['tool'] != tool: continue
        a = r['args']; a2 = a.get('request', a)
        if all((a.get(k) if k in a else a2.get(k)) == v for k, v in kw.items()): return r['data']
    raise SystemExit(f'missing {tool} {kw}')
data = lambda x: x.get('data', x) if isinstance(x, dict) else x
r1 = lambda v, d=1: None if v is None else round(v, d)
def st(idx): return [x.split('=') for x in data(find('sorftime-mcp', 'category_trend', node_id=NODE, trend_index=idx))]
TPL = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="use-iframe" content="true"><meta name="html-box-height-mode" content="auto"><meta name="description" content="{desc}"><title>{title}</title>
<style>body{{margin:0;background:#fcfcfb;color:#0b0b0b;font:13px -apple-system,PingFang SC,Hiragino Sans GB,sans-serif}}#mc{{width:100%;max-width:100%;box-sizing:border-box;padding:10px 12px}}
.mc-h{{font-size:15px;font-weight:600;margin:2px 0 6px}}.mc-title{{font-size:13px;font-weight:600;color:#3a3936;margin:12px 0 2px}}
.mc-legend{{display:flex;flex-wrap:wrap;gap:6px 16px;justify-content:center;font-size:12px;color:#3a3936;margin:2px 0 6px}}.mc-legend i{{display:inline-block;width:12px;height:10px;border-radius:2px;margin-right:5px;vertical-align:middle}}
.mc-src{{font-size:11px;color:#7a7973;margin-top:8px}}</style></head><body><div id="mc"></div>
<script>{js}</script><script>MiniChart.render({spec});</script></body></html>'''
def write(n, spec):
    html = TPL.format(desc=spec['title'], title=spec['title'], js=JS, spec=json.dumps(spec, ensure_ascii=False))
    open(f'{OUT}/fig{n}.html', 'w').write(html); return len(html)
def ym(s): return s[2:7]
sizes = {}

# fig1
ms = data(find('xydc-mcp', 'get_category_market_size_trends', categoryId=CAT))['trends']
lb = [ym(t['localDate']) for t in ms]
s1 = st('SalesCount')
sizes[1] = write(1, {'title': '图1 首饰盒大盘月销量与销售额', 'source': '西柚、Sorftime（采集日期 2026-10-26）', 'panels': [
  {'title': '西柚 首饰盒类目 月销量（件）', 'type': 'bar', 'categories': lb, 'series': [{'name': '月销量', 'values': [t['sales']['value'] for t in ms], 'unit': ' 件', 'decimals': 0, 'color': C[0]}]},
  {'title': '西柚 首饰盒类目 月销售额（美元）', 'type': 'bar', 'categories': lb, 'series': [{'name': '月销售额', 'values': [round(float(t['salesRevenue']['value'])) for t in ms], 'unit': '', 'decimals': 0, 'color': C[1]}], 'unit': ''},
  {'title': 'Sorftime 节点 16350291 Top100 月销量（件；含旅行包/戒指盒；2026-10 截至 26 日）', 'type': 'bar', 'categories': [a[2:] for a, b in s1], 'series': [{'name': 'Top100 月销量', 'values': [int(b) for a, b in s1], 'decimals': 0, 'unit': ' 件', 'color': C[2]}]}]})

# fig2
se = data(find('xydc-mcp', 'get_category_seasonality', categoryId=CAT))['monthInfos']
col = {'peak': C[1], 'shoulder': C[3], 'off': C[0]}; nm = {'peak': '旺季', 'shoulder': '次旺/过渡', 'off': '平淡季'}
sizes[2] = write(2, {'title': '图2 首饰盒 1–12 月销量季节系数（1.0 = 全年月均）', 'source': '西柚（采集日期 2026-10-26）', 'panels': [
  {'title': '季节系数', 'type': 'bar', 'labels': True, 'unit': '', 'categories': [f"{m['month']}月" for m in se],
   'series': [{'name': '季节系数', 'values': [round(float(m['monthlySalesMultiplier']), 2) for m in se], 'decimals': 2, 'colors': [col[m['seasonType']] for m in se],
               'tipText': [f"{float(m['monthlySalesMultiplier']):.2f}（{nm[m['seasonType']]}）" for m in se]}],
   'legend': [{'name': nm[k], 'color': col[k]} for k in ('peak', 'shoulder', 'off')]}]})

# fig3
cur = data(find('xydc-mcp', 'get_keyword_aba_trends', start_week='2025-10-26'))['entities']
prv = {e['searchTerm']: e['trends'] for e in data(find('xydc-mcp', 'get_keyword_aba_trends', start_week='2024-10-27'))['entities']}
def monthly(tr):
    m = collections.OrderedDict()
    for t in tr: k = t['reportFromDate'][:7]; m[k] = m.get(k, 0) + (t['weeklySearchVolume'] or 0)
    ks = list(m)[1:-1]; return ks, [m[k] for k in ks]
others = []; jb = None
for e in cur:
    ks, vs = monthly(prv.get(e['searchTerm'], []) + e['trends'])
    if e['searchTerm'] == 'jewelry box': jb = (ks, vs)
    else: others.append({'name': e['searchTerm'], 'values': vs, 'decimals': 0, 'kind': 'line'})
for i, o in enumerate(others): o['color'] = C[(i + 1) % 8]
g = data(find('sellersprite-mcp', 'google_trend', keyword='jewelry box'))['items']
gl = [datetime.datetime.utcfromtimestamp(i['time']/1000).strftime('%y-%m') for i in g]; gv = [i['value'] for i in g]
sizes[3] = write(3, {'title': '图3 核心词站内月搜索量与 Google 热度', 'source': '西柚、卖家精灵（采集日期 2026-10-26）', 'panels': [
  {'title': '“jewelry box” ABA 月搜索量（按周汇总，首尾不完整月已去掉）', 'type': 'line', 'categories': [k[2:] for k in jb[0]], 'unit': ' 次', 'series': [{'name': 'jewelry box', 'values': jb[1], 'decimals': 0, 'color': C[0]}]},
  {'title': '其他 7 个核心词 ABA 月搜索量', 'type': 'line', 'categories': [k[2:] for k in jb[0]], 'unit': ' 次', 'series': others},
  {'title': 'Google Trends “jewelry box” 美国热度，近 5 年（0–100）', 'type': 'line', 'categories': gl, 'unit': '', 'ymax': 100, 'series': [{'name': '热度', 'values': gv, 'decimals': 0, 'color': C[2]}]},
  {'title': 'Google Trends “jewelry box” 近 24 个月逐月热度', 'type': 'line', 'labels': True, 'categories': gl[-24:], 'unit': '', 'ymax': 100, 'rotate': True, 'series': [{'name': '热度', 'values': gv[-24:], 'decimals': 0, 'color': C[2]}]}]})

# fig4 brands with ASIN
br = data(find('xydc-mcp', 'get_category_brand_market_size', categoryId=CAT))['list']
asin = {}
def add(b, a, s):
    if b and (b.lower() not in asin or s > asin[b.lower()][1]): asin[b.lower()] = (a, s)
for r in REC:
    if (r['tool'] == 'get_category_sales_ranking' and r['args'].get('categoryId') == CAT) or r['tool'] == 'brand_top_asin':
        for x in data(r['data'])['list']: add(x['asinInfo']['brand'], x['asinInfo']['primaryAsin'], x['metrics']['sales']['value'] or 0)
    if r['tool'] == 'get_category_new_release_opportunity_trends' and r['args'].get('categoryId') == CAT:
        for x in data(r['data'])['list']: add(x.get('brand'), x['primaryAsin'], 0)
def aof(b): return '多个无品牌商品' if b.lower() == 'generic' else asin.get(b.lower(), ('?',))[0]
t3 = st('Top3BrandSalesAmountShare')
sizes[4] = write(4, {'title': '图4 品牌份额（含代表 ASIN）与头部集中度', 'source': '西柚、Sorftime（采集日期 2026-10-26）', 'panels': [
  {'title': '西柚 Top20 品牌近 30 天销量份额（品牌｜代表 ASIN｜加权均价）', 'type': 'hbar', 'labels': True, 'unit': '%', 'labelWidth': 270,
   'categories': [f"{b['brand']}  {aof(b['brand'])}  ${float(b['priceDistribution']['weightedAvg']):.0f}" for b in br],
   'series': [{'name': '销量份额', 'values': [r1(float(b['sales']['ratio'])*100) for b in br], 'decimals': 1, 'color': C[0]},
              {'name': '近 30 天销量', 'kind': 'none', 'values': [b['sales']['metrics']['value'] for b in br], 'decimals': 0, 'unit': ' 件'}],
   'extra': [f"星级 {float(b['avgStars']):.2f}，平均评论 {b['avgRatings']}" for b in br]},
  {'title': 'Sorftime 节点 Top100：Top3 品牌销售额占比（%）', 'type': 'line', 'labels': True, 'unit': '%', 'ymax': 40, 'categories': [a[2:] for a, b in t3], 'series': [{'name': 'Top3 品牌销售额占比', 'values': [float(b) for a, b in t3], 'decimals': 1, 'color': C[1]}]}]})

def bar_line(title, cats, bars, line, bar_name, line_name, unit='%'):
    return {'title': title, 'type': 'bar', 'labels': True, 'unit': unit, 'categories': cats,
            'series': [{'name': bar_name, 'values': [r1(v) for v in bars], 'color': C[0]}, {'name': line_name, 'kind': 'line', 'values': [r1(v) for v in line], 'color': C[1]}]}
# fig5
cn = data(find('sellersprite-mcp', 'market_seller_country_distribution', month='202609'))
ty = data(find('sellersprite-mcp', 'market_seller_type_concentration', month='202609'))
sizes[5] = write(5, {'title': '图5 卖家所属地与配送方式（节点 Top100）', 'source': '卖家精灵（节点 Top100，2026-09）', 'panels': [
  bar_line('卖家所属地', [x['label'] for x in cn], [x['products'] for x in cn], [x['unitsRatio']*100 for x in cn], '商品数占比', '销量占比'),
  bar_line('配送方式', [{'NA': 'FBM/其他', 'FBA': 'FBA', 'Amazon自营': '亚马逊自营'}.get(x['label'], x['label']) for x in ty], [x['asinRatio']*100 for x in ty], [x['unitsRatio']*100 for x in ty], '商品数占比', '销量占比')]})
# fig6
ld = data(find('sellersprite-mcp', 'market_listing_date_distribution', month='202609'))
nr = data(find('xydc-mcp', 'get_category_new_release_opportunity_trends', categoryId=CAT))['trends']
p6 = bar_line('卖家精灵 节点 Top100 上架时间分布（2026-09）', ['≤'+x['label'] if x['label'] != '3年以上' else x['label'] for x in ld], [x['products'] for x in ld], [x['unitsRatio']*100 for x in ld], '商品数（个，即 %）', '销量占比')
sizes[6] = write(6, {'title': '图6 上架时间分布与新品销量占比', 'source': '卖家精灵、西柚（采集日期 2026-10-26）', 'panels': [p6,
  {'title': '西柚 首饰盒类目 新品销量占比（%）', 'type': 'line', 'unit': '%', 'categories': [ym(t['localDate']) for t in nr],
   'series': [{'name': '新品销量占比', 'values': [r1(float(t['newRelease']['sales']['ratio'])*100) for t in nr], 'color': C[2]},
              {'name': '新品销量', 'kind': 'none', 'values': [t['newRelease']['sales']['value'] for t in nr], 'decimals': 0, 'unit': ' 件'},
              {'name': '新品 ASIN 数', 'kind': 'none', 'values': [t['newRelease']['asinCount']['value'] for t in nr], 'decimals': 0, 'unit': ''}]}]})
# fig7
sr = data(find('xydc-mcp', 'get_category_sales_ranking', categoryId=CAT, pageSize=10))['list']
cats = [f"{r['asinInfo']['brand']}\n{r['asinInfo']['primaryAsin']}" for r in sr]
new = [r['asinInfo']['streetDate'] >= '2025-10-01' for r in sr]
yo = [r['metrics']['sales']['yoy']['rate'] for r in sr]
ext = [f"上架 {r['asinInfo']['streetDate']}｜均价 ${r['asinInfo']['priceDistribution']['value']}｜评论 {r['asinInfo']['ratings']}" for r in sr]
sizes[7] = write(7, {'title': '图7 $25–60 对标段 Top10：近 30 天销量与同比', 'source': '西柚（采集日期 2026-10-26）', 'panels': [
  {'title': '近 30 天销量（件）', 'type': 'bar', 'labels': True, 'unit': '', 'height': 300, 'categories': cats, 'extra': ext,
   'series': [{'name': '近 30 天销量', 'values': [r['metrics']['sales']['value'] for r in sr], 'decimals': 0, 'unit': ' 件', 'colors': [C[1] if n else C[0] for n in new]}],
   'legend': [{'name': '上架 ≥1 年', 'color': C[0]}, {'name': '上架 <1 年（新品）', 'color': C[1]}]},
  {'title': '近 30 天销量同比（%）', 'type': 'bar', 'labels': True, 'unit': '%', 'height': 300, 'categories': cats, 'extra': ext,
   'series': [{'name': '同比', 'values': [r1(float(v)*100, 1) if v is not None else None for v in yo], 'decimals': 1, 'colors': [C[2] if (v and float(v) > 0) else C[7] for v in yo],
               'tipText': ['无去年数据' if v is None else f'{float(v)*100:+.1f}%' for v in yo], 'labelText': ['' if v is None else f'{float(v)*100:+.0f}%' for v in yo]}]}]})
# fig8
pr = {x['priceType']: x for x in data(find('xydc-mcp', 'get_category_price_segment_trends', categoryId=CAT))['priceDistribution']}
nmap = {'lowPrice': '低价带 <$29', 'midPrice': '中价带 $29–65', 'highPrice': '高价带 >$65'}
lb = [ym(y['localDate']) for y in pr['lowPrice']['trends']]
S = {t: [(y['sales']['value'] or 0) for y in x['trends']] for t, x in pr.items()}
tot = [sum(S[t][i] for t in S) for i in range(len(lb))]
ap = st('AvgPrice')
sizes[8] = write(8, {'title': '图8 三档价格带月销量、销量占比与均价', 'source': '西柚、Sorftime（采集日期 2026-10-26）', 'panels': [
  {'title': '西柚 三档价格带 月销量（件，堆叠）', 'type': 'stack', 'unit': ' 件', 'categories': lb, 'series': [{'name': nmap[t], 'values': S[t], 'decimals': 0, 'color': C[k]} for k, t in enumerate(pr)]},
  {'title': '西柚 三档价格带 销量占比（%）', 'type': 'line', 'unit': '%', 'ymax': 80, 'categories': lb, 'series': [{'name': nmap[t], 'values': [r1(S[t][i]/tot[i]*100) for i in range(len(lb))], 'color': C[k]} for k, t in enumerate(pr)]},
  {'title': 'Sorftime 节点 Top100 均价（美元，含低价旅行包等）', 'type': 'line', 'unit': '', 'ymin': 0, 'categories': [a[2:] for a, b in ap], 'series': [{'name': '均价', 'values': [float(b) for a, b in ap], 'decimals': 2, 'unit': ' 美元', 'color': C[3]}]}]})
# fig9
segs = []
for t in ('lowPrice', 'midPrice', 'highPrice'):
    r = float(pr[t]['sales']['recent']['ratio'])
    for d in pr[t]['priceDetails']:
        if t == 'highPrice': segs.append((f"${float(d['min']):.0f}+", r*100, pr[t]['sales']['recent']['current'])); break
        segs.append((f"${float(d['min']):.0f}–{float(d['max']):.0f}", float(d['sales']['ratio'])*r*100, d['sales']['value']))
pdist = data(find('sellersprite-mcp', 'market_price_distribution', month='202609'))
sizes[9] = write(9, {'title': '图9 两家价格分布对照：西柚首饰盒类目 vs 卖家精灵节点 Top100', 'source': '西柚、卖家精灵（采集日期 2026-10-26）', 'panels': [
  {'title': '西柚 首饰盒类目（596 个主商品，只含桌面首饰盒）各价格段销量占比（近 30 天）', 'type': 'line', 'unit': '%', 'rotate': True, 'categories': [s[0] for s in segs],
   'series': [{'name': '销量占比', 'values': [r1(s[1]) for s in segs], 'color': C[1]}, {'name': '近 30 天销量', 'kind': 'none', 'values': [s[2] for s in segs], 'decimals': 0, 'unit': ' 件'}]},
  bar_line('卖家精灵 节点 16350291 销量 Top100（69 个为旅行包/戒指盒/礼品袋）价格段分布', ['$'+x['label'] for x in pdist], [x['products'] for x in pdist], [x['unitsRatio']*100 for x in pdist], '商品数（个，即 %）', '销量占比')]})
# fig10
rv = data(find('xydc-mcp', 'get_category_review_analysis', categoryId=CAT))['ratingsTrends']
ar = st('AvgRatingCount')
sizes[10] = write(10, {'title': '图10 评论数门槛', 'source': '西柚、Sorftime（采集日期 2026-10-26）', 'panels': [
  bar_line('西柚 按评论数分层（近 30 天）', [f"{x['ratings']['min']}–{x['ratings']['max']}" if x['ratings']['max'] is not None else f"{x['ratings']['min']}+" for x in rv],
           [float(x['primaryAsinCount']['ratio'])*100 for x in rv], [float(x['sales']['ratio'])*100 for x in rv], '商品数占比', '销量占比'),
  {'title': 'Sorftime 节点 Top100 平均评论数（条）', 'type': 'line', 'unit': ' 条', 'categories': [a[2:] for a, b in ar], 'series': [{'name': '平均评论数', 'values': [round(float(b)) for a, b in ar], 'decimals': 0, 'color': C[2]}]}]})
# fig11
eb = {x['label']: x for x in data(find('sellersprite-mcp', 'market_ebc_distribution', month='202609'))}
cats = ['有A+有视频', '有A+无视频', '无A+有视频', '无A+无视频']
sizes[11] = write(11, {'title': '图11 A+ 与主图视频覆盖（节点 Top100）', 'source': '卖家精灵（节点 Top100，2026-09）', 'panels': [
  bar_line(ttl, cats, [eb.get(pre+c, {}).get('productsRatio', 0) for c in cats], [eb.get(pre+c, {}).get('unitsRatio', 0) for c in cats], '商品数占比', '销量占比')
  for pre, ttl in (('', '节点 Top100 全部商品'), ('新品', '节点 Top100 中的新品'))]})
# fig12
kw = data(find('xydc-mcp', 'get_category_keywords', categoryId=CAT))['list'][:15]
cats = [k['searchTerm'] for k in kw]
cpc = lambda c: (c.get('value') if isinstance(c, dict) else c)
ext = [f"ABA 排名 {k['searchFrequencyRank']}｜竞争难度 {k['searchTermCompetitiveDifficulty']}｜CPC ${cpc(k['cpc'])}" for k in kw]
sizes[12] = write(12, {'title': '图12 Top15 流量词：月搜索量与点击转化率', 'source': '西柚（采集日期 2026-10-26）', 'panels': [
  {'title': '月搜索量（次）', 'type': 'bar', 'labels': True, 'unit': '', 'rotate': True, 'categories': cats, 'extra': ext, 'series': [{'name': '月搜索量', 'values': [int(k['searchVolume']) for k in kw], 'decimals': 0, 'unit': ' 次', 'color': C[0]}]},
  {'title': '点击转化率（%）', 'type': 'bar', 'labels': True, 'unit': '%', 'rotate': True, 'categories': cats, 'extra': ext,
   'series': [{'name': '点击转化率', 'values': [r1(float(k['adjustedClickConversionRate'])*100) if k['adjustedClickConversionRate'] else None for k in kw], 'color': C[2]}]}]})
# fig13
tf = data(find('xydc-mcp', 'get_asin_traffic'))['entities']
bmap = {}
for r in REC:
    if r['tool'] == 'brand_top_asin' or (r['tool'] == 'get_category_sales_ranking' and r['args'].get('categoryId') == CAT):
        for x in data(r['data'])['list']: bmap[x['asinInfo']['primaryAsin']] = x['asinInfo']['brand']
ads = [r['data'] for r in REC if r['tool'] == 'get_parent_asin_ad_overview' and r['server'] == 'xydc-mcp']
seg = ['organic', 'sp', 'sb', 'sbv']; sn = {'organic': '自然', 'sp': 'SP', 'sb': 'SB', 'sbv': 'SBV'}
sizes[13] = write(13, {'title': '图13 对标竞品流量结构', 'source': '西柚（采集日期 2026-10-26）', 'panels': [
  {'title': '10 款对标竞品 近 7 天流量结构（%）', 'type': 'stack', 'unit': '%', 'ymax': 100, 'categories': [f"{bmap.get(e['asin'], '?')}\n{e['asin']}" for e in tf],
   'extra': [f"流量总分 {e['totalTrafficScore']:,}｜自然词 {e['organicSearchTermCount']}｜广告词 {e['advertisingSearchTermCount']}" for e in tf],
   'series': [{'name': '自然流量', 'values': [r1(e['organicTrafficScoreRatio']*100) for e in tf], 'color': C[0]}, {'name': '广告流量', 'values': [r1(e['advertisingTrafficScoreRatio']*100) for e in tf], 'color': C[1]}]},
  {'title': '5 个父体 流量来源结构（%，近 7 天）', 'type': 'stack', 'unit': '%', 'ymax': 100, 'categories': [f"{bmap.get(data(d)['scope']['inputAsin'], '?')}\n{data(d)['scope']['inputAsin']}" for d in ads],
   'extra': [f"变体 {data(d)['scope']['includedVariationCount']}｜活动 {data(d)['campaignCount']}｜广告词 {data(d)['keywordCount']}" for d in ads],
   'series': [{'name': sn[s], 'values': [r1(next((x['shareOfTotalScore'] for x in data(d)['trafficScoreDistribution'] if x['source'] == s), 0)*100) for d in ads], 'color': C[k]} for k, s in enumerate(seg)]}]})
# fig14
rows = list(csv.DictReader(open(D + '/差评打标-96条.csv', encoding='utf-8-sig')))
cnt = collections.Counter(t for r in rows for t in r['标签'].split('；') if t).most_common(); n = len(rows)
sizes[14] = write(14, {'title': f'图14 {n} 条差评问题标签频次（6 款 $26–53 竞品，近一年 1–3 星）', 'source': 'Sorftime（评论），Gemini Flash 打标、Claude 抽查', 'panels': [
  {'title': '标签提及次数（一条差评可多标）', 'type': 'hbar', 'labels': True, 'unit': '', 'labelWidth': 190, 'categories': [k for k, v in cnt],
   'series': [{'name': '提及次数', 'values': [v for k, v in cnt], 'decimals': 0, 'color': C[7], 'labelText': [f'{v} 次（{v/n:.0%}）' for k, v in cnt], 'tipText': [f'{v} 次，占 {v/n:.1%}' for k, v in cnt]}]}]})
print({k: f'{v/1024:.0f}KB' for k, v in sizes.items()})
