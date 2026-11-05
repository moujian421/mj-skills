# 新类目首次设置

1. 确认站点和类目节点（免费）：卖家精灵 `product_node`（keyword=类目名）、Sorftime `category_name_search`、西柚 `search_market_insight_categories`。
   西柚要求用户确认类目；类目口径和亚马逊节点不一致时，用节点里销量最高的 1~2 个 ASIN 反查西柚类目（同一工具传 ASIN），选能覆盖这些 ASIN 的上级类目，告诉用户依据。
2. 用户确认后生成西柚资源（500 Credits）。
3. 新建配置 `data/<slug>/config.json`，复制 `data/exercise-equipment-mats/config.json` 的结构：节点、西柚 categoryId/resourceId、飞书表 token 和页签名、
   `start_week`（第一周的周一）、`top_n`、`top_bsr_max`、`riser_rule`、`promo_days`（已知大促日）。`tracked`、`risers` 先留空。
   飞书表：用户给了表就写进去；没给就 `lark-cli sheets +workbook-create --title "<类目> 竞品周度监控"`，再在 config 里填 token。
4. 拉 snapshot 和 sales_rank → `pick_top.py --write` 生成跟踪名单 → 逐个改中文短名（品牌 + 规格/类型）和核心词（按产品类型选，写进 `keyword_by_type`）。
5. 拉 market_xy，看关键词列表，按产品类型分组选核心词（每组 3~5 个，总数 ≤10）：按搜索量和类目相关度选通用词；
   同义变体不重复列；剔除相关度低的泛词、他用词、品牌词。写进 `keyword_groups`。
6. 之后按 SKILL.md 的“每月刷新”和“每周流程”跑一遍。
