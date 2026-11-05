"""Print the lines of CALLS.txt that have no successful raw result under OUT_DIR (any raw/index.json below it).
Usage: python3 missing_calls.py CALLS.txt OUT_DIR > retry.txt
A call counts as done when some index entry has the same tool and identical args and no error."""
import json, re, sys, glob, os
calls, out = sys.argv[1], sys.argv[2]
def key(tool, args): return tool + "|" + json.dumps(args, sort_keys=True, ensure_ascii=False)
done = set()
for ip in glob.glob(os.path.join(out, "**", "raw", "index.json"), recursive=True):
    for e in json.load(open(ip)):
        if not e.get("error"): done.add(key(e["tool"], e.get("args", {})))
for l in open(calls):
    m = re.match(r'tools\["([^"]+)"\]\["([^"]+)"\]\((.*)\)\s*$', l.strip())
    if m and key(m.group(2), json.loads(m.group(3))) not in done: print(l.strip())
