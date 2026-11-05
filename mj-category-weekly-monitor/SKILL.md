---
name: mj-category-weekly-monitor
description: 亚马逊类目竞品周度监控：按周记录头部 15 个变体组（西柚月销量排名、只取节点小类 BSR 前 50）的价格/Deal/Prime/广告/变体组拆分等运营动作和效果，排查头部以外小类排名明显稳定上升的商品（快速上升 🚀 / 渐进上升 📈）并复盘其打法（A/B 分级、重点标记），每月更新大盘月度和核心词月度，全部写入飞书表格（含主图、排版、回读核对）；另有每天自动跑的前 20 竞品降价监控和每周二自动跑的周度机械部分。用户说“日度监控/降价监控怎么样”“周度自动跑了没”“复盘待复盘的上升商品”“跑一下周度监控”“更新竞品周报”“竞对动作”“这周头部有什么动作”“排名上升的商品”“排查飙升/上升的竞品”“做一个 XX 类目的周度监控表”，或给出飞书监控表链接让继续更新、换一个类目照着做时，都应使用本 skill，即使没提“skill”二字。Weekly Amazon category competitor monitoring (actions, effects, rank risers, monthly market & keyword tabs) written to Feishu sheets.
---

# 类目竞品周度监控

## 自动运行与 Claude 的分工

脚本能做的都由系统定时器跑，不经过 Claude（安装：`bash SKILL/scripts/install_timers.sh`，要用户自己在终端运行）：

| 任务 | 时间 | 脚本 | 日志 |
|---|---|---|---|
| 日度降价监控 | 每天 10:00（推车 10:30，Exercise Mats 11:00） | `daily_run.sh <slug>` | `data/<slug>/daily_runs/<日期>/run.log` |
| 周度机械部分 | 每周二 08:00（推车 09:00，Exercise Mats 10:00） | `weekly_run.sh <slug>` | `data/<slug>/weekly_runs/<日期>/run.log` |

同一时间只跑一个（`pull_lib.sh` 里的锁）。同一周已经手动跑完的（比如周一提前跑了），周二的定时任务会自动跳过。**不要在 `weekly_run.sh` 正在运行时改它**（bash 边跑边读脚本，改了会错位）。`weekly_run.sh` 做第 2 步的 1~4、6~8（周度页签）和清空上周日度记录；
**不做**：新上升商品的复盘和录入 config（第 2 步第 5 条）、复盘页签、每月刷新。新上升商品写进 `weekly_runs/<日期>/pending_risers.json`，系统通知会提示“N 个待复盘”。

用户开会话说“看周度/复盘上升商品”时：读最新 `weekly_runs/<日期>/run.log` 和 `pending_risers.json`，`RUN` 就用这个目录，
从第 2 步第 5 条做起（拉 riser_extra、写复盘、录入 config），再重跑第 6~8 步把上升商品行和复盘页签写上。
当月第一次还要做第 1 步（通知会提示“需要做 YYYY-MM 月度刷新”）。

快照来源：卖家精灵优先；拉不到时用 Sorftime `category_products`（BestSeller 前 100）。Sorftime 快照只有前 100 名、每组通常 1 个子体，
和卖家精灵快照对比时初筛候选会偏多（实测 33 个，平时十几个），最终都由西柚 BSR 确认，只是多花些 Credits。

每天的小类排名（前 100）存在 `data/<slug>/daily_ranks/<日期>.json`。攒满 6 周后可以用它代替 `riser_bsr` 的西柚拉数（尚未改，届时改 `riser_scan.py confirm` 读这里）。

## 周度流程

每周跑一次（建议周二，上一周完整结束、西柚有了周日的数据后）。产出一张飞书表，五个页签：

