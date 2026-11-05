---
name: mj-aba-trend-discovery
description: ABA 周度趋势新词发现：每周用卖家精灵 ABA 周榜的“异动市场”（上周不在榜的新词/回归词）和“周排名提升 ≥70%”（飙升词）两个清单，限排名 20 万内、13 个实物类目，脚本过滤节日词、品牌词、单品垄断词，按同词根词簇排序，再用西柚批量查去年同期排名剔除季节词，输出趋势候选词表。不存 ABA 全量，每周约 30–50 次卖家精灵调用 + 几百西柚 Credits。用户说“找新出现的趋势词/趋势产品”“ABA 新词”“ABA 飙升词”“这周 ABA 冒出什么新品”“排除季节性的趋势词”“跑一下 ABA 趋势”，或举出“某词以前不在 ABA、突然进榜”的例子时使用，即使没提 skill。单个关键词值不值得做用 amazon-keyword-seo；找到候选后做立项调研用 mj-market-analysis 或 mj-blackhorse-selection。
---

# ABA 周度趋势新词发现

目标：从亚马逊 ABA 周榜里找**新出现的产品需求**，排除节假日和季节性。案例：handheld fat trimmer（厨房切肉去脂工具），2024 年以来从未进榜，W34（2026-08-22）首次 5.5 万名，同周冒出 6 个同词根新词，之后稳定在 9–18 万名。

## 怎么跑

```bash
~/.claude/skills/mj-aba-trend-discovery/scripts/run_week.sh [yyyymmdd 周六]
```

- 不给日期时取 10 天前之前最近的周六。卖家精灵周榜**只开放最近一周**（2026-11-04 时只能查 20261024），历史周查不了。
- **周榜只能在进榜那一周抓到新词**：之后它上周已在榜、周涨幅也不大，两个清单都不会再返回（fat trimmer W34 进榜，W43 就抓不到了；接口不能按“12 周前不在榜”过滤，排序参数也不生效）。所以**每月再跑一次月榜**兜底：`run_week.sh yyyymm`（只跑异动市场，`aba_research_monthly`），月榜**可以查历史月份**（2026-11-04 时 202608、202609 可查，202610 还没出，报“只能查询上一月的数据”）。漏掉的时段用 `run_backfill.sh 202608 202609` 补跑（含清洗）。
- 用 `run_in_background` 跑，全程几分钟。拉数交给 DeepSeek（`oc_pull.sh`），第 1 轮一个都没拉到（免费额度用完、限流）时自动换 CodeBuddy hy3（`cb_pull.sh`），也可以 `PULLER=cb` 直接指定。
- 结果在 `data/<日期>/`：`report.md`（前 80 个候选）、`candidates.csv`（全部）、`screened.json`（含被过滤的词和原因）、`seasonal.json`（判为季节词的）、`run.log`。
- Claude 只读 `run.log` 的统计行和 `report.md`，不读 raw。
- 统计行里 `接口 total` 比 `拉到` 多是正常的（多类目重复返回）；要看的是每页条数是否满、`errors`/`missing_lines` 是否为空、`西柚未查到` 是否为 0。
- CodeBuddy 的西柚返回超长时，raw 里是 `.txt` 的“saved to <文件>”指针，`aba_trend.py` 会去读那个文件（在 `~/.codebuddy/projects/.../tool-results/`），不用重拉。

## 流程和规则（参数都在 `config.json`）

1. **拉两个清单**（卖家精灵 `aba_research_weekly`，每页最多 40 条；月度 `aba_research_monthly` **每页最多 15 条**，`size` 填更大也只给这么多，页数按这个算，曾因按 40 算漏掉 60% 的月度词）：
   - A 异动市场：`searchModel: 2`，返回上周不在榜的词。4 周前和 12 周前也不在榜 = **新词**，否则 = **回归词**。
   - B 飙升：`minRankGrowthRate: 70`，**按百分数填**（填 0.7 等于 0.7%）。不填 `searchModel` 和填 4（快速飙升）结果一样。= **飙升词**。
   - 两个都加 `maxSearchRank: 200000` 和 `departments`。
