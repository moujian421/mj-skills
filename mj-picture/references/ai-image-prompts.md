# AI 生图提示词

Claude 不生成图片，只在需求表里写提示词，交给设计或运营拿去生图工具用。制作方式是「AI 生成」或「实拍合成」（AI 出背景或场景）的图位，在「AI 生图提示词（可选）」列写；实拍图不写。

## 什么时候适合用 AI

- 适合：场景和背景、氛围图、把实拍商品放进新场景（产品替换）、改已有图的局部（换背景、去杂物、补光、加自然接触阴影）。
- 主图、细节特写、尺寸图、操作步骤图：商品必须是实拍，AI 只能做局部修改（补光、阴影、背景清理、给实拍特写配背景底座），不能重绘商品本体、刻度、接口和零件细节。
- 【底线】商品本身以实拍图为准，AI 只负责商品以外的部分。生成结果要按「设计稿审核」逐项对照实物：结构、比例、颜色、材质、零件、Logo、标签文字。

## 图上的文字

生图工具画字容易出乱码、拼错、重叠、发糊。默认**让 AI 只出画面，不带任何文字**，标题、副标题、图标由设计在排版软件里加。提示词里写 `no text, no letters, no logos, no watermark`。确实要 AI 出字时：只用英文，逐字写在引号里，出图后逐字核对拼写。

## 提示词结构

按这个顺序写一段英文，每部分一两句：

1. **商品**：是什么、颜色、材质、关键部件，写明以上传的商品图为准；
2. **场景**：在哪里、谁在用、在做什么（人物、动作、环境要和「画面与构图」一致）；
3. **构图**：画幅比例（副图 4:5、A+ 手机端 4:3、A+ 电脑端约 2.44:1）、机位角度、商品在画面里的位置和大小、给标题留出的空白位置；
4. **光线和镜头**：自然光 / 棚拍光、时间、景深、焦段；
5. **画质**：固定写 `photorealistic, commercial advertising photography, professional studio quality, natural lighting, physically accurate materials, true-to-life reflections, real-world shadows, sharp detail, high resolution`；
6. **风格**：目标市场和品牌调性，例如 `clean, modern, US market lifestyle`；
7. **不要**：`no text, no watermark, no extra products, no distorted hands`，再加画面里不该出现的东西（竞品 Logo、不随货的配件等）；
8. **商品保真规则**：每条提示词最后固定附下面这段。

```
STRICT PRODUCT PRESERVATION RULES
Use ONLY the provided product images as the exact reference.
DO NOT redesign, reinterpret, stylize, modify proportions, change dimensions,
alter color, alter material, add or remove parts, or change logos and labels.
Maintain 100% consistency with the original product.
```

## 产品替换（参考图 + 我方商品图）

用一张竞品或场景参考图的版式，把商品换成我方的：

```
Replace the product in the reference image with the product from the provided product photos.
Keep the composition, camera angle, lighting, depth of field, layout and scene exactly the same.
Only replace the product. [STRICT PRODUCT PRESERVATION RULES]
```

参考图是竞品图时，只借构图和光影；画面里的竞品 Logo、文字、包装都要去掉，不能出现在成品里。

## 局部修改（改已有图）

```
Edit only the [指定区域，如 background / top-left corner / the floor]. 
Keep everything else 100% unchanged. Do not recompose or re-render the product.
[要改成什么]
```

## 写在需求表里的格式

「AI 生图提示词」格子里：第一行写用途（`场景生成` / `产品替换` / `局部修改`），下面是完整英文提示词，最后一段是商品保真规则。需要上传的参考图写在「我方 / 其他参考图」列。

## 例子（结构示意，不是定稿）

```
场景生成
A black three-wheel golf push cart (use the provided product photos as the exact reference) 
standing on a sunlit fairway, a golfer walking beside it holding the handle.
Vertical 4:5 frame, eye-level three-quarter view, cart fills the lower 60% of the frame, 
clear sky in the top 30% left empty for a headline.
Late-afternoon natural sunlight, soft long shadows, shallow depth of field, 50mm lens.
Photorealistic, commercial advertising photography, physically accurate materials, 
true-to-life reflections, real-world shadows, sharp detail, high resolution.
Clean, modern, US golf lifestyle.
No text, no watermark, no other brands' logos, no extra carts.
STRICT PRODUCT PRESERVATION RULES ...
```