| 页签 | 内容 | 更新 |
|---|---|---|
| 竞对动作-日度 | 小类前 20 组竞品里近 2 天有降价动作的：日期、小类排名、ASIN、品牌、产品、主图、动作（无效果列）；保留本周每天的记录 | 每天自动（见文末“日度降价监控”） |
| 竞对动作-周度 | 头部 15 组每周有动作的一行；排名上升商品只在发现那周列一行（🚀/📈 标记）：周次、周排名、ASIN、品牌、产品、主图、动作、效果 | 每周 |
| 排名上升-动作复盘 | 新发现的排名上升商品：动作时间线、效果、打法总结、A/B 分级（累积） | 每周 |
| 大盘月度 | 卖家精灵 / Sorftime / 西柚 24 个月销量、销售额 | 每月 |
| 核心词月度 | 西柚核心词 24 个月搜索量，按产品类型分组 | 每月 |

判定规则全在 `references/rules.md`（向用户解释口径时读它）；拉数清单和花费在 `references/data-pulls.md`；新类目在 `references/first-run.md`。

## 约定

- `SKILL` = 本 skill 目录；`CFG` = `SKILL/data/<类目slug>/config.json`；`IMG` = `SKILL/data/<slug>/images`；
  `RUN` = scratchpad 下新建的 `cwm/<slug>/<运行日期>/`；`DATE` = 今天（脚本按它找“上一个完整的周一到周日”）。
- 批量拉数走 batch-offload（`make_calls.py` 生成清单 → `oc_pull.sh`），不要自己逐个调；只调一两次、返回很小的自己调。
  西柚 `user_task` 填用户这次的原话（sheet token 脱敏）。收费步骤按 data-pulls.md 的估算先告诉用户。
- 脚本负责算数和排版，判断由你做：复盘文字、要不要录入某个上升商品、异常要不要向用户说明。
- 写飞书只用 `write_tab.py`（不用清空、删除这类需要 `--yes` 的命令），写完看它打印的核对结果。

## 第 0 步：找配置

`ls SKILL/data/`。用户说的类目已有配置就用它；没有就按 `references/first-run.md` 新建（要和用户确认类目）。
读 config 里的 `tracked`、`risers`、`sheet`、`rank_month`。

## 第 1 步：每月刷新（当月第一次运行时；`rank_month` 不是上个月才做）

1. 西柚资源是否覆盖上个月（看 config `xiyou.resource_report_date`，不够就问用户后重新生成，500 Credits）。
2. 拉 `sales_rank`，并先做第 2 步第 1 条拿到本周快照 `SNAP.json`（= `SKILL/data/<slug>/snapshots/DATE.json`）→
   `python3 SKILL/scripts/pick_top.py --config CFG --sales RUN/sales_rank --snapshot SNAP.json` 看名单；没问题加 `--write`。
   新进的 ASIN 要改中文短名、填核心词（按产品类型，见 config `keyword_by_type`）；掉出的告诉用户。不是同类竞品的加进 config `exclude_asins`。
   如果周度已经先跑了（名单是旧的），新进的 ASIN 要补拉 `daily --asins`（输出到周度 RUN 下的新子目录），再重跑第 2 步 6~8。
3. 大盘与核心词：拉 `market_ss`、`market_xy`；自己调 Sorftime `category_trend` 两次、卖家精灵 `market_product_demand_trend` 一次，存成 json（格式见 data-pulls.md）→
   `python3 SKILL/scripts/build_monthly.py --config CFG --run RUN --month 上月 --ss RUN/market_ss --xy RUN/market_xy --sorftime RUN/sorftime.json --glance RUN/glance.json --date DATE`
   脚本自动标出卖家精灵销量异常跳涨的月份（黄底）；你看一眼是否合理，必要时用 `--market-note` 补充说明。
   核心词缺失（关键词不再是高相关）时，换同组的词并更新 config。
4. `write_tab.py` 写 `RUN/spec_market.json`、`RUN/spec_keywords.json`。

## 第 2 步：每周流程

