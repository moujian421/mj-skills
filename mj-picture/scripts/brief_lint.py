#!/usr/bin/env python3
"""MJ-Picture 图片需求自动检查。

只有【底线】规则（违规、写错事实、误导买家）报「错误」；默认规则只「提醒」，有理由可以不按。

用法：
  python3 brief_lint.py brief.json [--out-dir DIR] [--sheet-id ID] [--cols field=列,...]

brief.json 格式见 references/brief-schema.md。
输出：
  - 终端：错误（必须改）和提醒（Claude 按意思再判断）
  - DIR/brief.checked.json：补好「字数」count 字段的 brief
  - DIR/shoot_list.tsv：所有“需另拍”汇总成的拍摄清单
  - DIR/writes.json：给了 --sheet-id 和 --cols 时，生成 lark-cli +cells-set --writes 用的批量写入文件
退出码：有错误时为 1。
"""
import argparse, json, os, re, sys

try:
    from PIL import ImageFont
except ImportError:  # 没有 Pillow 时只按字符数检查
    ImageFont = None

FONT_DIR = "/System/Library/Fonts/Supplemental"
_fonts = {}


def px(text, size, bold=False):
    """Arial 实测像素宽度；没有字体时返回 None。"""
    if ImageFont is None:
        return None
    key = (size, bold)
    if key not in _fonts:
        path = os.path.join(FONT_DIR, "Arial Bold.ttf" if bold else "Arial.ttf")
        if not os.path.exists(path):
            return None
        _fonts[key] = ImageFont.truetype(path, size)
    return round(_fonts[key].getlength(text))


# 每层：(画布字号, 粗体, 单行字符上限, 像素上限)
LIMITS = {
    "pt": {  # 副图 1200x1500
        "headline": (72, True, 25, 880),
        "sub": (48, False, 42, 915),
        "body": (40, False, 52, 935),
        "icon": (36, False, 22, None),
    },
    "aplus": {  # A+ 手机端 600x450
        "headline": (40, True, 22, 440),
        "sub": (26, False, 38, 460),
        "body": (20, False, 50, 470),
        "icon": (18, False, 20, None),
    },
}
ICON_MAX_WORDS = 4
ICON_MAX_PT = 3
TWO_LINE_MAX = {"headline": 32, "sub": 50, "body": 65}  # 团队标准，排两行时的总长上限
ACCESSORY_MIN = 4
LIST_ITEM_MAX_WORDS, LIST_ITEM_MAX_CHARS = 4, 22
APLUS_OPEN_LINE2 = (34, True, 29, 500)
CAROUSEL_HALF = (24, True, None, 260)
ALT_MAX = 100
MAKE_TYPES = ("实拍", "实拍合成", "AI 生成")
LAYER_CN = {"headline": "主", "sub": "副", "body": "小", "icons": "图标"}

TYPES_PT = {"main", "feature", "steps", "accessory", "dimension", "scene", "pain", "multi"}
TYPES_APLUS = {"aplus_open", "aplus_carousel", "aplus_grid", "aplus_feature", "aplus_steps",
               "aplus_dimension", "aplus_scene", "aplus_compare", "aplus_package"}

# 所有图都不能写
BANNED_ALL = [r"\bbest\b", r"#\s?1\b", r"\bno\.?\s?1\b", r"\bnumber one\b", r"\bpremium\b",
              r"\bcheapest\b", r"\bsale\b", r"\bdiscount", r"%\s?off", r"\$\s?\d", r"\bdeals?\b",
              r"limited time", r"black friday", r"prime day", r"cyber monday"]
# A+ 额外禁止
BANNED_APLUS = [r"guarantee", r"warrant", r"refund", r"\breturns?\b", r"free shipping",
                r"\bships?\b", r"https?://", r"www\.", r"\.com\b", r"\bqr\b", r"\breviews?\b",
                r"\brated\b", r"\bstars?\b", r"customers? love", r"\bgift\b", r"buy now",
                r"order now", r"\bshop now\b"]
LIST_BULLETS = re.compile(r"^\s*[•·\-\*–—▪●✓✔]|[;；|｜,，]\s*\S")
STOP = set("a an the and or for with to of on in at by your you it its is are be from into "
           "that this as up off out over all any each every per".split())
EMPTY = {"", "—", "-", "无", None}