2. **类目**：`departments` 要填**亚马逊类目代码**，填类目名（如 "Sports & Outdoors"）返回 0 条。多个代码取并集。已实测可用：`kitchen` `home-garden` `sporting` `hpc` `beauty` `pets` `tools` `lawngarden` `toys-and-games` `baby-products` `automotive` `office-products` `arts-crafts`。`garden` 无效（要用 `lawngarden`）。没有类目的词（多是图书）会自然被排除。
3. **节日词**：关键词含 `holiday_roots` 里的词根就剔除。
4. **词簇**（`aba_trend.py` 初筛用）：相邻两个实词组成的词组（复数去 s）。只用于初筛阶段的品牌/单品垄断豁免；交付时词簇改用 supply.py 的核心词词簇。
5. **品牌词 / 单品垄断**：关键词含 top3 品牌名，或第 1 名 ASIN 点击占比 ≥50% 的剔除；**词簇 ≥3 时豁免**（爆款首发期常被一个 ASIN 垄断，不能误杀）。
6. **季节词**（西柚 `get_keyword_aba_trends`，服务名在 `config.json` 的 `xiyou_server`，用户 2026-11-04 要求改用 `xydc-mcp-2`，每词 1 Credit，一次 100 个词，查去年同期前 8 周到后 2 周）：
   - 新词 / 回归词：去年这段时间有 ≥2 周进过前 30 万 → 季节词。
   - 飙升词：去年同期 ±2 周最好排名进前 30 万，并且比去年前 4–8 周的中位排名好一倍以上（去年也这样飙过）→ 季节词。去年不在榜按 250 万名算。
7. 排序：词簇大小 → 新词 > 回归词 > 飙升词 → 本周排名。

用户明确不要的过滤（2026-11-04）：连续几周留存（一周闪现）、老品换叫法（和老词前 10 ASIN 重合）。不要加回来。

## 成本（2026-11-04 实测）

| 项目 | 每周量 |
|---|---|
| 存 ABA 全量（前 20 万） | 约 5000 次卖家精灵调用，已放弃 |
| 清单 A | W43 限类目后 145 个，4 次 |
| 清单 B | W43 限类目后 total 597（一个词属于多个类目会重复返回，去重后 457 个），15 次 |
| 西柚季节性 | W43 共 280 个词 × 11 周，约 150 Credits；免费额度每周 1 万、每月 3 万 |
| 月榜（每月一次） | 8 月 539 个、9 月 638 个，每月约 40 次调用 |

W43（20261024）实测：节日词剔除 74 个、品牌词 133 个、单品垄断 115 个，季节词 28 个，最终 252 个候选。拉数用 CodeBuddy hy3，19+3 次调用全部成功，几分钟跑完。

西柚 `find_keyword_opportunities` 也带全部历史，但 10 Credits/词，不要用它查季节性。

## 第二道清洗：剔除品牌 / IP / 球队 / 高风险 / 季节 / 无效词

脚本规则剔不干净（W43 的 252 个候选里还有 139 个该剔），跑完 `run_week.sh` 后接着跑：

```bash
python3 ~/.claude/skills/mj-aba-trend-discovery/scripts/clean.py data/<日期>
```

- 交给 agy 的 `gemini-3.8-flash-medium` 按 `references/clean_prompt.txt` 打 7 类标签（keep/brand/ip/sports/risk/holiday/junk），一次全部发出，没标上的自动重试 2 次。DeepSeek 可用时也可以换它，规则文件通用。
- 输出 `candidates_clean.csv`（保留）、`candidates_removed.csv`（剔除 + 原因）、`clean_tags.jsonl`。
- **Claude 必须抽查保留的词**：W43 实测 Flash 剔除部分基本准确，保留部分漏了约 13%（万圣节面具、年末日历、圣诞 tinsel、降临节日历书、政治旗帜、补充剂、类枪玩具）。规则已补进 prompt。抽查出的错写进 `data/<日期>/overrides.json`（`{"关键词": ["tag", "中文原因"]}`），再跑 `clean.py data/<日期> gemini-3.8-flash-medium --reuse` 只套用修正、不重新打标。
- 月度结果也要抽查：2026-09 Flash 漏了 poke wreath（圣诞花环）、gift trap（节日礼物）、感恩节肉汁船等。W43 + 8、9 月合计保留 307、剔除 543。

