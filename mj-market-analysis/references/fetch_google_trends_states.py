# Google Trends 美国各州热度（Interest by subregion）。用法: python3 -I fetch_google_trends_states.py <输出.json>；关键词和时间范围在脚本里改。每次只请求几次、间隔 3–4 秒，遇到 429 或人机验证就停，不要重试绕过。
import urllib.request, urllib.parse, json, http.cookiejar, time, sys
out = sys.argv[1]
cj = http.cookiejar.CookieJar(); op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36', 'Accept-Language': 'en-US,en;q=0.9'}
def get(url):
    r = op.open(urllib.request.Request(url, headers=UA), timeout=30); return r.read().decode('utf-8')
get('https://trends.google.com/trends/?geo=US'); time.sleep(3)
res = {}
for key, date in (('A_12m', 'today 12-m'), ('B_5y', 'today 5-y')):
    req = {'comparisonItem': [{'keyword': 'jewelry box', 'geo': 'US', 'time': date}], 'category': 0, 'property': ''}
    t = get('https://trends.google.com/trends/api/explore?hl=en-US&tz=0&req=' + urllib.parse.quote(json.dumps(req)))
    w = json.loads(t[t.index('{'):])['widgets']; geo = next(x for x in w if x['id'] == 'GEO_MAP'); time.sleep(3)
    t2 = get('https://trends.google.com/trends/api/widgetdata/comparedgeo?hl=en-US&tz=0&req=' + urllib.parse.quote(json.dumps(geo['request'])) + '&token=' + geo['token'])
    d = json.loads(t2[t2.index('{'):])['default']['geoMapData']
    res[key] = sorted([{'state': x['geoName'], 'code': x.get('geoCode'), 'value': x['value'][0]} for x in d if x.get('hasData', [True])[0]], key=lambda z: -z['value'])
    time.sleep(4)
json.dump(res, open(out, 'w'), ensure_ascii=False, indent=1)
for k, v in res.items(): print(k, len(v), v[:8])