1. **快照**：拉 `snapshot` → `python3 SKILL/scripts/snapshot.py --config CFG --pull RUN/snapshot --date DATE --save SKILL/data/<slug>/snapshots`
2. **初筛候选**：`python3 SKILL/scripts/riser_scan.py prefilter --config CFG --snapdir SKILL/data/<slug>/snapshots --date DATE --out RUN/cand.txt`
   **补新品候选**：`make_calls.py new_listing` → oc_pull 到 `RUN/new_listing`（卖家精灵当前数据，按上架时间倒序 2 页，免费），再
   `python3 SKILL/scripts/riser_scan.py supplement --config CFG --snapdir SKILL/data/<slug>/snapshots --date DATE --out RUN/cand.txt --newlist RUN/new_listing`
   （追加上架 90 天内、小类前 100 的新链接，以及 config 里 `recheck: true` 的上次新品冲榜商品）。
3. **拉数（可并行）**：`daily`（跟踪 + 现有上升商品 + 兄弟链接）和 `riser_bsr --asins RUN/cand.txt`。
   以前几周发现的上升商品不会再拉（它们那一行已存在 `data/<slug>/riser_rows.json`，周度表直接沿用）。
4. **确认上升**：`python3 SKILL/scripts/riser_scan.py confirm --config CFG --run RUN --date DATE`
   - 输出分 🚀 快速上升、📈 渐进上升、🆕 新品冲榜（带“下周复核”的也录入，config 加 `recheck: true`）、`watch` 观察名单（只汇报）、`excluded`（只是从下跌里回升、或下周复核）；带“大促周，下周复核”的本周不录入。
   - 头部跟踪的 15 组不参与排查（脚本已排除）。
5. **复核新上升商品**：新的 ASIN 写进 `RUN/new_risers.txt`，先加进 config `risers`
   （字段照现有条目：asin、brand、name、keyword、type=fast/gradual/new、recheck（新品冲榜下周复核时为 true）、added=DATE、detected_week=上一周的周一、why、takeoff_text=起飞（渐进为上升起点）的日期和排名变化、grade），
   再拉 `riser_extra --asins RUN/new_risers.txt` 和 `daily --asins RUN/new_risers.txt`（只拉这几个，输出目录用 `RUN/daily_new`）。
   然后 `python3 SKILL/scripts/riser_timeline.py --config CFG --run RUN --date DATE --asins <新ASIN...>`：
   - 有“断货恢复”“变体组变化”标记的，核实后剔除并从 config 删掉；
   - 按时间线写复盘（动作时间线按日期列 5~8 条：改图改标题、价格/Deal/Prime/促销、新开广告、广告流量和自然流量的变化；
     效果写排名、自然流量、核心词自然位的前后数字；打法总结 2~3 句：靠什么起来、自然流量接没接上、能不能学、风险）。
     写进 `SKILL/data/<slug>/riser_reviews.json` 的 `entries`（date=DATE、type、grade），并更新 `common`（所有上升商品的共性）和 `not_listed`（观察名单、大促待复核）。
6. **周度表**：`python3 SKILL/scripts/weekly.py --config CFG --run RUN --date DATE`
   扫一遍输出：变体拆分、断货、Prime 价这些是否合理；动作明显不对就查原始数据，不要硬写进表。
7. **主图**：`python3 SKILL/scripts/fetch_images.py --dir IMG --asins <周度表和复盘里所有 ASIN> --snapshot SNAP.json --sales RUN/sales_rank`
   还缺的按 data-pulls.md 用卖家精灵 includeBrands 查一次，`--map` 补上。
