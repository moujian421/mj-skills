#!/usr/bin/env python3
"""需求类型打标：新产品 / 旧产品新属性 / 旧产品回暖。
用法: classify.py RUN [RUN2 ...]   （对每个 RUN 的 candidates_clean.csv）
1) agy Flash 拆核心词+新属性+变体（references/core_prompt.txt），缓存在 RUN/core_tags.jsonl
2) 西柚 get_keyword_aba_trends 查核心词 + 1 个变体在 [本期-52 周, 本期-27 周] 共 26 周的在榜情况
   扣费约每 20 个“词·周”1 Credit（2 词×2 周=1，3 词×18 周=3），26 周 × 500 词约 650 Credits
   在榜 >=6 周 或 跨 >=3 个自然月 = 旧产品；核心词或变体任一达标即算
3) 输出 RUN/candidates_classified.csv，打印统计
拉数用 PULLER（oc/cb），和 run_week.sh 一致。"""
import csv, json, os, re, subprocess, sys
from datetime import timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import aba_trend as A
SKILL = Path(__file__).resolve().parent.parent
BO = Path.home() / ".claude/skills/batch-offload/scripts"


from agylib import agy_jsonl


runs = [Path(p).resolve() for p in sys.argv[1:]]
allcores = {}  # core/variant -> 窗口
for run in runs:
    rows = list(csv.DictReader(open(run / "candidates_clean.csv")))
    cache = run / "core_tags.jsonl"
    # 缓存按关键词对应（清洗结果改动后行号会变）
    tags = {json.loads(l)["keyword"]: json.loads(l) for l in open(cache)} if cache.exists() else {}
    need = {str(i): r["keyword"] for i, r in enumerate(rows) if r["keyword"] not in tags}
    if need:
        for i, o in agy_jsonl(SKILL / "references/core_prompt.txt", need).items():
            o["keyword"] = need[i]; tags[o["keyword"]] = o
        with open(cache, "w") as f:
            for o in tags.values(): f.write(json.dumps(o, ensure_ascii=False) + "\n")
    end = A.period_end(json.loads((run / "meta.json").read_text())["date"])
    win = ((end - timedelta(weeks=52)).strftime("%Y-%m-%d"), (end - timedelta(weeks=27)).strftime("%Y-%m-%d"))
    for o in tags.values():
        for k in [o["core"]] + list(o.get("variants") or [])[:1]:
            allcores.setdefault(k.lower().strip(), win)

# 按窗口分组查西柚：每次 30 个词（52 周 × 100 词的返回太大，CodeBuddy 会压缩上下文、丢掉调用记录）
work = runs[0] / "core_pull"; work.mkdir(exist_ok=True)
bywin = {}
for k, w in allcores.items(): bywin.setdefault(w, []).append(k)
lines = []
for (s, e), ks in bywin.items():
    for i in range(0, len(ks), 30):
        lines.append(A.fmt(A.CFG.get("xiyou_server", "xydc-mcp"), "get_keyword_aba_trends", {"keywords": ks[i:i + 30], "start_week": s, "end_week": e, "country": A.CFG["marketplace"],
                     "user_task": A.CFG["user_task"], "intent_summary": "查产品核心词 6–18 个月前的 ABA 在榜情况，判断新产品还是旧产品新属性"}))
(work.parent / "core_calls.txt").write_text("\n".join(lines) + "\n")
puller = os.environ.get("PULLER", "oc")
cmd = [str(BO / "cb_pull.sh"), str(work.parent / "core_calls.txt"), str(work), "2"] if puller == "cb" else [str(BO / "oc_pull.sh"), str(work.parent / "core_calls.txt"), str(work)]
print("西柚调用", len(lines), "次，核心词+变体", len(allcores), "个"); print(subprocess.run(cmd, capture_output=True, text=True).stdout.strip().splitlines()[-1:])
hist, failed = {}, 0
for e, body in A.pulled(work.parent, "core_pull"):
    if not body or body.get("status") != 200:
        failed += 1; print("西柚失败:", str((body or {}).get("data", {}).get("reason") or body)[:120]); continue
    for ent in body["data"].get("entities") or []:
        on = [t["reportToDate"] for t in ent.get("trends") or [] if t.get("searchFrequencyRank")]
        hist[ent["searchTerm"].lower()] = (len(on), len({d[:7] for d in on}))
if failed:
    sys.exit(f"{failed} 次西柚调用失败，不出结果（否则会全部误判成新产品）。修好后删掉 core_pull 重跑。")
from collections import Counter
for run in runs:
    rows = list(csv.DictReader(open(run / "candidates_clean.csv")))
    tags = {json.loads(l)["keyword"]: json.loads(l) for l in open(run / "core_tags.jsonl")}
    cnt = Counter()
    with open(run / "candidates_classified.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(list(rows[0].keys()) + ["core", "attr", "core_weeks", "core_months", "demand_type"])
        for i, r in enumerate(rows):
            o = tags.get(r["keyword"], {"core": "", "attr": "", "variants": []})
            best = max([hist.get(k.lower().strip(), (0, 0)) for k in [o["core"]] + list(o.get("variants") or [])[:1]] or [(0, 0)])
            old = best[0] >= 6 or best[1] >= 3
            attr = (o.get("attr") or "").strip()
            t = "新产品" if not o["core"] else ("旧产品新属性" if old and attr else "旧产品回暖" if old else "新产品")
            if not o["core"]: t = "未拆出"
            cnt[t] += 1
            w.writerow(list(r.values()) + [o["core"], attr, best[0], best[1], t])
    print(run.name, dict(cnt))
