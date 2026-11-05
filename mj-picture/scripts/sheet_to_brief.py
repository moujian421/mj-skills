#!/usr/bin/env python3
"""把飞书上已有的图片需求表（lark-cli +csv-get 导出的 annotated_csv）转成 brief.json，交给 brief_lint.py 检查。

用法：
  python3 sheet_to_brief.py --token T --sheet-id S [--range A1:U40] [--product product.json] \
      [--types "副图 6=accessory,M1=aplus_open"] > brief.json
  （给 --token 时脚本自己用 lark-cli 读表，并数三列参考图里嵌了几张图；也可以传本地 csv 路径，但那样看不到嵌图）

按表头名找列（图位/模块、主标题、副标题、小文案、图标、我方参考图、中文释义、画面与构图、必拍细节、参考竞品图/A+、依据、alt text），
图的类型按「本张要回答的问题 / 类型」列里的关键词猜，猜不准用 --types 指定。
"""
import argparse, csv, io, json, re, subprocess, sys

HEAD = {
    "slot": ("图位", "模块"), "question": ("本张要回答的问题",), "kind_hint": ("类型",),
    "headline": ("主标题",), "sub": ("副标题",), "body": ("小文案",), "icons": ("图标",),
    "ref_own": ("我方",), "cn": ("中文释义",), "composition": ("画面与构图",),
    "must_shoot": ("必拍细节",), "dont": ("禁用",), "ref_text": ("参考竞品",),
    "evidence": ("依据",), "alt": ("alt text",), "count_old": ("字数",), "ai_prompt": ("AI 生图",),
}
DIM_RE = re.compile(r"\d+(\.\d+)?\s*(x|×)\s*\d|net weight|\d\s*(lb|in)\b", re.I)


def guess_type(slot, hint, sub):
    s, h = slot.lower(), hint
    aplus = slot.strip().upper().startswith("M")
    if "主图" in slot or "main" in s:
        return "main"
    if aplus:
        for k, t in (("开场", "aplus_open"), ("轮播", "aplus_carousel"), ("宫格", "aplus_grid"),
                     ("尺寸", "aplus_dimension"), ("步骤", "aplus_steps"), ("对比", "aplus_compare"),
                     ("包装", "aplus_package"), ("场景", "aplus_scene")):
            if k in h:
                return t
        return "aplus_feature"
    if "尺寸" in h or "规格" in h:
        return "dimension"
    if "场景" in h or "实景" in h:
        return "scene"
    if len([l for l in sub.split("\n") if l.strip()]) >= 3:
        return "accessory"
    if "折叠" in h or "步骤" in h or "安装" in h:
        return "steps"
    return "feature"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="?")
    ap.add_argument("--token")
    ap.add_argument("--range", default="A1:U40")
    ap.add_argument("--sheet-id", default="")
    ap.add_argument("--product")
    ap.add_argument("--types", default="")
    a = ap.parse_args()
    if a.token:
        t = subprocess.run(["lark-cli", "sheets", "+csv-get", "--spreadsheet-token", a.token, "--sheet-id",
                            a.sheet_id, "--range", a.range, "-q", ".data.annotated_csv"],
                           capture_output=True, text=True, check=True).stdout
    else:
        t = open(a.csv, encoding="utf-8").read()
    if t.startswith('"'):
        t = json.loads(t)
    rownos = [int(m) for m in re.findall(r"^\[row=(\d+)\]", t, flags=re.M)]
    t = re.sub(r"^\[row=\d+\]", "", t, flags=re.M)
    rows = list(csv.reader(io.StringIO(t)))
    hi = next(i for i, r in enumerate(rows) if any(c.strip().startswith("主标题") for c in r))
    head = [c.strip() for c in rows[hi]]
    col = {}
    for f, keys in HEAD.items():
        for j, h in enumerate(head):
            if any(k in h for k in keys):
                col.setdefault(f, j)
    imgcols = [j for j, h in enumerate(head) if h.endswith("参考图") or h.endswith("参考图 2")]
    imgs = {}
    if a.token and imgcols and rownos:
        L = lambda j: (chr(65 + j) if j < 26 else "A" + chr(65 + j - 26))
        r0, r1 = rownos[hi + 1], rownos[-1]
        rng = f"{L(min(imgcols))}{r0}:{L(max(imgcols))}{r1}"
        out = subprocess.run(["lark-cli", "sheets", "+cells-get", "--spreadsheet-token", a.token, "--sheet-id",
                              a.sheet_id, "--range", rng, "-q",
                              '[.data.ranges[0].cells[] | map((.rich_text//[]) | map(select(.type=="embed-image")) | length)]'],
                             capture_output=True, text=True).stdout
        try:
            for k, row in enumerate(json.loads(out)):
                imgs[r0 + k] = {head[min(imgcols) + q]: n for q, n in enumerate(row)}
        except Exception:
            print("注意：没读到嵌图数量", file=sys.stderr)
    overrides = dict(p.split("=", 1) for p in a.types.split(",") if "=" in p)
    images = []
    for i, r in enumerate(rows[hi + 1:], start=hi + 1):
        g = lambda f: (r[col[f]].strip() if f in col and col[f] < len(r) else "")
        slot = g("slot")
        if not slot or not g("headline") and not g("question") and not g("kind_hint"):
            continue
        img = {k: g(k) for k in ("slot", "question", "headline", "sub", "body", "ref_own", "cn",
                                 "composition", "must_shoot", "dont", "evidence", "count_old", "ai_prompt")}
        img["row"] = rownos[i] if i < len(rownos) else i + 1
        img["sheet_id"] = a.sheet_id
        img["icons"] = [re.sub(r"^\s*[•·\-\*]\s*", "", x) for x in g("icons").split("\n") if x.strip() not in ("", "—")]
        img["ref_comp"] = [x.strip() for x in re.split(r"[、；;]", g("ref_text")) if x.strip()]
        cnt = imgs.get(img["row"])
        if cnt is not None:
            img["ref_comp_imgs"] = sum(1 for h, n in cnt.items() if h.startswith("竞品") and n)
            img["ref_own_imgs"] = sum(n for h, n in cnt.items() if h.startswith("我方"))
        comp = img["composition"]
        m = re.match(r"\s*(实拍合成|实拍|AI ?生成)", comp)
        img["make"] = (m.group(1).replace("AI生成", "AI 生成") if m else "")
        img["type"] = overrides.get(slot) or guess_type(slot, g("question") + g("kind_hint"), img["sub"])
        if img["type"] == "aplus_carousel":
            sides = []
            for ln in img["headline"].split("\n"):
                ln = re.sub(r"^\s*\d+[.、]\s*", "", ln)
                sides += [x.strip() for x in ln.split(" / ") if x.strip()]
            img["headline"] = "\n".join(sides)
            img["alt"] = [re.sub(r"^\s*\d+[.、]\s*", "", x) for x in g("alt").split("\n") if x.strip()]
        elif "alt" in col:
            img["alt"] = g("alt")
        if img["type"] in ("dimension", "aplus_dimension"):
            src = "\n".join([img["headline"], img["sub"], img["body"], comp])
            img["dims"] = [l.strip() for l in re.split(r"[\n；;]", src) if DIM_RE.search(l)]
        if "不随货" in comp + img["must_shoot"] or "not included" in (comp + img["must_shoot"]).lower():
            img["props"] = ["（表里提到不随货物品）"]
        images.append(img)
    product = json.load(open(a.product, encoding="utf-8")) if a.product else {}
    json.dump({"product": product, "images": images}, sys.stdout, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
