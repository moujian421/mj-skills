#!/usr/bin/env python3
"""用 Antigravity CLI（agy）按清单拉 MCP 只读数据，原始返回落盘，只打印统计。DeepSeek（oc_pull.sh）不通时用。

清单格式和 oc_pull.sh 一样，一行一个：tools["<server>"]["<tool>"](<严格 JSON 参数>)
用法：python3 agy_pull.py CALLS.txt OUT_DIR [--batch 12] [--parallel 3] [--model gemini-3.8-flash-low]
结果：OUT_DIR/raw/NN.json（NN = 清单行号）、OUT_DIR/index.json、OUT_DIR/agy/batch_K.json
统计：missing_lines（清单里没执行到的行）、unexpected_calls（执行了但参数和清单不一致）、errors（返回不是 JSON）。
三项都为空数据才完整；有缺失时只把缺的行重跑。
前提：~/.gemini/config/config.json 的 globalPermissionGrants.allow 放行了对应 server，见 data-pulls.md。
"""
import argparse, concurrent.futures as cf, json, os, re, subprocess

AGY = os.path.expanduser('~/.local/bin/agy')
BRAIN = os.path.expanduser('~/.gemini/antigravity-cli/brain')
WORKDIR = os.path.expanduser('~/.gemini-offload')
LINE = re.compile(r'^tools\["([^"]+)"\]\["([^"]+)"\]\((.*)\)\s*$')

PROMPT = """你是数据拉取执行器。对下面清单的每一行，各调用一次 MCP 工具：server 是 tools[...] 第一个名字，工具是第二个名字，参数是括号里的 JSON，原样照抄。
规则：不得修改参数、不得合并、跳过或增加调用；只允许调用清单里的工具；禁止任何写入、发送、创建、修改、删除；禁止读写文件、运行命令、浏览器操作。
不要整理、摘要或转抄返回数据。全部调用完成后只回复“完成”。
=== 清单开始 ===
{calls}
=== 清单结束 ==="""


def norm(server, tool, args):
    return json.dumps([server, tool, args], sort_keys=True, ensure_ascii=False)


def parse_calls(path):
    out = []
    for i, line in enumerate(open(path), 1):
        line = line.strip()
        if not line:
            continue
        m = LINE.match(line)
        if not m:
            raise SystemExit(f'第 {i} 行格式不对: {line[:80]}')
        out.append((i, m.group(1), m.group(2), json.loads(m.group(3)), line))
    return out


def run_batch(k, batch, out, model):
    text = PROMPT.format(calls='\n'.join(c[4] for c in batch))
    res_path = f'{out}/agy/batch_{k}.json'
    with open(res_path, 'w') as f, open(f'{out}/agy/batch_{k}.err', 'w') as e:
        subprocess.run([AGY, '-p', text, '--model', model, '--output-format', 'json'],
                       cwd=WORKDIR, stdin=subprocess.DEVNULL, stdout=f, stderr=e, timeout=1800)
    try:
        return json.load(open(res_path)).get('conversation_id')
    except Exception:
        return None


def harvest(conv):
    """返回 [(server, tool, args, output_text)]，按执行顺序。"""
    d = f'{BRAIN}/{conv}/.system_generated'
    steps = [json.loads(l) for l in open(f'{d}/logs/transcript.jsonl')]
    calls = []
    for s in steps:
        for tc in s.get('tool_calls') or []:
            if tc.get('name') != 'call_mcp_tool':
                # 直接以 mcp_<server>_<tool> 形式调用的，多半参数无效；占位以保持与输出步骤对齐
                if str(tc.get('name', '')).startswith('mcp_'):
                    calls.append(['?', tc['name'], tc.get('args')])
                continue
            a = tc['args']
            calls.append([json.loads(a['ServerName']), json.loads(a['ToolName']), json.loads(a['Arguments'])])
    outs = [s['step_index'] for s in steps if s.get('type') == 'GENERIC' and os.path.exists(f"{d}/steps/{s['step_index']}/output.txt")]
    res = []
    for c, idx in zip(calls, outs):
        res.append((*c, open(f'{d}/steps/{idx}/output.txt').read()))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('calls'); ap.add_argument('out')
    ap.add_argument('--batch', type=int, default=12); ap.add_argument('--parallel', type=int, default=3)
    ap.add_argument('--model', default='gemini-3.8-flash-low')
    ap.add_argument('--only', help='只重跑这些清单行号，如 37-48,52；结果并入已有 index.json')
    a = ap.parse_args()
    os.makedirs(f'{a.out}/raw', exist_ok=True); os.makedirs(f'{a.out}/agy', exist_ok=True)
    calls = parse_calls(a.calls)
    all_lines = {c[0] for c in calls}
    old = []
    if a.only:
        keep = set()
        for part in a.only.split(','):
            lo, _, hi = part.partition('-'); keep |= set(range(int(lo), int(hi or lo) + 1))
        calls = [c for c in calls if c[0] in keep]
        if os.path.exists(f'{a.out}/index.json'):
            old = [x for x in json.load(open(f'{a.out}/index.json')) if x['line'] not in keep]
    want = {norm(c[1], c[2], c[3]): c for c in calls}
    batches = [calls[i:i + a.batch] for i in range(0, len(calls), a.batch)]
    with cf.ThreadPoolExecutor(a.parallel) as ex:
        tag = 'r' if a.only else ''
        convs = list(ex.map(lambda kb: run_batch(f'{tag}{kb[0] + 1}', kb[1], a.out, a.model), enumerate(batches)))
    got, unexpected, errors, index = set(), [], {}, []
    for conv in convs:
        if not conv:
            continue
        for server, tool, args, text in harvest(conv):
            key = norm(server, tool, args)
            if key not in want:
                unexpected.append({'server': server, 'tool': tool, 'args': args}); continue
            n = want[key][0]; got.add(n)
            fn = f'{n:02d}.json'
            # 输出前面可能有 “Created At/Completed At” 行
            body = text[text.find('{'):] if '{' in text else text
            try:
                json.loads(body)
                open(f'{a.out}/raw/{fn}', 'w').write(body)
            except ValueError:
                open(f'{a.out}/raw/{n:02d}.txt', 'w').write(text); errors[n] = text[:150]
            index.append({'line': n, 'file': fn, 'server': server, 'tool': tool, 'args': args, 'bytes': len(body)})
    index += old
    got |= {x['line'] for x in old}
    json.dump(sorted(index, key=lambda x: x['line']), open(f'{a.out}/index.json', 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({'calls': len(calls), 'got': len(got), 'missing_lines': sorted(all_lines - got),
                      'unexpected_calls': len(unexpected), 'errors': errors,
                      'raw_bytes': sum(x['bytes'] for x in index), 'conversations': convs}, ensure_ascii=False))


if __name__ == '__main__':
    main()
