#!/usr/bin/env python3
"""用固定指令让 DeepSeek（opencode）逐条给评论打标，校验后落盘。DeepSeek 不通时改用 agy。

用法:
    python3 tag_reviews.py WORK TAXONOMY.md --product "EVA 拼接泡沫地垫（家用健身/儿童爬行）"
        [--batch 30] [--parallel 3] [--only-ids ids.txt]
    中断后直接重跑会接着做没打完的；--only-ids 给出的 id 会删掉旧结果重打（改了标签库后用）。
    统计和抽查只针对本次涉及的评论（传了 --only-ids 时只算这些）。

输入:  WORK/tag_input.tsv（merge_reviews.py 生成）
输出:  WORK/tags.jsonl   {"id","zh","summary","points":[{"tag","quote"}],"new_tag":""}
       WORK/tag_failed.txt  两次都没通过校验的 id（Claude 自己补或改指令重跑）
       WORK/tag_sample.txt  随机 8% 的抽查样本（原文 + 标签），Claude 必须亲自看
只打印统计。指令是写死的，不要让子 agent 或模型自己组织指令。
"""
import argparse
import json
import random
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

OC = "/Applications/OpenCode.app/Contents/Resources/opencode-cli"
OC_DIR = Path.home() / ".opencode-offload"     # 这里的 opencode.json 禁止终端命令和写文件，必须在这里跑
AGY = Path.home() / ".local/bin/agy"
AGY_DIR = Path.home() / ".gemini-offload"
OTHER_NEG, OTHER_POS = "其他（负面）", "其他（正面）"


def load_taxonomy(path):
    """读标签库的 markdown 表：| 一级 | 标签 | 正负 | 定义 | 不归入 |"""
    tags = []
    for line in Path(path).read_text().splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 5 and cells[2] in ("正", "负"):
            tags.append({"l1": cells[0], "tag": cells[1], "pol": cells[2], "def": cells[3], "not": cells[4]})
    names = [t["tag"] for t in tags]
    dup = {n for n in names if names.count(n) > 1}
    if dup:
        sys.exit(f"标签库里有重名标签：{dup}")
    return tags


def build_prompt(tags, product, rows):
    lib = "\n".join(f"- {t['tag']}（{t['pol']}面｜{t['l1']}）：{t['def']}" + (f"；不归入：{t['not']}" if t["not"] and t["not"] != "—" else "")
                    for t in tags)
    data = "\n".join(f"{i}\t{t}" for i, t in rows)
    return f"""你是亚马逊评论打标员。产品：{product}。
下面每行是一条评论：id<TAB>[星级] 标题 | 正文（多为英文）。对每条评论：
1. zh：把标题和正文译成通顺的中文（标题和正文之间用换行符 \\n 隔开）。
2. summary：20 个字以内的中文摘要。
3. points：找出评论里每一个对产品的具体评价（夸的和骂的都要），每个评价配一个标签库里的标签，quote 写评论里支撑它的原文短句（英文原词，不超过 15 个词）。
   - 一条评论可以有多个标签；同一个标签在一条评论里只写一次。
   - 只用标签库里的标签名，一字不改。正面评价只能用“正”标签，负面只能用“负”标签。
   - 只谈物流、客服、退款的，也用对应标签；和产品无关、看不出评价什么的（如只写 "ok"、"good"），points 写 []。
   - 评价不在标签库里的，用“{OTHER_NEG}”或“{OTHER_POS}”，并在 new_tag 里写一个建议的新标签名（6 个字以内）；否则 new_tag 写 ""。
4. 不要因为星级高就只找优点，也不要因为星级低就只找缺点。

标签库：
{lib}
- {OTHER_NEG}（负面）：不在上面任何负面标签里的问题
- {OTHER_POS}（正面）：不在上面任何正面标签里的优点

输出格式：每条评论输出一行 JSON，保留原 id，按输入顺序，例如
{{"id":"R00001","zh":"标题\\n正文","summary":"拼接处容易散开","points":[{{"tag":"拼接不牢/易散开","quote":"comes apart easily"}}],"new_tag":""}}
只输出 JSONL，不要解释，不要代码块标记，不要读写任何文件，不要运行任何命令或工具。

=== 数据开始 ===
{data}
=== 数据结束 ==="""


def run_deepseek(prompt):
    p = subprocess.run([OC, "run", "-m", "opencode/deepseek-v4.1-flash-free", "--format", "json", prompt],
                       cwd=OC_DIR, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=900)
    text, used_tool = [], False
    for line in p.stdout.splitlines():
        try:
            part = json.loads(line).get("part") or {}
        except json.JSONDecodeError:
            continue
        if part.get("type") == "text" and part.get("text"):
            text.append(part["text"])
        elif part.get("type") == "tool":
            used_tool = True
    if used_tool:
        print("警告：DeepSeek 在打标时调用了工具，这批结果作废", file=sys.stderr)
        return ""
    return "\n".join(text)


