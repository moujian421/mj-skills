---
name: mj-competitor-review-analysis
description: 竞品评论打标分析：输入一个或多个亚马逊 ASIN，用卖家精灵 review 翻页拉全部文字评论，按细分市场的标签库让 DeepSeek 逐条打标签（问题和卖点都打，一条评论可有多个标签，附中文翻译和原文依据），算出好评（4–5 星）、中评（3 星）、差评（1–2 星）里各细分标签的占比，以及按 ASIN、变体、近 12 个月、VP/Vine 的拆分，写进一个新的飞书多维表格，仪表盘同时做饼图和柱状图。用户说“评论打标”“Review 打标”“评论分析”“竞品评论都在骂什么/夸什么”“差评痛点占比”“好评卖点占比”“抓全部评论分析”，或给出 ASIN 要看评论细分比例时使用，即使没提 skill。新品首月的评论资产（Vine、VP、老链接继承）用 mj-competitor-launch-analysis；类目级的评论情感概览用 mj-market-analysis。
---

# 竞品评论打标分析

输入 ASIN，拉全部文字评论，逐条打标签，输出好评、差评里各细分标签的占比，写进飞书多维表格。

## 一、输入

- ASIN：一个或多个（同一个变体组的子体、或同一细分市场的几个竞品可以一起做）
- 站点：默认 US
- 细分市场：决定用哪份标签库（见 `references/taxonomy/`）。用户没说时，Claude 按商品标题判断后告诉用户用了哪份
- 截止日期：默认今天，用来划“近 12 个月”

缺 ASIN 先问，不猜。

工作目录 `WORK` 放在 `~/.claude/skill-work/mj-competitor-review-analysis/<第一个ASIN>_<YYYYMMDD>/`，不要放在 `/private/tmp` 的 scratchpad 里（会被隔夜清空）。脚本都在 `~/.claude/skills/mj-competitor-review-analysis/scripts/`，下文写作 `$S`。

## 二、拉评论（DeepSeek 拉，Claude 不读全量）

卖家精灵 `review` 每页最多 20 条（2026-10-30 实测，传多大的 size 都只给 20），一个 1200 条评论的 ASIN 要翻 60 多页，所以一律交给 `batch-offload` 的 `oc_pull.sh`。

1. 确认商品：Claude 自己调一次 `asin_detail`，记下标题、品类、评分总数（ratings）。评分总数会比文字评论数大很多，多出来的是只打星没写字的评分，报告里要写明覆盖比例。
2. 探总数：每个 ASIN × 每个星级调一次（只返回星级，数据很小）
   ```bash
   python3 $S/make_calls.py probe --site US --asin B07YN1W5W3 > WORK/calls_probe.txt
   ~/.claude/skills/batch-offload/scripts/oc_pull.sh WORK/calls_probe.txt WORK/pull_probe
   ```
3. 翻页：按星级分开翻页，页数更少，不容易碰到翻页上限，拉完也能逐星级核对条数
   ```bash
   python3 $S/make_calls.py pages --site US --probe-dir WORK/pull_probe > WORK/calls_pages.txt
   ~/.claude/skills/batch-offload/scripts/oc_pull.sh WORK/calls_pages.txt WORK/pull_pages
   ```
   超过 100 个调用时用 `run_in_background` 跑。`oc_pull.sh` 打印的 `errors`、`missing_lines`、`unexpected_calls`、`unrecognized` 四项要看（含义见 batch-offload）。
4. 合并、去重、核对
   ```bash
   python3 $S/merge_reviews.py WORK WORK/pull_pages [WORK/pull_retry ...] --probe-dir WORK/pull_probe
   ```
   - `shortfall` 不为空、生成了 `WORK/missing_calls.txt` 时，把它当清单再跑一次 `oc_pull.sh`（输出到 `pull_retry`），然后带上所有 pull 目录重新合并。
   - `star_missing` 大于 0 说明接口没给星级，脚本已用请求的星级补上，结果里写明。
   - 某个星级超过 150 页（3000 条）时，脚本只拉最新的部分并提示；这时和用户确认是否按时间段再拆。
   - 卖家精灵拉不到（ASIN 没收录、返回空）时，用 Sorftime `product_reviews` 兜底，但它只给近一年最多 100 条，只能当样本，结论里必须写“样本 N 条，不是全量”。

