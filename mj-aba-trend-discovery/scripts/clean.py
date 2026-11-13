#!/usr/bin/env python3
"""第二道清洗：让 Gemini Flash 给候选词打标签（keep/brand/ip/sports/risk/holiday/junk），剔除非 keep。
用法: clean.py RUN [模型，默认 gemini-3.8-flash-medium] [--reuse 按关键词复用已有标签，只给新词打标，并套用 overrides.json]
输入 RUN/candidates.csv；输出 RUN/clean_tags.jsonl、RUN/candidates_clean.csv、RUN/candidates_removed.csv，只打印统计。
DeepSeek 不可用时用 agy；数据约 250 行一批全部发出。"""
import csv, json, os, re, subprocess, sys
from pathlib import Path
RUN = Path(sys.argv[1]).resolve(); MODEL = sys.argv[2] if len(sys.argv) > 2 else "gemini-3.8-flash-medium"
SKILL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agylib import agy_bin
rows = list(csv.DictReader(open(RUN / "candidates.csv", encoding="utf-8")))
if not rows:
    print("没有候选词，跳过清洗"); sys.exit(0)
# 品牌信息从 screened.json 补
br = {it["keyword"]: [b for b in (it.get("top3Brands") or []) if b] for it in json.load(open(RUN / "screened.json", encoding="utf-8"))["keep"]}
tags = {}
if len(sys.argv) > 3 and sys.argv[3] == "--reuse" and (RUN / "clean_tags.jsonl").exists():
    idx = {r["keyword"]: str(i) for i, r in enumerate(rows)}   # 按关键词复用：候选表变了行号也会变
    for l in open(RUN / "clean_tags.jsonl", encoding="utf-8"):
        o = json.loads(l)
        if o["tag"] != "未标" and not o.get("manual") and o.get("keyword") in idx:
            o["id"] = idx[o["keyword"]]; tags[o["id"]] = o
TAGS = {"keep", "brand", "ip", "sports", "risk", "holiday", "junk", "category"}
from concurrent.futures import ThreadPoolExecutor
BATCH = 80   # Windows 命令行上限约 3.2 万字符，带商品标题时一批不能太大（2026-11-13 400 行报 WinError 206）
def run_batch(todo):
    data = "\n".join(f"{i}\t{r['keyword']}\t{','.join(br.get(r['keyword'], []))}\t{(r['departments'] or '')[:70]}" for i, r in todo)
    prompt = (SKILL / "references/clean_prompt.txt").read_text(encoding="utf-8") + "\n\n=== 数据开始 ===\n" + data + "\n=== 数据结束 ===\n"
    res = subprocess.run([agy_bin(), "-p", prompt, "--model", MODEL, "--output-format", "json"],
                         cwd=os.path.expanduser("~/.gemini-offload"), stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
    try:
        d = json.loads(res.stdout)
    except json.JSONDecodeError:
        print("agy 输出不是 JSON:", res.stderr[-300:]); return {}
    if d.get("status") != "SUCCESS":
        print("agy 失败:", str(d)[:300]); return {}
    ids, got = {str(i) for i, _ in todo}, {}
    for line in d.get("response", "").splitlines():
        line = re.sub(r"\x1b\[[0-9;]*m", "", line).strip()
        if not line.startswith("{"): continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(o.get("id")) in ids and o.get("tag") in TAGS: got[str(o["id"])] = o
    return got
for attempt in range(3):
    todo = [(i, r) for i, r in enumerate(rows) if str(i) not in tags]
    if not todo: break
    with ThreadPoolExecutor(3) as ex:
        for got in ex.map(run_batch, [todo[j:j + BATCH] for j in range(0, len(todo), BATCH)]): tags.update(got)
# 人工修正：RUN/overrides.json {"关键词": ["tag", "原因"]}，Claude 抽查后写入
ov = json.load(open(RUN / "overrides.json", encoding="utf-8")) if (RUN / "overrides.json").exists() else {}
for i, r in enumerate(rows):
    if r["keyword"] in ov:
        tags[str(i)] = {"id": str(i), "tag": ov[r["keyword"]][0], "why": ov[r["keyword"]][1], "manual": True}
with open(RUN / "clean_tags.jsonl", "w", encoding="utf-8") as f:
    for i, r in enumerate(rows):
        o = tags.get(str(i), {"id": str(i), "tag": "未标", "why": ""}); o["keyword"] = r["keyword"]
        f.write(json.dumps(o, ensure_ascii=False) + "\n")
cols = list(rows[0].keys())
with open(RUN / "candidates_clean.csv", "w", newline="", encoding="utf-8") as fk, open(RUN / "candidates_removed.csv", "w", newline="", encoding="utf-8") as fr:
    wk = csv.writer(fk); wr = csv.writer(fr); wk.writerow(cols); wr.writerow(cols + ["tag", "why"])
    for i, r in enumerate(rows):
        o = tags.get(str(i))
        if o is None or o["tag"] == "keep": wk.writerow([r[c] for c in cols])
        else: wr.writerow([r[c] for c in cols] + [o["tag"], o.get("why", "")])
from collections import Counter
print(json.dumps({"输入": len(rows), "已标": len(tags), "标签": Counter(o["tag"] for o in tags.values())}, ensure_ascii=False))
