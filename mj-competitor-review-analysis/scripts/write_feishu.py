#!/usr/bin/env python3
"""把 stats.py 生成的表一次写进一个新的飞书多维表格，并建仪表盘（饼图 + 柱状图）。
命令都是固定的，日志写到 WORK/feishu/write.log，只打印成败和读回的条数。

用法:
    python3 write_feishu.py WORK --name "B07YN1W5W3 评论打标 2026-10-30" [--dry-run]
    # 已建好表格、只想补写某张表：--base-token XXX --only 占比汇总

一次分析建一个新多维表格（细分市场不同，不和别的分析合并）。
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

LARK = str(Path.home() / ".npm-global/bin/lark-cli")
GROUPS = ["好评", "中评", "差评", "全部"]


def text(name):
    return {"type": "text", "name": name}


def num(name, precision=0):
    return {"type": "number", "name": name, "style": {"type": "plain", "precision": precision}}


def sel(name, options, multiple=False):
    return {"type": "select", "name": name, "multiple": multiple, "options": [{"name": o} for o in options]}


def check(name):
    return {"type": "checkbox", "name": name}


class Lark:
    def __init__(self, log, dry):
        self.log, self.dry, self.ok, self.fail = log, dry, 0, 0

    def run(self, *args):
        cmd = [LARK, "base", *args, "--as", "user"] + (["--dry-run"] if self.dry else [])
        p = subprocess.run(cmd, capture_output=True, text=True)
        with open(self.log, "a") as f:
            f.write("$ " + " ".join(a if len(a) < 300 else a[:300] + "…" for a in cmd) + "\n")
            f.write(p.stdout[-3000:] + p.stderr[-2000:] + "\n")
        try:
            d = json.loads(p.stdout)
        except json.JSONDecodeError:
            d = {}
        good = p.returncode == 0 and (self.dry or d.get("ok", False))
        self.ok += good
        self.fail += not good
        if not good:
            print(f"失败：{args[0]} {args[1:3]}（详见日志）", file=sys.stderr)
        return d


def find(d, key):
    """在返回 JSON 里递归找第一个 key。"""
    if isinstance(d, dict):
        if key in d:
            return d[key]
        for v in d.values():
            r = find(v, key)
            if r:
                return r
    if isinstance(d, list):
        for v in d:
            r = find(v, key)
            if r:
                return r
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("--name", required=True)
    ap.add_argument("--base-token")
    ap.add_argument("--only")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    fd = Path(a.work) / "feishu"
    log = fd / "write.log"
    log.write_text("")
    L = Lark(log, a.dry_run)
    J = {k: json.loads((fd / f"{k}.json").read_text()) for k in ["detail", "taxonomy", "share", "l1", "split"]}

    neg = [t["标签"] for t in J["taxonomy"] if t["正负"] == "负"] + ["其他（负面）"]
    pos = [t["标签"] for t in J["taxonomy"] if t["正负"] == "正"] + ["其他（正面）"]
    l1s = sorted({t["一级分类"] for t in J["taxonomy"]} | {"其他"})
    all_tags = neg + pos

    share_fields = [text("标签"), sel("分组", GROUPS), sel("正负", ["正", "负"]), sel("一级分类", l1s),
                    num("评论数"), num("组内评论数"), num("占比(%)", 1), num("提及构成(%)", 1), num("排名")]
    tables = {
        "评论明细": ([text("评论ID"), text("ASIN"), {"type": "datetime", "name": "日期"}, num("星级"),
                     sel("分组", GROUPS[:3]), text("变体"), check("VP"), check("Vine"), sel("图片/视频", ["图片", "视频"]),
                     text("英文标题"), text("英文正文"), text("中文翻译"), text("摘要"),
                     sel("负面标签", neg, True), sel("正面标签", pos, True), sel("一级分类", l1s, True),
                     text("依据"), text("建议新标签")], J["detail"]),
        "占比汇总": (share_fields, J["share"]),
        "一级分类汇总": ([text("一级分类"), sel("分组", GROUPS[:3]), sel("正负", ["正", "负"]),
                        num("评论数"), num("组内评论数"), num("占比(%)", 1)], J["l1"]),
        "拆分对比": ([text("标签"), text("维度"), text("维度值")] + share_fields[1:], J["split"]),
        "标签库": ([text("标签"), text("一级分类"), sel("正负", ["正", "负"]), text("定义"), text("不归入")], J["taxonomy"]),
    }
    for r in J["detail"]:
        r["日期"] = r["日期"] + " 00:00" if r["日期"] else None
        if not r["图片/视频"]:
            r["图片/视频"] = None
        for k in ("分组",):
            r[k] = [r[k]] if r[k] else []
    for k in ("share", "split", "l1"):
        for r in J[k]:
            for f in ("分组", "正负", "一级分类"):
                if f in r:
                    r[f] = [r[f]]
    for r in J["taxonomy"]:
        r["正负"] = [r["正负"]]
    for r in J["detail"]:
        if r["图片/视频"]:
            r["图片/视频"] = [r["图片/视频"]]

    # 1. 建多维表格（第一张表在建表格时一起建）
    base, url = a.base_token, None
    names = [n for n in tables if not a.only or n == a.only]
    if not base:
        first = names[0]
        d = L.run("+base-create", "--name", a.name, "--time-zone", "Asia/Shanghai",
                  "--table-name", first, "--fields", json.dumps(tables[first][0], ensure_ascii=False))
        base = find(d, "base_token") or ("DRYRUN" if a.dry_run else None)
        url = find(d, "url")
        url = url if str(url).startswith("http") else None
        if not base:
            sys.exit("建多维表格失败，见日志")
        rest = names[1:]
    else:
        rest = names
    for n in rest:
        L.run("+table-create", "--base-token", base, "--name", n,
              "--fields", json.dumps(tables[n][0], ensure_ascii=False))

    # 2. 写记录（明细带长文本，每批 100 条；其他每批 200 条）
    for n in names:
        rows = tables[n][1]
        size = 100 if n == "评论明细" else 200
        for i in range(0, len(rows), size):
            L.run("+record-batch-create", "--base-token", base, "--table-id", n,
                  "--json", json.dumps({"create_records": rows[i:i + size]}, ensure_ascii=False))

    # 3. 仪表盘：饼图看提及构成（相加 100%），柱状图看占比（评论里有多少比例提到）
    if not a.only:
        d = L.run("+dashboard-create", "--base-token", base, "--name", "好评差评细分")
        dash = find(d, "dashboard_id") or "DRYRUN"

        def flt(g, pol):
            return {"conjunction": "and", "conditions": [
                {"field_name": "分组", "operator": "is", "value": g},
                {"field_name": "正负", "operator": "is", "value": pol}]}

        blocks = [("说明", "text", {"text": "## 口径\n- 好评 4–5 星，中评 3 星，差评 1–2 星\n"
                                          "- **柱状图 = 占比**：该组里提到这个标签的评论数 ÷ 该组评论数，一条评论可有多个标签，相加会超过 100%\n"
                                          "- **饼图 = 提及构成**：该标签提及次数 ÷ 该组同方向的全部提及次数，相加 = 100%"})]
        for g, pol, title in [("差评", "负", "差评问题"), ("好评", "正", "好评卖点")]:
            blocks.append((f"{title}占比（柱状图）", "column", {
                "table_name": "占比汇总", "series": [{"field_name": "占比(%)", "rollup": "SUM"}],
                "group_by": [{"field_name": "标签", "mode": "integrated", "sort": {"type": "value", "order": "desc"}}],
                "filter": flt(g, pol)}))
            blocks.append((f"{title}提及构成（饼图）", "pie", {
                "table_name": "占比汇总", "series": [{"field_name": "评论数", "rollup": "SUM"}],
                "group_by": [{"field_name": "标签", "mode": "integrated"}], "filter": flt(g, pol)}))
        blocks.append(("差评一级分类占比（柱状图）", "column", {
            "table_name": "一级分类汇总", "series": [{"field_name": "占比(%)", "rollup": "SUM"}],
            "group_by": [{"field_name": "一级分类", "mode": "integrated", "sort": {"type": "value", "order": "desc"}}],
            "filter": flt("差评", "负")}))
        for name, typ, cfg in blocks:  # 同一个仪表盘的组件要按顺序建，不能并行
            L.run("+dashboard-block-create", "--base-token", base, "--dashboard-id", dash,
                  "--name", name, "--type", typ, "--data-config", json.dumps(cfg, ensure_ascii=False))

    # 4. 读回条数
    back = {}
    if not a.dry_run:
        d = L.run("+table-list", "--base-token", base)
        for t in find(d, "tables") or []:
            back[t["name"]] = t.get("records_count")
    result = {"base_token": base, "url": url or f"https://cathug-inc.feishu.cn/base/{base}",
              "commands_ok": L.ok, "commands_failed": L.fail, "log": str(log),
              "readback": {n: {"应写": len(tables[n][1]), "读回": back.get(n)} for n in names}}
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