def empty(v):
    if isinstance(v, list):
        return all(empty(x) for x in v)
    return (v.strip() if isinstance(v, str) else v) in EMPTY


def words(s):
    return len(s.split())


def lines(s):
    return [l for l in str(s).split("\n") if l.strip()]


def keyterms(s):
    toks = re.findall(r"[a-z0-9°]+", s.lower())
    out = set()
    for t in toks:
        if t in STOP or len(t) < 3 and not t[0].isdigit():
            continue
        out.add(t.rstrip("s") if len(t) > 4 else t)
    return out


class Report:
    def __init__(self):
        self.items = []

    def err(self, slot, msg):
        self.items.append(("错误", slot, msg))

    def warn(self, slot, msg):
        self.items.append(("提醒", slot, msg))

    @property
    def n_err(self):
        return sum(1 for k, _, _ in self.items if k == "错误")


DIM_RE = re.compile(r"\d+(\.\d+)?\s*(x|×)\s*\d|net weight|\d\s*(lb|in|kg|cm)\b", re.I)


def check_line(r, slot, layer, text, lim, soft):
    size, bold, cmax, pmax = lim
    if DIM_RE.search(text):  # 尺寸和重量标注不计字数
        return
    say = r.warn  # 字数是默认规则，只提醒
    two = TWO_LINE_MAX.get(layer)
    if "\n" in text and two and len(text.replace("\n", " ")) > two:
        say(slot, f"{LAYER_CN.get(layer, layer)}排两行，总长 {len(text)} 字符 > 两行上限 {two}：{text!r}")
    for ln in lines(text):
        if cmax and len(ln) > cmax and "\n" not in text:
            say(slot, f"{LAYER_CN.get(layer, layer)} {len(ln)} 字符 > {cmax}：{ln!r}")
        w = px(ln, size, bold)
        if pmax and w is not None and w > pmax:
            say(slot, f"{LAYER_CN.get(layer, layer)} {w}px > {pmax}px（Arial {'粗体 ' if bold else ''}{size}px）：{ln!r}")
        elif pmax and w is not None and w > pmax * 0.95:
            r.warn(slot, f"{LAYER_CN.get(layer, layer)} {w}px 接近上限 {pmax}px：{ln!r}")


def count_str(img):
    parts = []
    t = img.get("type")
    for key, cn in (("headline", "主"), ("sub", "副"), ("body", "小")):
        v = img.get(key, "")
        if empty(v):
            parts.append(f"{cn} 无")
        elif key == "sub" and t == "accessory":
            parts.append(f"副 {len(lines(v))} 项清单")
        elif key == "headline" and t == "aplus_open":
            parts.append("主 " + "、".join(f"{words(l)}/{len(l)}" for l in lines(v)))
        else:
            parts.append(f"{cn} {words(v)}/{len(v)}")
    icons = [i for i in img.get("icons", []) if not empty(i)]
    parts.append("图标 " + ("、".join(f"{words(i)}/{len(i)}" for i in icons) if icons else "无"))
    s = "｜".join(parts)
    if not empty(img.get("dims")):
        s += "｜尺寸 / 重量标注（不计字数）"
    return s