def run_agy(prompt):
    p = subprocess.run([str(AGY), "-p", prompt, "--model", "gemini-3.8-flash-medium", "--output-format", "json"],
                       cwd=AGY_DIR, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=900)
    try:
        d = json.loads(p.stdout)
        return d.get("response", "") if d.get("status") == "SUCCESS" else ""
    except json.JSONDecodeError:
        return ""


def parse(text, want_ids, valid):
    """返回 {id: 合格结果}，不合格的直接丢掉，交给下一轮重跑。"""
    ok = {}
    for line in re.sub(r"\x1b\[[0-9;]*m", "", text).splitlines():
        line = line.strip().strip("`")
        if not line.startswith("{"):
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        i = o.get("id")
        pts = o.get("points")
        if i not in want_ids or not isinstance(pts, list) or not o.get("zh"):
            continue
        clean_pts, bad = [], False
        for pt in pts:
            if not isinstance(pt, dict) or pt.get("tag") not in valid:
                bad = True
                break
            if pt["tag"] not in [c["tag"] for c in clean_pts]:
                clean_pts.append({"tag": pt["tag"], "quote": str(pt.get("quote", ""))[:200]})
        if bad:
            continue
        ok[i] = {"id": i, "zh": o["zh"], "summary": str(o.get("summary", ""))[:40],
                 "points": clean_pts, "new_tag": str(o.get("new_tag") or "")}
    return ok


def run_batch(args):
    tags, product, rows, valid, runner = args
    out = parse(runner(build_prompt(tags, product, rows)), {i for i, _ in rows}, valid)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("taxonomy")
    ap.add_argument("--product", required=True)
    ap.add_argument("--batch", type=int, default=30)
    ap.add_argument("--parallel", type=int, default=3)
    ap.add_argument("--only-ids")
    a = ap.parse_args()
    work = Path(a.work)
    tags = load_taxonomy(a.taxonomy)
    valid = {t["tag"] for t in tags} | {OTHER_NEG, OTHER_POS}

    rows = [l.rstrip("\n").split("\t", 1) for l in open(work / "tag_input.tsv") if "\t" in l]
    if a.only_ids:
        keep = set(Path(a.only_ids).read_text().split())
        rows = [r for r in rows if r[0] in keep]
    out_f = work / "tags.jsonl"
    done = {}
    if out_f.exists():
        for l in open(out_f):
            o = json.loads(l)
            done[o["id"]] = o
    if a.only_ids:  # 指定的 id 一律重打：先从结果里删掉旧的
        for i in keep:
            done.pop(i, None)
        with open(out_f, "w") as f:
            for o in done.values():
                f.write(json.dumps(o, ensure_ascii=False) + "\n")
    todo = [r for r in rows if r[0] not in done]
    print(f"标签 {len(valid)} 个；待打标 {len(todo)} 条（已有 {len(done)} 条）", file=sys.stderr)

    # 第 1 轮 DeepSeek；没通过的再用 DeepSeek 跑一轮（小批）；还不行换 agy
    for rnd, (runner, size) in enumerate([(run_deepseek, a.batch), (run_deepseek, 10), (run_agy, 20)], 1):
        if not todo:
            break
        batches = [todo[i:i + size] for i in range(0, len(todo), size)]
        with ThreadPoolExecutor(a.parallel) as ex:
            for res in ex.map(run_batch, [(tags, a.product, b, valid, runner) for b in batches]):
                done.update(res)
                with open(out_f, "a") as f:
                    for o in res.values():
                        f.write(json.dumps(o, ensure_ascii=False) + "\n")
        todo = [r for r in todo if r[0] not in done]
        print(f"第 {rnd} 轮（{runner.__name__}）后剩 {len(todo)} 条", file=sys.stderr)

    (work / "tag_failed.txt").write_text("\n".join(i for i, _ in todo) + ("\n" if todo else ""))

    # 统计和抽查样本
    allr = [done[i] for i, _ in rows if i in done]
    n_pts = sum(len(o["points"]) for o in allr)
    other = sum(1 for o in allr for p in o["points"] if p["tag"] in (OTHER_NEG, OTHER_POS))
    empty = sum(1 for o in allr if not o["points"])
    new_tags = {}
    for o in allr:
        if o["new_tag"]:
            new_tags[o["new_tag"]] = new_tags.get(o["new_tag"], 0) + 1
    text = dict(rows)
    random.seed(42)
    sample = random.sample(allr, max(1, round(len(allr) * 0.08))) if allr else []
    with open(work / "tag_sample.txt", "w") as f:
        for o in sample:
            f.write(f"{o['id']}\t{text[o['id']][:600]}\n  → {[p['tag'] for p in o['points']]}\n\n")
    print(json.dumps({
        "tagged": len(allr), "failed": len(todo), "points": n_pts,
        "other_share_of_points": round(other / n_pts, 3) if n_pts else 0,
        "no_point_reviews": empty,
        "suggested_new_tags": dict(sorted(new_tags.items(), key=lambda x: -x[1])[:20]),
        "sample_file": str(work / "tag_sample.txt"), "sample_size": len(sample),
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
