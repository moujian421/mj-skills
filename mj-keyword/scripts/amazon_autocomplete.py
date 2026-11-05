#!/usr/bin/env python3
"""亚马逊搜索框下拉词拓词（Alphabet Soup 字母表拓词法），来自 opencode 的 mj-keyword skill。

对一个种子词请求亚马逊官方 Completion 接口 30 次：种子词本身、best/cheap/top 前缀、种子词 + a~z。
纯标准库，免 API Key，支持 us uk de fr it es jp ca au in mx br。

广告词库流程里的用法（每个种子词存一份，文件名必须以 ac_ 开头，merge_sources.py 才认得）:
    python3 amazon_autocomplete.py "golf push cart" us --json > WORK/ac_golf_push_cart.json
JSON 里的 failed_requests 是没拿到结果的请求数；接近 30 说明被亚马逊拦了，过几分钟再跑。
"""

import sys
import json
import argparse
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

MARKETPLACES = {
    "us": {"domain": "amazon.com", "mid": "ATVPDKIKX0DER", "name": "美国站 (US)"},
    "uk": {"domain": "amazon.co.uk", "mid": "A1F83G8C2ARO7P", "name": "英国站 (UK)"},
    "de": {"domain": "amazon.de", "mid": "A1PA6795UKMFR9", "name": "德国站 (DE)"},
    "fr": {"domain": "amazon.fr", "mid": "A13V1IB3VIYZZH", "name": "法国站 (FR)"},
    "it": {"domain": "amazon.it", "mid": "APJ6JRA9NG5V4", "name": "意大利站 (IT)"},
    "es": {"domain": "amazon.es", "mid": "A1RKKUPIHCS9HS", "name": "西班牙站 (ES)"},
    "jp": {"domain": "amazon.co.jp", "mid": "A1VC38T7YXB528", "name": "日本站 (JP)"},
    "ca": {"domain": "amazon.ca", "mid": "A2EUQ1WTGCTBG2", "name": "加拿大站 (CA)"},
    "au": {"domain": "amazon.com.au", "mid": "A39IBJ37TRP1C6", "name": "澳洲站 (AU)"},
    "in": {"domain": "amazon.in", "mid": "A21TJRUUN4KGV", "name": "印度站 (IN)"},
    "mx": {"domain": "amazon.com.mx", "mid": "A1AM78C64UM0Y8", "name": "墨西哥站 (MX)"},
    "br": {"domain": "amazon.com.br", "mid": "A2Q3Y263D00KWC", "name": "巴西站 (BR)"},
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

def query_autocomplete(query_term, domain, mid, timeout=5):
    """请求亚马逊官方 Completion API 获取实时下拉建议词；失败返回 None（和"没有建议词"的 [] 区分开）"""
    encoded = urllib.parse.quote(query_term.strip())
    url = f"https://completion.{domain}/api/2017/suggestions?mid={mid}&alias=aps&prefix={encoded}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8", errors="ignore"))
            suggestions = [s.get("value", "").strip() for s in data.get("suggestions", []) if s.get("value")]
            return suggestions
    except Exception:
        return None

