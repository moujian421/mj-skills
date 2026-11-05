# 拉数清单（参数已实测，2026-10-26；2026-11-03 更新分页上限）

> 2026-11-03：领星搜索词、投放词报表的 `length` 上限改成 **200**（传 500 会报 code 102“工具参数定义已更新”），要翻页（page 1、2…）。活动报表 length 200 可用。
> 领星同一工具并发有上限（429“并发已达上限”）：清单里同一工具别塞太多行，失败的单批补拉。
> DeepSeek 免费额度用完时改用 `cb_pull.sh`（hy3）。hy3 遇到大返回会存成文件，脚本把这些行记进 errors；raw/*.txt 里有 `/Users/cathug/.codebuddy/...txt` 路径，直接复制成 .json 就是完整返回。

领星都通过 `lingxing-mcp` 的 `action(toolId, params)` 调用。返回通常很大（50 万到 100 万字符），一定要落盘再用 Python 读。
profile_ids 用 `ad_auth_shops` 拿；店铺 sid 用于商品表现（例：AIRHOP-US = 9515）。

## A 组：商品层面（每次必拉）

```
lingxing query_product_performance_asin_lists
  {"offset":0,"length":50,"start_date":"<基准第一周周一>","end_date":"<最新周周日>",
   "date_view_type":"week","date_view_order_type":2,"search_field":"asin",
   "search_value":[<ASIN...>],"sids":"<sid>","currency_code":"USD","summary_field":"asin"}
```
返回在 `data.data.list`，每个 ASIN 每周一行（字段 `rweek`）。常用字段：sessions_total、cvr、order_items、volume、nature_order_items、ad_order_quantity、amount、promotion_order_items、promotion_discount、buy_box_percentage、spend、ad_sales_amount、acos、tacos、cpc、cate_rank、afn_fulfillable_quantity、available_days、avg_star、reviews_count、predict_gross_margin。

西柚（每个主力 ASIN）：
- `get_asin_info_trends` {asin, country, start_date, end_date}：每日价格、优惠券、Deal（4 Credits）
- `get_asin_info_change_trends`：标题、主图变化（4 Credits）
- `get_asin_traffic_trends_weekly` {asin, country, start_week, end_week}：只到上上周（1 Credit）
- `get_asin_bsr_trends`
西柚数据一般只到前一天，周流量只到上一个完整周之前。

## B 组：广告整体

```
lingxing ad_campaign_report
  {"report_date":"YYYY-MM-DD - YYYY-MM-DD","profile_ids":[...],"page":1,"length":200,
   "sort_field":"spends","sort_type":"desc","name":"<产品代码>"}      # 按名字筛
  或 "portfolio_id":"<组合ID>"                                           # 按组合筛（字符串，一次一个）
```
第一行是汇总行。`search_text` 不起筛选作用，要用 `name`。
字段：campaign_id、name、ads_type(sp/sb2/sd)、state、portfolio_name/portfolio_id、bidding_type、placement_top、top_of_search_impression_share、daily_budget、serving_status、is_apply_time（分时策略）。

```
lingxing ad_campaign_product_report
  {"report_date":...,"profile_id":<int>,"portfolio_id":[...],"length":100,"sort_field":"spends","sort_type":"desc"}
```
核对实际推的 ASIN/SKU 和标价（listing_price）。

## C 组：活动明细

```
lingxing ad_campaign_report  按 portfolio_id，report_date 分别取近 30 天、近 60 天（暂停/否定判断必用）
lingxing ad_campaign_search_term_report {"report_date":"<60天>","profile_ids":[...],"campaign_id":"<id>","search_type":"query","search_text":"<候选词>","page":1,"length":50,...}   # 否词、收词前复核单个词 60–90 天表现
lingxing get_sp_ad_placement_hour_data  # 需要降价的 SP 活动，按天拉后汇总三大广告位的点击、订单、花费（参数先用 search 看 schema）
```

```
lingxing ad_campaign_keyword_report    {"report_date","profile_ids","portfolio_id":[...],"page":1,"length":500,"sort_field":"spends","sort_type":"desc"}
lingxing ad_campaign_targeting_report  {同上, "length":"200", "with_ring":0}
lingxing ad_campaign_search_term_report {"report_date","profile_ids","campaign_id":"<id>","page":1,"length":200,"sort_field":"spends","sort_type":"desc"}   # 每个活动一次，14 天
lingxing ad_campaign_search_term_report {"report_date","profile_ids","portfolio_id":[...],"group_type":"query","page":1,"length":500,...}            # 按组合聚合，每周一次，丢单词分析用
lingxing get_sp_campaign_hour_data     {"campaign_ids":[<int>...最多50],"report_date":"YYYY-MM-DD"}   # 每天一次
  # 重开前逐日复核：每天一行，近 60 天约 60 次调用，交给 cb_pull/oc_pull；并发 20 会撞 429，失败的那几天单批重拉。没有按天的活动报表，只能用它
```
投放词字段：keyword_id、keyword_text、match_type、bid、state、campaign_id。投放 ASIN 字段：target_id、targeting_text、bid、asin_price。

## D 组：三方关键词与竞品（只对丢单词和前 5 核心词）

- `get_keyword_aba_trends` {keywords:[≤100], country, start_week, end_week}：**最多 52 周**，超过会报错
- `get_asin_keyword_rank_trends` {asin, keyword, country, start_date, end_date}：自然位、SP、SB、SBV 每日排名（7 Credits）
- `get_keyword_asin_analysis` {keyword, country, page_size:15–20}：近 7 天竞争 ASIN 的价格、排名、自然和广告流量及增速（1 Credit）
  否词复核（rules.md §4c）：每个要否的词调 1 次；再对 1–3 个同价位前排竞品调 `get_asin_info_trends`，默认 30 天（2026-11-03 实测 90 天 = 9 Credits/个）
- 需要看某天谁在打广告时：`get_keyword_advertising_replay` {keyword, country, report_date}

## 领星写入（只在用户确认后，Claude 自己调）

- `advertising_add_negative_keywords`：SP 否定关键词（活动或广告组层级）
- `advertising_add_negative_targets`：SP 否定 ASIN
- `advertising_sp_add_keywords`：SP 加关键词
- 没有改出价、改广告位、暂停活动、改预算的写入工具，这些交给用户手动改

## 分流

- `oc_pull.sh CALLS OUT` 生成的 raw 文件和 `index.json` 的 args 对应。用 index 里的参数找文件，不要假定顺序。
- DeepSeek 免费额度用完时返回 `FreeUsageLimitError`（`retryAfterMs` 约 17 小时）。
- agy 能不能调某个 MCP，看 `~/.gemini/config/config.json` 里 `userSettings.globalPermissionGrants.allow`。2026-10-26 起放行了 `mcp(xydc-mcp/*)`、`mcp(sellersprite-mcp/*)`、`mcp(sorftime-mcp/*)`、`mcp(lingxing-mcp/*)`。领星 Key 已由用户更新并实测可用（2026-10-26）。如果再返回 code 102“MCP Key无效或已失效”，请用户在领星重新生成 Key 后自己运行 `agy mcp add lingxing-mcp "<URL含新KEY>"`（Claude 不替用户填凭证）。
  用脚本：`python3 SKILL/scripts/agy_pull.py CALLS.txt OUT --batch 12 --parallel 4`，缺行用 `--only 37-48` 只补拉这些行（结果并入原 index.json）。
  已知坑：agy 偶尔把整批调用写成 `mcp_<server>_<tool>` 直接调用，全部报“invalid arguments”，却仍回复“完成”。脚本按参数逐条核对，会把它们列进 missing_lines，补拉即可。
  所以 DeepSeek 不通时，四家只读查询都可以交给 agy：指令里只要求逐个调用并回复“完成”，原始返回从 `~/.gemini/antigravity-cli/brain/<conversation_id>/.system_generated/steps/*/output.txt` 用 Python 读。领星写入一律不交给 agy。
  不要加 `--dangerously-skip-permissions`；`--mode auto` 对这个账号不可用。清单不要把领星和三方混在一批交给 agy。