8. **写飞书**：
   ```bash
   python3 SKILL/scripts/emit_weekly.py --config CFG --run RUN --date DATE
   python3 SKILL/scripts/emit_risers.py --config CFG --reviews SKILL/data/<slug>/riser_reviews.json --run RUN --date DATE
   python3 SKILL/scripts/write_tab.py --token <sheet token> --spec RUN/spec_weekly.json --images IMG --log RUN/write.log
   python3 SKILL/scripts/write_tab.py --token <sheet token> --spec RUN/spec_risers.json --images IMG --log RUN/write.log
   ```
   核对结果里 `value_mismatch_rows`、`cells_without_image`、`cells_without_link`、`truncated_rows` 都应为空；不为空就看 log 补做。
   **清空上周日度记录**（周度写完后做，配置了 `daily` 的类目才有）：
   ```bash
   python3 SKILL/scripts/daily_monitor.py reset --config CFG --run RUN/daily_reset --date DATE
   python3 SKILL/scripts/write_tab.py --token <sheet token> --spec RUN/daily_reset/spec_daily.json --images IMG --log RUN/write.log
   ```
   只保留 DATE 所在这一周（周一起）的日度记录。
   表头为“ASIN”的列会自动写成亚马逊商品页链接（蓝色下划线，单元格值仍是 ASIN）；非美国站加 `--domain amazon.co.uk` 这类参数。
9. **保存配置**：config 的 `risers` 改动、大促日（发现新的大促就加进 `promo_days`）写回。

## 汇报给用户

先说结果和表格链接，再按这个顺序简短说明：
1. 本周头部的关键动作（3~5 条：谁降价/做 Deal/开广告/变体拆分，效果如何）。
2. 排名上升：新录入几个（A/B 分级 + 一句打法），观察名单和大促待复核的有哪些。
3. 每月刷新时：跟踪名单的进出、大盘同比、异常月份。
4. 分流和花费：交给 DeepSeek 拉了多少调用、抽查情况、西柚大约扣了多少 Credits。

## 日度降价监控

每天由系统定时器自动运行，不经过 Claude：`scripts/daily_run.sh <slug>`（launchd 任务 `com.cathug.cwm-daily-<slug>`，每天 10:00；电脑睡眠时唤醒后补跑）。
配置在 config 的 `daily`：`top_n`（默认 20）、`own_brands`（剔除的自家品牌）、`drop_min`（降价阈值，默认 5%）、`task`（西柚 user_task）。

流程：卖家精灵当日快照 1 页（免费）→ 小类 BSR 前 N 个变体组，剔除自家品牌，每组取销量最高的子 ASIN → 西柚 `get_asin_info_trends` 近 6 天（每个约 1 Credit）
→ 最近 2 个有数据的日期里有降价动作的列一行 → 这些 ASIN 补拉 `get_asin_ad_change_trends` → 主图 → 写“竞对动作-日度”。

- 算降价动作：单日或连续 2 天累计降价 ≥ `drop_min`（次日恢复的写“单日降价，次日恢复”）、开始 Deal 或 Deal 价下调 ≥3%、Prime 专享价开始或下调、新增优惠券或促销。
- 动作列同时写这 2 天的其他动作：涨价、Deal 结束、划线价、断货、评分数骤降、新开广告。没有变体拆分判断（不拉兄弟链接）。
- 同一个降价（ASIN + 日期 + 类型）只在第一次发现时列出；同一天重跑会替换当天的行。记录存在 `data/<slug>/daily_rows.json`。
- 卖家精灵拉不到时改用 Sorftime `category_products`（BestSeller 前 100，当天数据，含本节点小类排名，1 次调用）；2026-10-28 实测和两天前的卖家精灵快照前 20 组重合 17 组，差异是正常排名变动。两家都拉不到时才用前一天的日度名单或最近的周快照，排名列标注“（MM-DD 排名）”。
- 每组的代表子 ASIN 优先用周度表已在跟踪的；Sorftime 只列出进了前 100 的子体，所以跟踪的子体不在其中时会换成组内销量最高的。
- 拉数：DeepSeek（oc_pull）先拉，`missing_calls.py` 找出没成功的行交给 agy 补拉。
- 中间文件在 `data/<slug>/daily_runs/<日期>/`，`run.log` 是日志，保留 14 天。成功或失败都会弹系统通知。
- 用户问“今天日度监控怎么样/为什么没跑”时，看最新的 `run.log`。