## 需求类型 + 供给判断（supply.py，只用卖家精灵 + Flash，不用西柚）

```bash
PULLER=cb python3 -u scripts/supply.py data/supply_<日期> data/<周> [data/<月> ...]
```

关键事实（2026-11-04 实证）：**ABA 收录只看搜索量，不要求先有对口商品**。silicone drill brush 已进 ABA，亚马逊前台自然位前 20 全是普通尼龙钻头刷，真正对口的宠物除毛硅胶钻头刷 10-20 后才上架；fat trimmer 最早对口商品 2025-08 上架，ABA 2026-08 进榜，大批跟卖 8–9 月上架。所以**前排对口商品的上架日期**能同时回答“是不是新产品”和“供给跟上没有”。

1. **词簇 = Flash 拆出的产品核心词**（`core_tags.jsonl`，按关键词缓存），不再用相邻两个词（会出现 "l f"、"plant live" 这种错簇）。核心词保留用途（用途变了算另一种产品）；但词里没写用途时 Flash 也判断不出（silicone drill brush → drill brush）。
2. **代表词**：优先和核心词一样的词，其次最短的词，去掉 best/top 等修饰。
3. **卖家精灵 `competitor_lookup`** 按销量取前 10：先精准匹配（matchType 3）；不到 3 个再用**词组匹配（matchType 1：所有词都出现、不限顺序）**。**不要用模糊匹配（matchType 2，任意词命中，返回几百万无关商品）**。`totalUnits` 字段返回 null，但按 `total_units` 排序有效；`availableDate` 是毫秒时间戳。
4. **对口校验**：Flash 按 `references/relevance_prompt.txt` 判断每个商品标题是否真对口，蹭词老链接不算（silicone drill brush 精准匹配 22 个，真对口 3 个）。结果缓存在 `relevance.jsonl`，新工作目录可以复制过去复用。
5. **判定**：
   - 核心词老产品 = 有对口商品早于 12 个月前上架，或精准匹配商品 ≥100（核心词前排常被配件占满，如 compound bow → 箭、瞄准镜）。老产品 + 新属性 = 旧产品新属性，无属性 = 旧产品回暖，否则新产品。
   - 供给缺口 = 对口商品 <3；供给早期 = 对口商品全部 12 个月内上架；否则已有供给（近 90 天新进 ≥3 个注明）。属性只是尺寸规格（4.25 hole saw）时供给看核心词。代表词 ≥4 个词、两种匹配都查不到但核心词早有供给的，标“可能缺口（词组长，需人工看）”。
6. **Google Trends**（卖家精灵 `google_trend`）：只查最后排在前面的 30 个词簇（config `google_top_n`；范围是新产品、旧产品新属性、缺口/早期，按缺口 > 早期 > 可能缺口 > 其他、同簇词数、最好排名排序，和导出表一致），标上升 / 平稳 / 回落 / 无热度和峰值月。fat trimmer 的 Google 热度 3 月底起暴涨、4–6 月高峰，ABA 8 月才进榜，说明进 ABA 时站外可能已经过了峰值，回落的要慎重。
7. 调用量：W43 83 个词簇共约 220 次卖家精灵调用（代表词 83 + 词组兜底 47 + 核心词 31 + Google 64；Google 限前 30 个后约 190 次）。以后周榜拉数已加 `titleDensityExact`（首页标题含该词的商品数），可以先用它预筛，只查密度低的词，减少调用。
8. 试点踩过的坑（都已修）：对口结果字段名不对被全部丢掉 → 全判成缺口；单个飙升词跳过 → 漏掉 silicone drill brush；长词组精准匹配为 0 → 假缺口。

**西柚账号（2026-11-04 更新）**：按全局 CLAUDE.md「西柚 MCP 额度规则」：本 skill 默认 `xydc-mcp-2`（`config.json` 的 `xiyou_server`），不够切 `xydc-mcp`；两个都不够才用 `xydc-mcp-3`，用前提醒用户，3 号剩余 ≤ 5000 停用；每次预估 > 500 Credits 先请示。Claude、CodeBuddy、WorkBuddy、opencode、Antigravity 同名同账号（2026-11-04 核对：opencode 的 xydc-mcp-2 和 Antigravity 的 xydc-mcp 原来都错指 3 号，已改正；此前本 skill 用 oc/agy 拉数烧的是 3 号额度）。批量跑前用 `get_account_credit_quota`（免费）查额度，额度显示有延迟。

