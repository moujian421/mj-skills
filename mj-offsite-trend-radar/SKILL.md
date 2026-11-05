---
name: mj-offsite-trend-radar
description: 站外热点雷达：在商品词进亚马逊 ABA 之前发现它，抢跑上架。每周用亚马逊搜索框下拉联想快照比对（免费直连）和 TikTok Shop 近 30 天新品当词源，Gemini Flash 抽通用商品名并剔除服装、美妆、梗周边、品牌 IP、加密币等，卖家精灵 Google Trends 判断上升 / 已回落，上升的再查 ABA 周排名历史和亚马逊商品上架日期（剔除印花周边再数供给），分成抢跑窗口 / 已进 ABA / 已有供给 / 已回落 / 梗 IP 伪机会。也能单词核查：用户给一个站外看到的词（连写、梗、网络用语都行），自动拆写法查完整时间线。用户说“站外热点”“站外爆款”“抢跑 ABA”“TikTok 上火的东西亚马逊有没有”“这个词站外火了能不能做”“查一下 XX 这个词（站外看到的）”“跑一下站外雷达”时使用，即使没提 skill。已经进 ABA 的新词用 mj-aba-trend-discovery；确定要做的品做立项调研用 mj-market-analysis 或 mj-blackhorse-selection。
---

# 站外热点雷达

## 为什么要有这一层

热点的传导顺序：**站外内容火（视频、社媒、Google 搜索）→ 有人去亚马逊搜 → 搜得够多进 ABA → 卖家跟进上架**。进 ABA 只看搜索量，不需要先有对口商品。mj-aba-trend-discovery 只能在词进 ABA 之后发现它，这个 skill 负责更早的一段。

已核实的两个案例（2026-11-05）：

| 词 | 站外 | ABA | 亚马逊供给 | 结论 |
|---|---|---|---|---|
| fat trimmer（厨房去脂刀） | Google 3 月底暴涨、峰值 5 月；回测按本 skill 规则 **4 月 12 日那周起判“上升”** | 8 月 22 日（W34）才进榜 | 对口商品大多 8–9 月上架；TikTok Shop 9–11 月才有、销量很小 | 站外领先 ABA 约 19 周；TikTok Shop 是跟随者，不是源头 |
| knightcat / knight cat（持剑骑士猫梗） | knightcat 连写各平台都没数据（网上主要是一个 Solana 加密币）；knight cat 的 Google 热度 3 月底到 6 月高峰，7 月回到基线 | 从未进榜 | 词组匹配 31 个商品，2026-10 冒出的一批全是印花 T 恤、杯子、钥匙扣、摆件 | 梗周边，不是商品机会；Google 回测在 4 月同样判“上升”，必须靠类型和印花占比剔除 |

## 流程

```bash
cd ~/.claude/skills/mj-offsite-trend-radar
PULLER=cb python3 -u scripts/radar.py data/$(date +%Y%m%d)                                  # 每周雷达
PULLER=cb python3 -u scripts/radar.py data/<日期> --words-only --words "knightcat,fat trimmer"   # 单词核查
```

中途限流停了，重跑同一条命令即可，已拉到的复用。PULLER 默认 cb（CodeBuddy hy3）；hy3 限流时用 agy，DeepSeek 恢复后可用 oc。

