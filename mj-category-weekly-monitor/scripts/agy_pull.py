"""Fallback for oc_pull.sh when DeepSeek is unavailable: run a calls.txt through agy, save raw/ + index.json in oc_pull format.
Usage: python3 agy_pull.py CALLS.txt OUT_DIR
Assumes agy's tool steps come back in list order; checks the count and (when present) the asin of each response."""
import json, os, re, subprocess, sys, glob
calls, out = sys.argv[1], sys.argv[2]
lines = [l for l in open(calls).read().split("\n") if l.strip()]
prompt = ("只允许调用下面清单里的查询工具，严格按顺序逐个调用，每行一次，参数原样照抄（JSON 不得改动、不得合并、不得增删），"
          "禁止调用任何其他工具、禁止任何写入/发送/创建/修改/删除操作。全部调用完成后只回复“完成”，不要整理或摘要数据。\n清单：\n" + "\n".join(lines))
os.makedirs(os.path.expanduser("~/.gemini-offload"), exist_ok=True)
# wait in proportion to the call count (a hung agy used to block the run for 25 min)
limit = min(1500, 180 + 40 * len(lines))
try:
    r = subprocess.run([os.path.expanduser("~/.local/bin/agy"), "-p", prompt, "--model", "gemini-3.8-flash-low", "--output-format", "json"],
                       cwd=os.path.expanduser("~/.gemini-offload"), stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=limit)
except subprocess.TimeoutExpired:
    sys.exit(f"agy timed out after {limit}s")
try:
    res = json.loads(r.stdout)
except ValueError:
    sys.exit(f"agy returned no JSON: {r.stdout[:200]} {r.stderr[-200:]}")
if res.get("status") != "SUCCESS": sys.exit(f"agy failed: {r.stdout[:500]} {r.stderr[-500:]}")
base = os.path.expanduser(f"~/.gemini/antigravity-cli/brain/{res['conversation_id']}/.system_generated/steps")
steps = sorted((int(os.path.basename(d)) for d in glob.glob(base + "/*") if os.path.exists(d + "/output.txt")))
def _ok(n):
    try: json.loads(open(f"{base}/{n}/output.txt").read()); return True
    except Exception: return False
if len(steps) > len(lines):  # agy retried after an error: drop the failed attempts
    steps = [n for n in steps if _ok(n)]
os.makedirs(out + "/raw", exist_ok=True); idx = []; problems = []
if len(steps) != len(lines): problems.append(f"steps {len(steps)} != calls {len(lines)}")
for i, (l, n) in enumerate(zip(lines, steps)):
    m = re.match(r'tools\["([^"]+)"\]\["([^"]+)"\]\((.*)\)$', l); srv, tool, args = m.group(1), m.group(2), json.loads(m.group(3))
    txt = open(f"{base}/{n}/output.txt").read(); err = None
    try:
        d = json.loads(txt); dd = d.get("data") if isinstance(d, dict) else None
        got = dd.get("asin") if isinstance(dd, dict) else None   # Sorftime returns data as a list
        if args.get("asin") and got and got != args["asin"]: problems.append(f"line {i+1}: asin {got} != {args['asin']}")
    except Exception as ex:
        err = str(ex)[:200]
    fn = f"{tool}_{i+1:02d}.json" if not err else f"{tool}_{i+1:02d}.txt"
    open(f"{out}/raw/{fn}", "w").write(txt)
    idx.append({"file": fn, "server": srv, "tool": tool, "args": args, "bytes": len(txt), "error": err})
json.dump(idx, open(f"{out}/raw/index.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps({"conversation_id": res["conversation_id"], "calls": len(idx), "errors": [e["file"] for e in idx if e["error"]], "problems": problems,
                  "credits": sum((json.load(open(f"{out}/raw/{e['file']}")).get("cost_credits") or 0) for e in idx if not e["error"])}, ensure_ascii=False))
