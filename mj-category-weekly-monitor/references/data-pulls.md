# 拉数清单与花费

批量调用一律用 `make_calls.py` 生成清单，再用 batch-offload 的 `oc_pull.sh` 交给 DeepSeek 执行：
```bash
python3 SKILL/scripts/make_calls.py STAGE --config CFG --out RUN/STAGE.txt --date RUN_DATE --task "<用户原话>" [--asins FILE] [--month YYYY-MM]
~/.claude/skills/batch-offload/scripts/oc_pull.sh RUN/STAGE.txt RUN/STAGE
```
看统计四项（errors / missing_lines / unexpected_calls / unrecognized）。`unexpected_calls` 常是同参数重复调用，无害；参数被改过的要重跑。
西柚工具的 `user_task` 填用户这次的原话（脱敏 sheet token），`--task` 传进去即可。

| 阶段 | 频率 | 调用 | 约花费 |
|---|---|---|---|
| snapshot | 每周 | 卖家精灵 product_research 当前数据（不填 month）5 页 × 100（variation=Y，带 imageUrl、availableDate） | 免费 |
| daily | 每周 | 每个跟踪/上升 ASIN 5 个西柚工具（info/bsr/traffic/ad_change/keyword），兄弟链接只拉 info | 18 个 ASIN ≈ 440 Credits |
| riser_bsr | 每周 | 候选 ASIN 的西柚每日 BSR（42 天，快速/渐进/回升判断都要用） | 每个约 4 Credits；首周约 75 个，之后通常十几个 |
| new_listing | 每周 | 卖家精灵 product_research 当前数据、按上架时间倒序 2 页 × 100 | 免费 |
| riser_extra | 有新上升商品时 | get_asin_info（一次多个 ASIN）+ info_change_trends | 少量 |
| sales_rank | 每月 | 西柚类目销量榜前 30 | 30 Credits |
| market_ss | 每月 | 卖家精灵 market_research_statistics 24 个月 | 免费 |
| market_xy | 每月 | 西柚 market_size_trends + category_keywords | 约 33 Credits |

自己直接调（1~2 次、返回很小）：
- Sorftime `category_trend`（SalesCount、AvgPrice）各一次 → 存成 `RUN/sorftime.json`：`{"SalesCount": data, "AvgPrice": data}`
- 卖家精灵 `market_product_demand_trend`（glance views）→ 存 `RUN/glance.json`（items 列表）
- 主图缺失时：卖家精灵 `product_research`（includeBrands=缺图品牌，returnFields=asin,imageUrl）→ `{asin:url}` 传给 fetch_images.py --map

## 西柚类目资源
类目级工具（销量榜、市场规模、关键词）需要 `resourceId`。`generate_category_insight_resource` 每次 500 Credits，
资源的 `reportEndDate` 覆盖到上月底就继续复用 config 里的；新的月份数据需要时（例如月初要上个月的销量榜而 reportEndDate 还停在上上月），
先问用户再重新生成，并把新的 resourceId、report 日期写回 config。ASIN 级日度工具不需要 resourceId。

## DeepSeek 额度用完时
opencode 免费额度用完会返回 `FreeUsageLimitError`（429，约 17 小时后恢复），oc_pull 的统计是 `calls: 0`、所有行都在 missing_lines。
改用 agy：同样的清单发给 agy（只调清单里的工具、按顺序、回复“完成”），原始返回在 `~/.gemini/antigravity-cli/brain/<conversation_id>/.system_generated/steps/<n>/output.txt`，
按顺序对上清单行、核对 asin，写成 `OUT/raw/index.json`（字段 file/server/tool/args/bytes/error），后面的脚本就能直接用。
这一步已写成脚本：`python3 SKILL/scripts/agy_pull.py CALLS.txt OUT_DIR`（打印 calls/errors/problems/credits，problems 为空才算完整）。

## 常见报错
- 卖家精灵 `Unexpected token '<', "<!DOCTYPE"`：接口偶发错误，单独重跑这几行；还不行就自己直接调，把 data 存成 `SS_DIR/fix_YYYYMM.json`。
- 西柚 `get_asin_info` 参数是 `asins`（数组），不是 `asin`。
- 返回很大的单次调用（销量榜、关键词）也交给 oc_pull，不要直接读进上下文。
- lark-cli 只能读当前目录、/tmp、~/files 下的文件：write_tab.py 已在图片目录里执行嵌图命令。

## 2026-11-02 补充
- DeepSeek 失败、改由 agy 补拉时，数据在 `OUT/retry/raw/`（再补一次是 `retry2/`）。`build_monthly.py`、`pick_top.py`、`fetch_images.py`、`riser_scan.py supplement` 已改成读 `OUT` 下所有子目录的 `raw/`，不用手工合并。
- 西柚类目资源：`reportEndDate` = 生成日前一天（10-20 生成的只到 10-19）。月初要上个月完整数据就得重新生成；11-02 生成的覆盖到 10-31。config 里另存了 `resource_end_date`。
- 西柚月度销量榜偶尔整组返回空值（EASEGO 2026-04/06/10、WAYTULES 2026-10），这些组会从销量榜消失。`pick_top.py` 现在保留“当月缺数、但卖家精灵小类仍在前 50”的老成员，按上月组销量排序；同一变体组只是换了最畅销子体的，沿用原来跟踪的子体。
- config `exclude_asins`：节点里有、但不是同类竞品的变体组（如地垫小类里的 Yes4All 仰卧起坐垫 B073VCMBSZ），月度选名单时跳过。