def lint(brief):
    r = Report()
    prod = brief.get("product", {})
    banned_claims = [c.lower() for c in prod.get("banned_claims", [])]
    banned_verbs = [v.lower() for v in prod.get("banned_verbs", [])]
    accessories = [a.strip().lower() for a in prod.get("accessories", [])]
    shoot = []
    pt_stats = {"sub": 0, "body": 0, "icons": 0, "n": 0}

    for img in brief.get("images", []):
        slot = img.get("slot", "?")
        t = img.get("type", "")
        is_aplus = t in TYPES_APLUS
        if t not in TYPES_PT | TYPES_APLUS:
            r.err(slot, f"type 不认识：{t!r}")
            continue
        canvas = "aplus" if is_aplus else "pt"
        soft = bool(img.get("brand_style"))  # 按参考品牌实测字号时，上限只作提醒
        L = LIMITS[canvas]
        h, s, b = (img.get(k, "") or "" for k in ("headline", "sub", "body"))
        icons = [i for i in img.get("icons", []) if not empty(i)]
        alt_v = img.get("alt", "") or ""
        copy_all = " ".join([h, s, b] + icons + (alt_v if isinstance(alt_v, list) else [alt_v]))

        # 主图
        if t == "main":
            if not (empty(h) and empty(s) and empty(b) and not icons):
                r.err(slot, "主图不能放任何文字或图标")
        # 单行长度
        if t == "aplus_open":
            ls = lines(h)
            if len(ls) >= 2:
                for ln in ls[1:]:
                    check_line(r, slot, "headline", ln, APLUS_OPEN_LINE2, soft)
            elif ls:
                r.warn(slot, "A+ 开场主标题只有一行：两行时第一行只放品牌")
            if ls and prod.get("brand") and ls[0].strip().upper() != prod["brand"].upper():
                r.warn(slot, f"A+ 开场第一行应只放品牌 {prod['brand']}：{ls[0]!r}")
        elif t == "aplus_carousel":
            for side in lines(h.replace("｜", "\n")) if not isinstance(img.get("headline"), list) else img["headline"]:
                for ln in lines(side):
                    w = px(ln, *CAROUSEL_HALF[:2])
                    if w and w > CAROUSEL_HALF[3]:
                        r.warn(slot, f"轮播配件名 {w}px > 半幅 260px（粗体 24px 起），需排两行：{ln!r}")
        elif not empty(h):
            check_line(r, slot, "headline", h, L["headline"], soft)
        if not empty(s) and t != "accessory":
            check_line(r, slot, "sub", s, L["sub"], soft)
        if not empty(b):
            check_line(r, slot, "body", b, L["body"], soft)
        dim_icons = [i for i in icons if DIM_RE.search(i)]  # 写在图标位的尺寸标注不计字数
        icons = [i for i in icons if i not in dim_icons]
        for i in icons:
            if words(i) > ICON_MAX_WORDS:
                r.warn(slot, f"图标 {words(i)} 个单词 > {ICON_MAX_WORDS}：{i!r}")
            check_line(r, slot, "icon", i, L["icon"], soft)
        if not is_aplus and len(icons) > ICON_MAX_PT:
            r.warn(slot, f"副图图标 {len(icons)} 个 > {ICON_MAX_PT}")

        # 按类型
        filled = [k for k in ("headline", "sub", "body") if not empty(img.get(k))] + (["icons"] if icons else [])
        if not is_aplus and t != "main" and len(filled) == 4:
            r.warn(slot, "副图四层全满：删掉和其他层重复最多的一层，讲出核心好处的那层留下")
        if t in ("scene", "aplus_scene") and (not empty(s) or not empty(b) or icons):
            r.warn(slot, "场景图只放一句主标题或不放文案")
        if t == "accessory":
            if icons:
                r.warn(slot, "配件汇总图不放图标")
            items = lines(s)
            if accessories and len(accessories) < ACCESSORY_MIN:
                r.warn(slot, f"随货配件只有 {len(accessories)} 个，少于 {ACCESSORY_MIN} 个时默认并进别的图")
            if not items:
                r.warn(slot, "配件汇总图副标题要写成清单")
            low = [x.strip().lower() for x in items]
            if len(set(low)) != len(low):
                r.warn(slot, "清单有重复项")
            for x in items:
                if LIST_BULLETS.search(x):
                    r.warn(slot, f"清单项不加点或分隔符，每项单独一行：{x!r}")
                if words(x) > LIST_ITEM_MAX_WORDS or len(x) > LIST_ITEM_MAX_CHARS:
                    r.warn(slot, f"清单项超限（≤{LIST_ITEM_MAX_WORDS} 词、≤{LIST_ITEM_MAX_CHARS} 字符）：{x!r}")
            if accessories:
                miss = [a for a in accessories if a not in low]
                if miss:
                    r.warn(slot, f"清单和 product.accessories 对不上，可能漏项：{miss}")
        if t in ("dimension", "aplus_dimension"):
            dims = (img.get("dims") or []) + dim_icons
            if empty(dims):
                r.warn(slot, "尺寸图要写 dims：外形尺寸、品类关键尺寸、净重")
            else:
                d = " ".join(dims).lower()
                if prod.get("foldable") and "fold" not in d:
                    r.warn(slot, "尺寸标注里没看到折叠尺寸（可折叠商品要写展开和折叠）")
                for x in dims:
                    if re.search(r"\d\s*(cm|kg)\b", x) and not re.search(r"\d\s*(in|lb)\b", x):
                        r.warn(slot, f"尺寸写法：英寸/磅在前，公制放括号里：{x!r}")
        if t in ("pain", "multi") or (t == "aplus_compare"):
            if empty(img.get("evidence")):
                r.err(slot, "痛点对比 / 多场景 / 对比表必须在 evidence 写出处")
        if t in ("feature", "pain", "aplus_feature") and empty(img.get("evidence")):
            r.warn(slot, "功能图没写依据（说明书图号、视频时间点、用户确认日期）")

        # 层级重复（字面初筛，意思上的重复 Claude 还要再看）
        if not empty(h):
            hk = keyterms(h)
            for key, cn in (("sub", "副"), ("body", "小")):
                v = img.get(key, "")
                if not empty(v) and t != "accessory":
                    dup = hk & keyterms(v)
                    if dup:
                        r.warn(slot, f"{cn}和主标题用词重复 {sorted(dup)}：主 {h!r} / {cn} {v!r}")
        if not empty(s) and not empty(b) and t != "accessory":
            dup = keyterms(s) & keyterms(b)
            if dup:
                r.warn(slot, f"小文案和副标题用词重复 {sorted(dup)}，按意思判断要不要删小文案")

        # 禁用说法
        low_copy = copy_all.lower()
        for pat in BANNED_ALL + (BANNED_APLUS if is_aplus else []):
            m = re.search(pat, low_copy)
            if m:
                r.err(slot, f"禁用说法 {m.group(0)!r}")
        for c in banned_claims:
            if c and c in low_copy:
                r.err(slot, f"本款禁用说法 {c!r}")
        on_image = " ".join([h, s, b] + icons).lower()  # 动词只查画面文字，不查 alt
        for v in banned_verbs:
            if re.search(rf"\b{re.escape(v)}(s|es|ing|ed)?\b", on_image):
                r.warn(slot, f"动词 {v!r}：锁定类部件用 flip / lock，不用 release / squeeze / hold")

        # 画面
        make = (img.get("make") or "").strip()
        if make not in MAKE_TYPES:
            r.warn(slot, f"make 要写 {' / '.join(MAKE_TYPES)}，现在是 {make!r}")
        props = [p for p in img.get("props", []) if not empty(p)]
        comp = img.get("composition", "") or ""
        ctx = (comp + (img.get("must_shoot") or "")).lower()
        if props and "not included" not in ctx and not ("不随货" in ctx and "标" in ctx):
            r.err(slot, f"画面有不随货物品 {props}，画面或必拍细节要写 Not included 角标")
        if t == "main" and props:
            r.err(slot, f"主图不能放不随货的东西：{props}")

        # AI 生图提示词
        prompt = img.get("ai_prompt", "") or ""
        if t == "main" and make == "AI 生成":
            r.err(slot, "主图要用实拍商品图，AI 只能做局部修改，制作方式不能是 AI 生成")
        if make in ("AI 生成", "实拍合成"):
            if empty(prompt):
                r.warn(slot, f"制作方式是 {make}，没写 ai_prompt（见 ai-image-prompts.md）")
            else:
                pl = prompt.lower()
                if "product preservation" not in pl:
                    r.err(slot, "AI 提示词缺商品保真规则（STRICT PRODUCT PRESERVATION RULES）")
                if "no text" not in pl and "text" not in pl:
                    r.warn(slot, "AI 提示词没写 no text：默认让 AI 只出画面，文字由设计后加")

        # A+
        if is_aplus:
            alts = img.get("alt") if isinstance(img.get("alt"), list) else [img.get("alt", "")]
            for a in alts:
                if empty(a):
                    r.err(slot, "A+ 缺 alt text")
                elif len(a) > ALT_MAX:
                    r.err(slot, f"alt text {len(a)} 字符 > {ALT_MAX}")
            if not empty(h) and alts and not empty(alts[0]):
                miss = keyterms(h) - keyterms(" ".join(a or "" for a in alts))
                if miss:
                    r.warn(slot, f"画面文字没出现在 alt text 里：{sorted(miss)}")

        # 中文释义
        cn = img.get("cn", "") or ""
        if t != "main":
            if "｜" in cn or "|" in cn:
                r.warn(slot, "中文释义每层单独一行，不用“｜”连写")
            cnl = [re.sub(r"^\s*\d+[.、]\s*", "", l).strip() for l in lines(cn)]
            for key, tag in (("headline", "主"), ("sub", "副"), ("body", "小")):
                has = any(l.startswith(tag + "：") for l in cnl)
                if not has:
                    r.warn(slot, f"中文释义缺「{tag}：」一行（不放的层写“{tag}：无”）")
                elif empty(img.get(key)):
                    line = next(l for l in cnl if l.startswith(tag + "："))
                    if not line[len(tag) + 1:].startswith("无"):
                        r.warn(slot, f"{tag}层没放，中文释义应写“{tag}：无”")

        # 参考图
        refs = [x for x in img.get("ref_comp", []) if not empty(x)]
        if "ref_comp_imgs" in img and img["ref_comp_imgs"] < 2:
            r.warn(slot, f"两列竞品参考图只嵌了 {img['ref_comp_imgs']} 张，要 2 张")
        if len(refs) < 2:
            r.warn(slot, f"竞品参考图要 ≥2 张，现在 {len(refs)} 张")
        elif len(set(x.split("（")[0].strip() for x in refs)) < len(refs):
            r.warn(slot, "两列竞品参考图是同一家同一张")
        own = img.get("ref_own", "") or ""
        if empty(own) and not img.get("ref_own_imgs"):
            r.warn(slot, "我方参考图为空：没有素材写“无（需另拍…）”")
        if "竞品" in own:
            r.err(slot, "我方参考图列只放我方素材，不能拿竞品图顶")
        if "需另拍" in own:
            shoot.append({"slot": slot, "what": own, "must": img.get("must_shoot", ""),
                          "make": make, "props": "、".join(props)})

        img["count"] = count_str(img)
        if not is_aplus and t != "main":
            pt_stats["n"] += 1
            pt_stats["sub"] += 0 if empty(s) else 1
            pt_stats["body"] += 0 if empty(b) else 1
            pt_stats["icons"] += 1 if icons else 0

    return r, shoot, pt_stats