| 步骤 | 做什么 | 工具 | 调用量 |
|---|---|---|---|
| 1. 下拉联想快照 | config 里 40 个种子词根 × (空 + a–z) 共 1080 个前缀，抓亚马逊搜索框联想词，和以往所有快照比对，**本周新出现的词**进候选。第一次跑只建基线 | Python 直连 completion.amazon.com，每次间隔 0.4 秒，约 8–10 分钟 | 0（免费，不登录账号） |
| 2. TikTok Shop 新品 | 近 30 天首次曝光、周销 ≥50 的新品翻 5 页（2026-11 实测满足条件的只有约 5 页、100 个），按类目名剔除服装、美妆、保健、食品、首饰、箱包、图书、收藏品。**只当词源，不按销量判断热度**（fat trimmer 在 TikTok 上销量很小） | Sorftime `tiktok_product_search` | 5 |
| 3. 抽商品名 | Flash 把联想词、TikTok 标题、用户给的词转成通用英文商品名，分类（实物功能 / 服装鞋包 / 美妆个护 / 食品保健 / 梗周边 / 品牌IP / 节日季节 / 非商品），判断是否新奇；用户给的词另给 1–3 个写法变体（knightcat → knight cat、cat knight）。雷达只留“实物功能 + 新奇”，28 天内查过的不重复查（过了 28 天会复查，防止早期没起势的词被永久跳过） | agy Gemini Flash | 1–3 次 |
| 4. Google Trends | 每个商品名（用户给的词每个变体都查）查 5 年周度曲线，最多 60 个，优先用户给的词、再 TikTok、再联想词 | 卖家精灵 `google_trend` | ≤60 |
| 5. 亚马逊深查 | 只查 Google 上升的和用户给的词：ABA 周排名历史、词组匹配前 20 个商品（按销量）、亚马逊下拉是否已出现该词；Flash 判断每个商品是否对口、是否印花周边 | 卖家精灵 `aba_research_trend` + `competitor_lookup`；直连下拉；Flash | 每个词 2 次 |
| 6. 判定和导出 | 见下表；输出 RUN/radar.csv 和 radar.xlsx（抢跑窗口标绿、排最前） | 本地 | 0 |

## 判定规则

**Google 阶段**（在 5 年周度曲线上算）：
- 上升：近 4 周均值 ≥ 前 12 周（第 5–16 周）中位数的 2 倍，且 ≥ 近 52 周峰值的 60%，且近 4 周里至少 3 周 ≥ 基线 1.5 倍（要持续上升，不是一周脉冲）
- 已回落：近 52 周峰值 ≥ 中位数 2 倍（确实火过），近 4 周 < 峰值 40%，且峰值在 4 周以前
- 其他为平稳 / 无热度
- Google 是相对值（0–100），小基数词从很少涨到稍多也会显示暴涨，所以要配合亚马逊下拉、ABA 一起看

**阶段**（按顺序判，命中即停）：

| 阶段 | 条件 |
|---|---|
| 梗/IP 伪机会 | 类型是梗周边、品牌IP、非商品；或前 20 个商品里印花周边 ≥80% 且对口功能商品 <3 |
| 已进ABA | 近 60 天 ABA 有排名 → 交给 mj-aba-trend-discovery |
| 已回落 | Google 已回落（knight cat 这类：4 月火、10 月才有人上周边，属于滞后跟风） |
| 已过热 | 近 30 天新上架的对口功能商品 ≥10 个（一个月涌进大量跟卖，窗口已关） |
| **抢跑窗口** | Google 上升，未进 ABA，对口功能商品（剔除印花周边后）<10 个，或全部是半年内上架 |
| 已有供给 | 对口功能商品 ≥10 个且有半年以前上架的 |
| TikTok先行（Google未起） | TikTok 来的词，Google 平稳或无热度。不深查，也不记入已查，下周继续复查 |
| 观察 | 其他（含 Google 平稳、无热度的） |

阈值都在 config.json：`overheat_new_30d`、`google_rise_ratio`、`google_rise_peak_share`、`google_fall_share`、`supply_few`、`supply_young_days`、`pod_share`、`recheck_days`、`google_max`。

## 调用量和速度

每周约 5（TikTok）+ ≤60（Google）+ 上升词 × 2（亚马逊），一般 80–100 次卖家精灵/Sorftime 调用，经 hy3 代调约 10 次/分钟，加上下拉联想 8–10 分钟，整体 15–25 分钟。不用西柚，不扣 Credits。单词核查一个词约 3–6 次调用，2–3 分钟。