## 三、标签库

每个细分市场一份，放在 `references/taxonomy/<细分市场>.md`，格式是一张表：`| 一级 | 标签 | 正负 | 定义 | 不归入 |`。标签名本身带方向（如「表面打滑」是负、「防滑好」是正），不要建一个标签同时用于正负两面。

现有标签库：
| 文件 | 适用 |
|---|---|
| `eva-拼接地垫.md` | EVA 拼接泡沫地垫 |
| `三轮高尔夫推车.md` | 三轮折叠手推高尔夫球车 |

**已有标签库**：直接用。文件里写着“正面标签初版、未校准”的，第一次用时先做校准：
```bash
python3 $S/sample_for_taxonomy.py WORK --n 60 --stars 4,5
```
Claude 读 `WORK/taxonomy_sample.txt`，看好评里常见的卖点有没有对应标签，缺的补上，定义不清的改掉，然后把“未校准”那句话删掉、写进变更记录。

**没有合适的标签库**（新的细分市场；同一个大类目下细分不同也算新的，比如整卷瑜伽垫不用拼接地垫的库）：
1. `python3 $S/sample_for_taxonomy.py WORK --n 90`，按星级 × 变体 × 时间分层抽样
2. Claude 读样本，起草标签库：负面 15–25 个、正面 10–15 个，一级分类 6–8 个。每个标签都要写定义；容易混的两个标签，在“不归入”里写清楚互相怎么分
3. 按 batch-offload「决策思考型任务」，把样本摘要和标签草稿交给 Argon 挑刺（重叠、遗漏、粒度不一），Claude 核对后定稿
4. 存成新文件，文件头写适用范围、来源、日期

改已有标签库要在文末“变更记录”里写日期和原因。改名或合并标签后，旧分析的飞书表不用回改。

## 四、打标（DeepSeek 打，Claude 抽查）

```bash
python3 $S/tag_reviews.py WORK $S/../references/taxonomy/<细分市场>.md --product "<一句话描述产品，含材质和用途>"
```

- 指令是写死在脚本里的：观点级打标（一条评论里夸的、骂的都要找出来），每个标签附原文依据，外加中文翻译和 20 字摘要。不要让子 agent 或 DeepSeek 自己组织指令。
- 每批 30 条，3 批并行；不合格的行（标签不在库里、缺字段）会自动用小批重跑，再不行换 agy。约 1000 条评论跑 10–20 分钟，用 `run_in_background`。
- 中断了直接重跑同一条命令，会接着打没打完的。

跑完看打印的统计，然后：
1. **抽查**：Claude 亲自读 `WORK/tag_sample.txt`（随机 8%），逐条判断标签对不对、有没有漏掉的评价。错误率超过约 10% 时，先改标签定义或“不归入”规则，再用 `--only-ids` 重打出错类型涉及的评论，不要整批放过。
2. **其他标签**：`other_share_of_points` 超过 0.08 时，看 `suggested_new_tags`，把反复出现的补进标签库，然后只重打带「其他」的评论：
   ```bash
   python3 -c "import json;[print(o['id']) for o in map(json.loads,open('WORK/tags.jsonl')) if any(p['tag'].startswith('其他') for p in o['points'])]" > WORK/redo.txt
   python3 $S/tag_reviews.py WORK <标签库> --product "..." --only-ids WORK/redo.txt
   ```
3. `tag_failed.txt` 里剩下的评论，少于 30 条时 Claude 自己打，写回 `tags.jsonl`（同样的格式）。

## 五、统计

```bash
python3 $S/stats.py WORK $S/../references/taxonomy/<细分市场>.md --asof <截止日期>
```

