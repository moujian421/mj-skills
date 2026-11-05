# brief.json 格式与检查脚本

Claude 写需求时先写 `brief.json`，交给 `scripts/brief_lint.py` 检查，没有错误后再写入飞书。字数、像素宽度、禁用词、层级、参考图数量这些机械检查都交给脚本，不靠 Claude 自己数。

## 命令

```bash
S=~/.claude/skills/mj-picture/scripts
# 检查新写的需求（同时生成字数列、拍摄清单；给了列映射就生成飞书批量写入文件）
python3 $S/brief_lint.py brief.json --out-dir OUT --sheet-id <sheet_id> \
  --cols headline=D,sub=E,body=F,icons=G,count=K,cn=L,composition=M,must_shoot=N,dont=O,evidence=Q
lark-cli sheets +cells-set --spreadsheet-token <T> --writes @OUT/writes.json   # 一次最多 100 项
# 审核飞书上已有的表：先转成 brief.json 再检查（会自己数参考图列里嵌了几张图）
python3 $S/sheet_to_brief.py --token <T> --sheet-id <id> --product product.json > brief.json
```

- 「错误」只来自【底线】规则：主图有字或不随货物品、禁用说法、Not included、A+ alt text、痛点 / 多场景 / 对比缺依据、我方参考图放了竞品图。必须改。
- 「提醒」来自默认规则（字数、层级、图标、参考图数量、格式等）：Claude 按意思判断，有理由不按时在「依据」或「禁用 / 注意」写一句理由。
- `OUT/brief.checked.json` 的 `count` 字段就是表里「字数」列的内容，直接写入，不要手算。
- `OUT/shoot_list.tsv` 是「我方参考图」写了“需另拍”的汇总，补上角度、背景、优先级后就是拍摄清单。
- 图的类型猜错时，用 `--types "副图 6=accessory,M1=aplus_open"` 指定。

## 结构

```json
{
  "product": {
    "model": "AH-GC1", "brand": "AIRHOP",
    "banned_claims": ["one-click fold", "all-terrain"],
    "banned_verbs": ["release", "squeeze", "hold"],
    "accessories": ["Storage compartment", "Adjustable phone mount"]
  },
  "images": [
    {
      "slot": "副图 1", "row": 6, "sheet_id": "8f0935",
      "type": "feature",
      "question": "前轮能转向，也能锁直行",
      "headline": "360° Swivel Front Wheel",
      "sub": "Steer easily, lock it for straight rolling",
      "body": "—",
      "icons": ["360° Swivel", "Locks Straight"],
      "dims": [],
      "cn": "主：…\n副：…\n小：无\n图标：…",
      "make": "实拍合成",
      "composition": "…", "must_shoot": "…", "dont": "…",
      "props": ["golf bag"],
      "ref_comp": ["Tivor #3（360° + Lock 小图）", "findway #2（锁止开关特写）"],
      "ref_own": "说明书 Fig.15", "evidence": "说明书 Fig.15-17；视频 1 0:00-0:33",
      "alt": "", "brand_style": ""
    }
  ]
}
```

| 字段 | 说明 |
|---|---|
| `type` | 副图：`main` `feature` `steps` `accessory` `dimension` `scene` `pain` `multi`；A+：`aplus_open` `aplus_feature` `aplus_steps` `aplus_carousel` `aplus_grid` `aplus_dimension` `aplus_scene` `aplus_compare` `aplus_package` |
| `sub` | 配件汇总图写成清单，每项一行（`\n`） |
| `headline` | A+ 开场两行用 `\n`，第一行只放品牌；轮播每个配件名一行 |
| `dims` | 尺寸和重量标注，不计字数 |
| `make` | `实拍` / `实拍合成` / `AI 生成` |
| `props` | 画面里不随货的物品，有就要在画面或必拍细节里写 Not included |
| `alt` | A+ 必填；轮播每张一条，写成列表 |
| `ai_prompt` | 制作方式是 AI 生成或实拍合成时写：第一行用途（场景生成 / 产品替换 / 局部修改），后面是英文提示词和商品保真规则 |
| `brand_style` | 按某个品牌的实测字号写时填品牌名，这时字数超限只作提醒 |
| `product.accessories` | 按零件清单写，配件汇总图的清单会和它对一遍 |
| `product.banned_verbs` | 有锁定类部件时填，画面文字里出现就提醒 |
| `product.foldable` | 可折叠商品填 true，尺寸图才检查有没有折叠尺寸 |

## 脚本查什么

- 每层单行字符数 + Arial 实测像素宽度（上限见 copy-rules.md），超过 95% 提醒；排两行时每行量像素、总长按团队两行上限；尺寸和重量标注跳过；
- 主图无文字、无不随货物品；副图不四层全满；图标 ≤3 个、≤4 词；场景图只有主标题；配件汇总图（配件 ≥4 个才做）无图标、清单每项一行、不加点、不重复、和零件清单对得上；尺寸图有 dims、可折叠的有折叠尺寸、英制在前；
- 主标题和副标题、小文案，副标题和小文案的用词重复（只是字面初筛）；
- 通用禁用词、A+ 额外禁用词、本款禁用说法、锁定类动词；
- 制作方式、Not included、中文释义每层一行和“无”、竞品参考图 ≥2 张且不同、我方参考图不为空；
- A+ alt text 必填、≤100 字符、包含画面文字；
- AI 生成 / 实拍合成的图位：有没有提示词、有没有商品保真规则、有没有写 no text；主图写了 AI 生成直接报错；
- 生成字数列、拍摄清单、飞书批量写入文件。

脚本查不了的，见 SKILL.md「Claude 自查」。