**拉数执行方**：`PULLER=cb`（CodeBuddy hy3，免费但会限流，2026-11-04 下午触发频率限制、当晚 19:31 恢复）、`PULLER=agy`（Gemini Flash low，占 Antigravity 每周额度）、`PULLER=oc`（DeepSeek，免费额度会用完）。supply.py 中途停了可以直接重跑同一条命令：已拉到的复用，只补缺的行。

旧的西柚版 `classify.py`（查核心词 6–12 个月前是否在 ABA 榜）保留但不再默认用：西柚按“词数 × 周数”扣费（约每 20 个词·周 1 Credit），曾把两个西柚账号（xydc-mcp、xydc-mcp-2）的周额度都用完（2026-11-04，11-09 重置）。

## 站外抢跑（在新词进 ABA 之前）

站外这一段已单独做成 skill **mj-offsite-trend-radar**（下拉联想快照 + TikTok Shop 新品 → Google 上升 → 亚马逊供给），以下为背景。

链路：站外内容火（视频、社媒、Google 搜索）→ 有人去亚马逊搜 → 搜得够多进 ABA → 卖家跟进上架。TikTok Shop 常是跟卖方不是源头（fat trimmer 的 TikTok Shop 商品 9–11 月才出现、销量很小），不能当主信号。

| 层 | 信号 | 工具 | 状态 |
|---|---|---|---|
| L0 站外内容 | TikTok / Reddit 突然火的商品视频、帖子 | Sorftime `tiktok_video_search_from_name`（按标签/标题）、`reddit_post_search`，Flash 抽商品名 | 未做（silicone drill brush 查不到 TikTok 视频数据，要先小量试积分和覆盖率） |
| L1 Google 热度 | 商品名 Google 搜索上升 | 卖家精灵 `google_trend` | 已接在 supply.py 后面 |
| L2 亚马逊下拉框 | 种子词下新冒出的联想长尾 | mj-keyword 的下拉框脚本 | 未做，要先有种子词 |
| L3 ABA 新词 + 供给缺口 | 本 skill 主流程 | 卖家精灵 | 已做 |

fat trimmer 是目前唯一有完整时间线的案例（站外领先 ABA 约 4–5 个月，但 Google 上这个词也可能指减肥腰带），领先时间要多验证几个案例。

## 交付

```bash
python3 scripts/export_xlsx.py <输出.xlsx> data/<周> data/<月> ... --supply=data/supply_<日期>/supply.csv [--supply=...]
```

第 1 页保留词：词簇（核心词）、需求类型、供给、Google 热度和峰值月、最早对口商品上架日期、核心词、新属性、来源（周/月，同一个词多处出现会合并）、排名和指标，供给缺口和供给早期排最前；第 2 页剔除词和原因。没跑 supply.py 的需求类型显示“待核实”。

## 读结果时 Claude 要做的判断

- 看清洗后的保留词，按词簇挑出可能的新品类。
- 对挑出的词簇做验证：西柚/卖家精灵看词下商品（上架时间、评论数、价格、卖家数）、Google Trends / TikTok 看站外热度、1688 价格算利润；减肥、医疗类宣称要注意合规。深入调研转 mj-blackhorse-selection 或 mj-market-analysis。
- 结论前按全局规则问 Argon 第二意见。

## 已知局限

- 爬坡慢的词（单周涨幅不到 70%、上周已在榜）会漏掉：服务端只能按 1 周增长率过滤。要补的话再加一个清单，本地按 4 周增长率过滤，但调用量会翻倍。
- 类目为空的新奇产品会被类目过滤漏掉。
- 词簇 ≥3 豁免品牌过滤，所以大品牌的一串词会漏进来（W43 的 e.l.f.、kitchenaid），读结果时人工剔。
- 去年同期本来就在榜、今年只是提前起量的季节词，飙升词规则可能漏判（W43 的 heated seat cushion for office chair）。
- 词簇只认相邻两个词，`fat meat trimmer` 和 `meat fat trimmer` 不会算一簇。
