"""agy（Gemini Flash）批量 JSONL 文本任务的公共函数。"""
import json, os, re, subprocess


def agy_bin():
    for c in ("~/.local/bin/agy", "~/AppData/Local/agy/bin/agy.exe"):
        if os.path.exists(os.path.expanduser(c)): return os.path.expanduser(c)
    return "agy"
from pathlib import Path


def agy_jsonl(prompt_file, lines, model="gemini-3.8-flash-medium", key="core"):
    """key：返回对象里必须有的字段（值可以是 0）"""
    out, todo = {}, dict(lines)
    for _ in range(3 + len(todo) // 150):   # 每轮最多 150 行（Windows 命令行长度上限），没标上的下一轮重试
        if not todo: break
        data = "\n".join(f"{i}\t{t}" for i, t in list(todo.items())[:150])
        prompt = Path(prompt_file).read_text(encoding="utf-8") + "\n\n=== 数据开始 ===\n" + data + "\n=== 数据结束 ===\n"
        r = subprocess.run([agy_bin(), "-p", prompt, "--model", model, "--output-format", "json"],
                           cwd=os.path.expanduser("~/.gemini-offload"), stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        try:
            d = json.loads(r.stdout)
        except json.JSONDecodeError:
            continue
        for l in d.get("response", "").splitlines():
            l = re.sub(r"\x1b\[[0-9;]*m", "", l).strip()
            if not l.startswith("{"): continue
            try:
                o = json.loads(l)
            except json.JSONDecodeError:
                continue
            if str(o.get("id")) in todo and key in o and o[key] not in (None, ""):
                out[str(o["id"])] = o; todo.pop(str(o["id"]))
    return out