def build_writes(brief, sheet_id, colmap):
    out = []
    for img in brief["images"]:
        row = img.get("row")
        if not row:
            continue
        for field, col in colmap.items():
            v = img.get(field, "")
            if isinstance(v, list):
                v = "\n".join(x for x in v if not empty(x)) or "—"
            if v in ("", None):
                v = "—"
            out.append({"sheet_id": img.get("sheet_id", sheet_id), "range": f"{col}{row}",
                        "cells": [[{"value": str(v)}]]})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("brief")
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--sheet-id")
    ap.add_argument("--cols", help="字段=列，逗号分隔，如 count=O,headline=D")
    a = ap.parse_args()
    brief = json.load(open(a.brief, encoding="utf-8"))
    out_dir = a.out_dir or os.path.dirname(os.path.abspath(a.brief))
    os.makedirs(out_dir, exist_ok=True)

    r, shoot, st = lint(brief)
    json.dump(brief, open(os.path.join(out_dir, "brief.checked.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    with open(os.path.join(out_dir, "shoot_list.tsv"), "w", encoding="utf-8") as f:
        f.write("图位\t拍什么（我方参考图列）\t必拍细节\t制作方式\t不随货物品\n")
        for x in shoot:
            f.write("\t".join(str(x[k]).replace("\n", " ") for k in ("slot", "what", "must", "make", "props")) + "\n")
    if a.sheet_id and a.cols:
        colmap = dict(p.split("=", 1) for p in a.cols.split(","))
        writes = build_writes(brief, a.sheet_id, colmap)
        json.dump(writes, open(os.path.join(out_dir, "writes.json"), "w", encoding="utf-8"), ensure_ascii=False)
        print(f"writes.json：{len(writes)} 格（lark-cli sheets +cells-set --writes 一次最多 100 项）")

    if ImageFont is None:
        print("注意：没有 Pillow，只按字符数检查，没量像素")
    for kind, slot, msg in r.items:
        print(f"[{kind}] {slot}：{msg}")
    n_warn = len(r.items) - r.n_err
    print(f"\n共 {len(brief.get('images', []))} 张；错误 {r.n_err}，提醒 {n_warn}；"
          f"副图 {st['n']} 张中 副标题 {st['sub']}、小文案 {st['body']}、图标 {st['icons']}；"
          f"需另拍 {len(shoot)} 项 → shoot_list.tsv")
    sys.exit(1 if r.n_err else 0)


if __name__ == "__main__":
    main()
