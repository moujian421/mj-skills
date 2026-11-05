#!/usr/bin/env python3
"""把报告 Markdown 转成可直接写入飞书的版本。
用法: md_to_feishu.py <报告.md> <图表HTML目录> <输出目录(~/files/<任务名>)>
- 图片行 ![图N ...](charts/figN.png) 换成 <html5-block path="@<输出目录>/figN.html"/>，并把 HTML 复制到输出目录（lark-cli 只读 cwd、/tmp、~/files）
- 代码格式（反引号）之外转义 $ < ~（否则 $..$ 会被当成 LaTeX，< 会被当成标签）；反引号内不转义
- 去掉开头 <title>（标题用 --title 传）"""
import re, sys, os, shutil
src, html_dir, out = sys.argv[1], sys.argv[2], os.path.expanduser(sys.argv[3])
os.makedirs(out, exist_ok=True)
s = open(src).read()
s = re.sub(r'^<title>.*?</title>\s*\n', '', s)
lines, n = [], 0
for line in s.split('\n'):
    m = re.match(r'^!\[图(\w+)[^\]]*\]\(charts/fig\w+\.png\)$', line)
    if m:
        f = f'fig{m.group(1)}.html'; shutil.copy(os.path.join(html_dir, f), os.path.join(out, f))
        lines.append(f'<html5-block path="@{out}/{f}"/>'); n += 1; continue
    parts = re.split(r'(`[^`]*`)', line)
    for i, p in enumerate(parts):
        if i % 2: continue
        p = re.sub(r'(?<!\\)\$', r'\\$', p); p = p.replace('<', r'\<'); p = p.replace('~', r'\~')
        parts[i] = p
    lines.append(''.join(parts))
open(os.path.join(out, 'report.md'), 'w').write('\n'.join(lines))
print(f'html5-block {n} 个 -> {out}/report.md')