## 已知限制

- **入口是瓶颈**：Google 规则在回测里能提前约 19 周抓到 fat trimmer，但前提是这个词先进了候选池。fat trimmer 不以任何种子词根开头，TikTok Shop 上又出现得晚，当时的雷达未必能抓到。补救办法：种子词根按需要扩充；在站外看到的词直接用 `--words` 核查。
- 下拉联想第一次跑只建基线，第二周起才有“新出现的词”。新词里很多是普通长尾词的日常波动，靠 Flash 的“新奇”判断过滤，可能误杀或漏放，要抽查 extract.jsonl。
- 卖家精灵 `google_trend` 只支持 web（youtube 报参数错误）；Reddit、Google 直连被拦；Google Trends 的 Rising 相关词榜单 2026-11-05 试过：agy 的 Gemini 没有网页读取工具，搜索只拿到摘要，如实回答取不到；本机脚本带 cookie 访问 Trends 接口被安全检查判为绕过反机器人限制而拒绝，不要再试。需要 Rising 词时，由用户在浏览器里看 Trends 页面，把词（或截图 OCR 后）用 `--words` 交给单词核查；Sorftime 的 `reddit_post_search` 噪音大（多是印度本地版块），`tiktok_video_tag_search` 只能按标签名模糊匹配，都没接进来。
- 连写词（knightcat）在各平台都查不到，所以用户给的词一定要拆写法。
- 结论只到“值得深查”，还没看利润、合规、专利；抢跑窗口的词转 mj-market-analysis 或 mj-blackhorse-selection。

## 参考过的外部做法（2026-11-05 调研）

| 做法 | 来源 | 本 skill 怎么处理 |
|---|---|---|
| Google Trends 看 5 年曲线、找 Rising/Breakout（涨幅 >5000%） | 卖家精灵博客 | 已用 5 年周度曲线；“峰值/中位数”列相当于涨幅。Rising 相关词榜单只能直连 Google 拿，被拦了，暂时用不了 |
| 搜索框联想词 = 买家真实输入 | 卖家精灵、Jungle Scout | 已用作主入口（每周快照比对） |
| 一个月内新增 10+ ASIN、价格下滑 = 过热 | 卖家精灵博客 | 已加“已过热”阶段（价格下滑还没算） |
| 信号顺序：TikTok 先起、Google 还低是早期窗口；亚马逊增速超过 Google 是购买意图在加速；YouTube 是中期信号 | Trends MCP 博客 | 加了“TikTok先行（Google未起）”。fat trimmer 是反例（Google 先、TikTok 最晚），说明顺序因品而异，所以两个入口都留 |
| 趋势要持续 3–6 周才算 | Trends MCP 博客 | Google 上升加了“近 4 周至少 3 周高于基线” |
| 多数据源 + 人工复核，剔除电影、名人八卦这类短命热点 | Exploding Topics | Flash 先剔除梗、IP、非商品，抢跑窗口的词由 Claude 抽查后再给结论 |
| 小批量测款：首批 100–200 件，7–14 天看 CTR >0.4%、CVR >10%、ACOS <40% | 卖家精灵博客 | 属于下游立项和测款，不在本 skill |

这些多是工具厂商的博客，阈值没有独立验证，只当参考。

## 文件

- `scripts/radar.py`：全流程，复用 mj-aba-trend-discovery 的 `aba_trend.py`（拉数读取）和 `agylib.py`（Flash 调用）
- `references/extract_prompt.txt`：抽商品名、分类、新奇、写法变体
- `references/title_prompt.txt`：亚马逊商品是否对口、是否印花周边
- `data/suggest_seen.json`：历次下拉联想词的累计集合（比对新词用）；`data/seen.json`：查过的商品名和日期
- `data/<日期>/`：每次运行的拉数、缓存和 radar.csv / radar.xlsx