def run_alphabet_soup(keyword, marketplace="us", max_workers=10):
    """
    执行完整的 Alphabet Soup 拓词矩阵：
    1. 基础词 (Seed)
    2. 高商业意图前缀词 (best, cheap, top)
    3. 后缀字母表 A-Z 穷举拓词
    """
    mp_info = MARKETPLACES.get(marketplace.lower())
    if not mp_info:
        raise ValueError(f"未知站点: {marketplace}。支持站点: {', '.join(MARKETPLACES.keys())}")

    domain = mp_info["domain"]
    mid = mp_info["mid"]

    # 任务池定义
    tasks = []
    # 基础词
    tasks.append(("base", "", keyword.strip()))
    # 意图前缀拓展
    for p in ["best ", "cheap ", "top "]:
        tasks.append(("prefix", p.strip(), f"{p}{keyword.strip()}"))
    # A-Z 字母表后缀拓展
    import string
    for letter in string.ascii_lowercase:
        tasks.append(("alphabet", letter, f"{keyword.strip()} {letter}"))

    results_by_tag = {
        "base": [],
        "prefix": {},
        "alphabet": {}
    }
    all_unique_keywords = set()
    failed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_task = {
            executor.submit(query_autocomplete, q, domain, mid): (tag, key, q)
            for tag, key, q in tasks
        }
        for future in as_completed(future_to_task):
            tag, key, q = future_to_task[future]
            suggestions = future.result()
            if suggestions is None:
                failed += 1
                suggestions = []
            for s in suggestions:
                all_unique_keywords.add(s)

            if tag == "base":
                results_by_tag["base"].extend(suggestions)
            elif tag == "prefix":
                if key not in results_by_tag["prefix"]:
                    results_by_tag["prefix"][key] = []
                results_by_tag["prefix"][key].extend(suggestions)
            elif tag == "alphabet":
                if key not in results_by_tag["alphabet"]:
                    results_by_tag["alphabet"][key] = []
                results_by_tag["alphabet"][key].extend(suggestions)

    # 排序与去重
    sorted_all = sorted(list(all_unique_keywords))

    return {
        "keyword": keyword,
        "marketplace": marketplace.upper(),
        "marketplace_name": mp_info["name"],
        "total_unique": len(sorted_all),
        "requests": len(tasks),
        "failed_requests": failed,
        "all_keywords": sorted_all,
        "base_suggestions": sorted(set(results_by_tag["base"])),
        "prefix_suggestions": {k: sorted(set(v)) for k, v in sorted(results_by_tag["prefix"].items())},
        "alphabet_suggestions": {k: sorted(set(v)) for k, v in sorted(results_by_tag["alphabet"].items()) if v}
    }

def main():
    parser = argparse.ArgumentParser(description="亚马逊官方下拉框 Alphabet Soup 字母表拓词工具")
    parser.add_argument("keyword", help="需要拓词的核心种子关键词")
    parser.add_argument("marketplace", nargs="?", default="us", help="目标站点代码 (默认: us，可选: us, uk, de, fr, it, es, jp, ca, au, in, mx, br)")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出完整数据")
    args = parser.parse_args()

    try:
        data = run_alphabet_soup(args.keyword, args.marketplace)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    # 格式化终端/Agent 输出
    print(f"==================================================")
    print(f"🔍 亚马逊下拉框 Alphabet Soup 拓词: [{data['keyword']}]")
    print(f"📍 站点: {data['marketplace_name']} | 共挖掘出 {data['total_unique']} 个唯一有效长尾词")
    if data["failed_requests"]:
        print(f"⚠ {data['requests']} 次请求里有 {data['failed_requests']} 次失败")
    print(f"==================================================\n")

    print(f"--- 1. 基础建议词 (Base Suggestions) ---")
    for s in data["base_suggestions"][:15]:
        print(f"• {s}")
    print()

    print(f"--- 2. 高意图前缀扩展词 (High-Intent Prefixes) ---")
    for p, items in data["prefix_suggestions"].items():
        if items:
            print(f"[{p.upper()}]:")
            for it in items[:6]:
                print(f"  - {it}")
    print()

    print(f"--- 3. A-Z 字母表后缀拓展汇总 (Alphabet Expansion Sample) ---")
    for letter, items in data["alphabet_suggestions"].items():
        if items:
            preview = ", ".join(items[:5])
            more = f" ... (+{len(items)-5} 更多)" if len(items) > 5 else ""
            print(f"[{letter.upper()}]: {preview}{more}")
    print()

    print(f"--- 4. 全量去重长尾词列表 (共 {data['total_unique']} 个) ---")
    for kw in data["all_keywords"]:
        print(kw)

if __name__ == "__main__":
    main()
