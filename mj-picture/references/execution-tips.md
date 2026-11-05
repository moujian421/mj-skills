# MJ-Picture 操作技巧

做 AH-GC1 图片需求时踩过的坑，下次直接照做。

## 飞书表（lark-cli sheets）

- **读表**：`lark-cli sheets +csv-get --spreadsheet-token <T> --sheet-id <id> --range A1:T30 -q '.data.annotated_csv'`。wiki 链接先用 `lark-cli wiki +node-get --node-token <URL>` 取 `obj_token` 作为 spreadsheet token。
- **批量写文字**：所有改动写进一个 JSON 数组，`+cells-set --writes @file.json` 一次提交（每项 `{sheet_id, range, cells}`，可跨 sheet）。不逐格调用。
- **嵌图片**：一个格子只能嵌一张图。用 `+cells-set-image --range P8 --image 本地文件`，每格调一次，会覆盖格子原有内容。
- **移动列**：`+dim-move --source-range P:R --target H` 会把嵌入图一起移走；目标位置落在表头合并格（如 B2:O2）中间时报 “Wrong Range”，先 `+cells-unmerge` 表头 1–5 行，移完再按新的最后一列 `+cells-merge`。
- **删掉格子里的嵌入图**：`+cells-clear --scope content` 删不掉图片，直接用 `+cells-set` 写一段文字（如“无（需另拍实景）”）覆盖。
- **插列**：`+dim-insert --position P --count 1 --inherit-style before`（插在 P 列前，继承左边列样式），再用 `+cols-resize` 设宽度。
- **数格子里有几张图**：`+cells-get --range O8:O16 -q '[.data.ranges[0].cells[][] | ((.rich_text//[]) | map(select(.type=="embed-image")) | length)]'`。
- **下载已嵌的图片**：先用 `+cells-get` 取 `rich_text[0].image_token`，再 `lark-cli api GET /open-apis/drive/v1/medias/<token>/download --output 文件名`。`drive +download` 对这种图片会返回 403。

## 抓亚马逊竞品图

用内置浏览器打开 `https://www.amazon.com/dp/<ASIN>`，在页面里跑 JS：

```js
(() => {
  const html = document.documentElement.innerHTML;
  const gallery = [...new Set([...html.matchAll(/"hiRes":"(https:[^"]+)"/g)].map(x => x[1]))];
  const aplus = [...new Set([...document.querySelectorAll('#aplus img, #aplus_feature_div img')]
    .map(i => i.getAttribute('data-src') || i.src).filter(s => s && s.includes('aplus-media')))];
  return {gallery, aplus};
})()
```

- `gallery` 是主图和副图原图（`_AC_SL1500_`），可能混有其他颜色的图，顺序不一定等于前台顺序。
- 用 `curl` 下载到 scratchpad，`sips -Z 360` 缩小后逐张看，确认和「竞品图片参考」记录的内容一致再用。
- A+ 对比表多是网页表格（`#aplus table`），没有现成图片：用 JS 取出表头图片地址和各行文字，重建成一个 HTML 页面，再用本机 Chrome 无头模式截图：

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --hide-scrollbars \
  --user-data-dir=<scratchpad>/prof --window-size=1464,820 --virtual-time-budget=8000 \
  --screenshot=<scratchpad>/cmp.png file://<scratchpad>/table.html
```

## 量文字宽度

字数接近上限时，用 Chrome 无头模式加 canvas `measureText` 量像素宽度：

```html
<script>
const c = document.createElement('canvas').getContext('2d');
const rows = [['bold 72px Arial', 'Hand Brake on the Handle'], ['48px Arial', 'Flip over to lock the right rear wheel']];
document.body.innerText = JSON.stringify(rows.map(([f, t]) => { c.font = f; return [t, Math.round(c.measureText(t).width)]; }));
</script>
```

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --user-data-dir=<scratchpad>/prof \
  --dump-dom file://<scratchpad>/measure.html | sed 's/<[^>]*>//g'
```

字号和像素上限见 copy-rules.md「字数上限」；一般用 scripts/brief_lint.py 直接量（Pillow + Arial），这里是备用方法。

## 拼图预览

没有 PIL 时，把多张缩略图写进一个 HTML（`<img>` 并排加文件名），用 Chrome 无头模式 `--screenshot` 截成一张，一次看完。

## 不开浏览器抓亚马逊（命令行 curl）

多个 agent 同时抓图时，内置浏览器只有一个，改用 curl（2026-10-23 验证可行）：

```bash
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'
curl -s -A "$UA" -H 'Accept-Language: en-US,en;q=0.9' --compressed 'https://www.amazon.com/s?k=<品牌+品类>' -o s.html
curl -s -A "$UA" -H 'Accept-Language: en-US,en;q=0.9' --compressed 'https://www.amazon.com/dp/<ASIN>' -o p.html
```

- **挑卖得好的样本**：优先用卖家精灵 MCP `competitor_lookup` 查月销量，一次调用就能拿到一个品牌的销量排行：
  `{"marketplace":"US","month":"<上个完整月 yyyyMM>","brand":"<品牌>","variation":"Y","order":{"field":"total_units","desc":true},"size":30,"returnFields":"asin,units,price,title,nodeLabelPath"}`
  `units` 是父体月销量，`nodeLabelPath` 用来分大类。当月数据常为空，用上个完整月。也可以传 `asins`（最多 40 个）核对已选样本。
  搜索页的 `bought in past month` 徽章只作参考：对新品会偏高，和卖家精灵对不上时以卖家精灵为准；卖家精灵没数据的款，写明“无数据”。
- **取图**：商品页里正则 `"hiRes":"https://m\.media-amazon\.com/images/I/([^"]+?)\._AC_SL1500_\.jpg"` 是副图原图；`id="aplus` 之后的 `aplus-media-library-service-media/` 地址里含 `1464,`、`970,`、`362,453`、`600,450` 的是 A+ 模块图。
- 有的商品图片地址不带 `_AC_` 前缀（如 `._SL1500_.jpg`），正则要放宽成 `\._(?:AC_)?SL1500_\.jpg`。
- 个别页面取不到图时，换同品类下一个热卖款。
- zsh 下通配符没有匹配会直接报错，循环文件时用 `ls 目录`。

## 抓手机端 A+（600×450）

- 手机端 Premium A+ 是单独一套图，电脑端页面里抓不到；curl 用手机 UA 会被亚马逊拦。
- 用内置浏览器：`resize_window` preset `mobile`（375×812，Android UA）→ navigate 商品页 → 在页面里跑：

```js
(()=>{const o=[];new Set([...document.querySelectorAll('img')].map(i=>i.getAttribute('data-src')||i.src)).forEach(s=>{const m=s&&s.match(/aplus-media-library-service-media\/([0-9a-f-]+)\.__CR0,0,(\d+,\d+)_PT0_SX600_V1___\.(\w+)/);if(m)o.push(m[1]+'|'+m[2]+'|'+m[3])});return location.pathname.slice(4)+' '+o.slice(0,14).join(' ')})()
```

- 每项 `uuid|宽,高|扩展名`，下载地址 `https://m.media-amazon.com/images/S/aplus-media-library-service-media/<uuid>.__CR0,0,<宽,高>_PT0_SX600_V1___.<扩展名>`。多个商品用 `browser_batch` 连着跑。
- 看图时拼图里每张设成宽 375px，模拟手机实际显示，才能判断字够不够大。
- 抓完 `resize_window` preset `desktop` 复原。
- 一次下载上百张会超过 2 分钟，用后台运行。