口径（不要改）：
- 好评 = 4–5 星，中评 = 3 星，差评 = 1–2 星。
  - 用户只要“差评分析”时，差评 = 1–3 星（用户 2026-11-05 纠正）：只拉 1–3 星，`stats.py` 的分组写死 1–2 星，这时自己按 1–3 星合并统计。B0GLQH4453 就是这样做的，结果写进了周度监控表的新页签（用 mj-category-weekly-monitor 的 `write_tab.py`），没有建多维表格。
- **占比** = 该组里提到这个标签的评论数 ÷ 该组评论总数。一条评论可以有多个标签，所以同组各标签的占比相加会超过 100%。柱状图用这个口径。
- **提及构成** = 该标签的提及次数 ÷ 该组同方向（负面或正面）的全部提及次数，相加等于 100%。饼图用这个口径。排名也在同组同方向内排。
- 没打上任何标签的评论（只写了 "good" 之类）也算在分母里。
- 除了按星级分组，还要看观点本身的方向：好评里的槽点、差评里仍被认可的点都会在简报里单独列出。

Claude 只读 `WORK/feishu/brief.md`，不读明细。结论写之前，按 batch-offload 把 brief 里的数字交给 Argon 要一次独立意见（先不给 Claude 的结论），Claude 核对它的【假设】后再定稿。

结论要回答：
- 差评的前 3–5 个问题，各占多少，属于产品本身（可改进）还是物流售后（与产品无关）
- 好评的前 3–5 个卖点
- 好评里也常出现的问题（说明连满意的买家都在意）
- 拆分里有没有明显差异：某个变体问题特别集中、近 12 个月比以前变好或变坏、Vine 和 VP 的说法不同
- 对我方产品的启示（Listing 卖点、图片、产品改进），只基于数据，不编

## 六、写飞书

一次分析建一个新的多维表格，不和别的分析合并（细分市场不同，标签库也不同）。

```bash
python3 $S/write_feishu.py WORK --name "<ASIN 或竞品名> 评论打标 <YYYY-MM-DD>"
```

建出来的内容：
| 表 | 内容 |
|---|---|
| 评论明细 | ASIN、日期、星级、分组、变体、VP、Vine、图片/视频、英文标题、英文正文、中文翻译、摘要、负面标签、正面标签、一级分类、依据、建议新标签 |
| 占比汇总 | 分组 × 标签：评论数、组内评论数、占比(%)、提及构成(%)、排名 |
| 一级分类汇总 | 分组 × 一级分类的占比 |
| 拆分对比 | 按 ASIN（多个时）、变体（≥30 条的）、近 12 个月、评论类型拆开的占比 |
| 标签库 | 本次用的标签、定义、不归入规则 |
| 仪表盘 | 口径说明；差评问题、好评卖点各一张柱状图（占比）和一张饼图（提及构成）；差评一级分类柱状图 |

脚本把每条命令和返回写进 `WORK/feishu/write.log`，只打印成败和读回条数。`应写` 和 `读回` 对不上、或 `commands_failed` 大于 0 时，看日志定位，用 `--base-token <已建的> --only <表名>` 补写那一张表，不要重建整个表格。第一次用某种图表配置前，可以先加 `--dry-run` 看请求。最后 Claude 用 lark-cli 读回 2–3 个关键单元格（如差评第一名的占比）核对。

## 七、给用户的结果

先给结论，再给链接。用一张表列差评前 5 和好评前 5（标签、占比、评论数），下面是三五句结论和启示。然后写：
- 覆盖：文字评论 N 条，占评分总数的 X%，日期范围
- 分流：拉数 M 个调用交给 DeepSeek；打标交给 DeepSeek，Claude 抽查 K 条，错误率约 Y%
- Argon：采纳了哪些意见，有哪些分歧

## 八、注意

- 不编：占比都来自脚本统计；结论里引用的评论内容要能在明细里找到。
- 样本不等于全量：用 Sorftime 兜底、或某星级被截断时，必须写明。
- 评论只代表留了文字的买家，不能直接当退货率或缺陷率。
- 竞品的差评占比高，不一定是产品差，先看是不是物流、售后、单一批次的问题集中出现（看拆分里的时间和变体）。
- 跑通或纠正过的做法，更新到本文件或标签库里。
