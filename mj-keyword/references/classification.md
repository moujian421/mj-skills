# 搜索意图分类规则

示例全部来自 US 站 Golf Push Cart（高尔夫手推车）类目。换成其他类目时，套用同样的思路，把"自家配置"换成实际产品的配置。

## 目录
1. 广告词库的词组类别
2. 否词库的否定原因
3. 宽泛词怎么判断（证据顺序）
4. 常见误判

---

## 1. 广告词库的词组类别

| 词组类别 | 判定 | 例子 | 使用说明（写进表格） |
|---|---|---|---|
| 核心品类/同义词 | 直接描述自家产品，相关度高，首页基本都是同类产品 | golf push cart、golf bag cart、golf walking cart、push golf cart | 同义词自然分布到标题和五点，不必逐个重复 |
| 长尾/场景 | 核心词加属性或场景，搜索量小 | golf pull carts 3 wheel folding、golf hand cart、folding golf cart | 精准小额测试，按转化决定去留 |
| 竞品品牌 | 竞品整车的品牌或型号 | caddytek push cart、bag boy nitron、clicgear 4.0 | 独立广告组测试；不写进自家 Title、五点或后台 Search Terms |
| 宽泛/促销意图 | 大词或泛词，意图混杂；或者带促销修饰 | golf cart、push cart、caddy cart、clearance golf push carts | 只做小额精准；不能作为词根整体做词组否定；文案里不能因此宣称清仓 |

## 2. 否词库的否定原因

| 否定原因 | 推荐匹配方式 | 例子 |
|---|---|---|
| 电动、遥控或电池需求（自家是手动款） | 词根做词组否定：electric、remote、motorized | electric golf push cart、remote golf push cart |
| 乘坐式车辆或滑行车 | 词根做词组否定：scooter、seater、street legal、used、gas golf；其余用精准否定 | golf carts for sale、golf car、golf carts for adults |
| 球包、旅行包或包附件，不是整车查询 | 精准否定（golf bag 不能作为词根做词组否定） | golf cart bag、womens golf bag、lightweight golf bag |
| 单独的配件，或乘坐式车辆的配件 | 精准否定 | golf cart cooler、golf cart storage、golf cart garage |
| 指定品牌的单独配件 | 精准否定 | bag boy umbrella holder、caddytek push cart accessories |
| 配件和整车意图可能混在一起 | 精准否定，启用状态写"按搜索词报告启用" | golf push cart phone holder、golf push cart umbrella holder |
| 儿童或玩具车 | 词根做词组否定：kids、mini golf cart | kids golf cart、golf cart for kids |
| 其他运动品类 | 词根做词组否定：disc golf | disc golf cart、zuca cart |
| 配置不适配（取决于自家 SKU） | 词根做词组否定：4 wheel、seat | golf push cart 4 wheel、golf push cart with seat |
| 其他品类 | 词组否定或精准否定 | go cart、stroller golf caddy、golf bike |

## 3. 宽泛词怎么判断（证据顺序）

按下面的顺序看证据，越往后越可靠：

1. **相关度、平均售价（卖家精灵）**：只能给一个初步方向。平均售价很容易被少数高价商品拉偏。
2. **点击转化率、建议竞价（西柚）**：和核心词比较。转化率达到核心词的一半以上，就值得测。
3. **ABA 点击前三和转化份额**：前三是不相关的产品而且几乎不转化，说明转化落在了别的商品上，还要结合第 4 步看是落在了谁身上。
4. **关键词反查 ASIN（西柚 `get_keyword_asin_analysis`，`page_size: 10`）**：首页自然排名和广告位前排是不是同类产品，同类产品拿到了多少流量。**这一步说了算。**

做决定（按前 10 个 ASIN 里同类产品的数量）：
- 同类 ≥6 个，而且转化率达到核心词的一半以上 → 升到 A2，跑精准匹配，出价控制在建议价以下。
- 同类 ≥6 个，但转化率不到核心词的一半 → C 低预算探索。例如 ab coaster：首页是同类，但转化率只有 2.4%，核心词是 5.0%。
- 同类 4 到 5 个 → C 低预算探索。例如 core workout equipment 是 5/10。
- 同类 ≤3 个 → 放进否词库。如果有少量同类，用精准否定，并标"按搜索词报告启用"。
- 西柚没有转化率时：依次用 ABA Top3 转化份额、卖家精灵购买率和核心词比较，并写明用的是哪个替代指标。

案例 golf cart：
- 卖家精灵：平均售价 $8,199，购买率只有核心词的四分之一 → 初判是"C 低预算探索"。
- 西柚：周搜索 9,522（比核心词还大），转化率 3.6%（核心词是 5.1%），竞价 $2.46。
- ABA：点击第一的是一辆 $10,500 的乘坐式电动车，转化份额只有 0.8%。
- 反查 ASIN：EASEGO 三轮手推车自然排名第 1、SP 广告第 1，CaddyLite 自然第 2，findway 自然第 4。
- 结论：升到 A2，跑精准；单均广告费约 $69，所以要控价。

## 4. 常见误判

- 把一个词根整体做了词组否定，结果误伤了想投的词：for sale 会挡掉 golf push carts for sale；cooler、umbrella 会挡掉带这些配件的整车词。**做词组否定之前，一定要拿词根在广告词库里搜一遍。**
- 以为词组否定能覆盖复数：scooter 不一定挡住 scooters，搜索量大的复数要另加精准否定。
- 品牌词一律否掉：竞品整车品牌词其实可以做竞品测试；只有竞品的配件词、包类词才需要否。
- 同一个词在两张表里都出现，或者两张表都没收：结束前把卖家精灵的全部拓词和两张表做一次比对，没收录的词列进报告。
- 两家的数据直接拿来比：卖家精灵是月度，西柚和 ABA 是周度，而且周乘 4.3 不一定等于月（AB machine 两家相差约 8.7 倍）。建议竞价两家可能差一倍，**方向也不固定**：golf 是卖家精灵高，AB machine 是西柚高。
- 被卖家精灵的平均售价带偏：ab workout 的均价 $18.87 被腹肌轮拉低了，但首页前 10 里有 7 个是腹肌机。
- 撞上同名的其他品类：abs 的首页基本是 3D 打印用的 ABS 耗材，只能做精准否定。
- 外语泛词做了词组否定：ejercicios 会挡住 maquina de ejercicios para abdomen（腹肌训练机）。外语泛词要和场景词组成短语再否（如 ejercicios en casa），或者逐条精准否定。
- 只看了几条示例就定了词组否定：词组否定会挡掉全部含这个词根的搜索。要看 `phrase_coverage.csv` 里这个词根挡掉的完整清单再决定。
