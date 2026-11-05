#!/usr/bin/env python3
"""拉数据：脚本直连 MCP（卖家精灵 / 西柚）和亚马逊下拉接口，原始返回落盘到 WORK/，模型不转抄数字。

服务器地址和凭证从 antigravity 的 ~/.gemini/config/mcp_config.json 读取（可用环境变量 MJK_MCP_CONFIG 改），
脚本不打印凭证。文件名前缀和 merge_sources.py 约定一致。

用法:
  pull.py ss  WORK --market US SEED [SEED ...] [--min-rel 15] [--max-pages 30]
      卖家精灵 keyword_miner，每页 100 条按月搜索量降序，翻到最后一页 -> ss_<种子>_p<页>.json
  pull.py ac  WORK --market us SEED [SEED ...]
      亚马逊下拉框 30 次/种子词 -> ac_<种子>.json
  pull.py xy  WORK --market US --keywords-file F --user-task "用户原话" [--yes]
      西柚 get_keyword_info，100 词一批 -> xy_<序号>.json。收费（约 10 词 1 Credit）：
      不带 --yes 只打印词数和预计 Credits，不调用
  pull.py asin WORK --market US --keywords-file F --user-task "用户原话" [--page-size 10] [--yes]
      西柚 get_keyword_asin_analysis，每词 1 Credit -> asin_<词>.json；不带 --yes 只打印预计消耗
  pull.py asin-summary WORK
      把 asin_*.json 压成每词前 10 个 ASIN 的一行摘要（标题/价格/自然排名/广告排名/流量占比），供判断意图

每个子命令只打印统计，不打印原始返回。
"""
import argparse, json, re, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

SS_FIELDS = ("keyword,keywordCn,month,searches,purchases,purchaseRate,products,adProducts,bid,bidMin,bidMax,"
             "monopolyClickRate,relevancy,searchRank,avgPrice,spr")


def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:60]


def read_keywords(f):
    """一行一个关键词；出现 Tab 直接报错，防止把 id 或中文列当关键词送去收费接口。"""
    out, seen = [], set()
    for n, line in enumerate(Path(f).read_text().splitlines(), 1):
        if "\t" in line:
            sys.exit(f"{f} 第 {n} 行含 Tab：--keywords-file 只能一行一个关键词")
        k = line.strip().lower()
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out


def check_xy(r, what):
    """西柚返回没有 data 就是失败（余额不足、参数错等），立即停，免得继续扣费。"""
    if not isinstance(r, dict) or not r.get("data"):
        sys.exit(f"西柚 {what} 返回异常，已停止：{str(r)[:300]}")


def call_retry(m, tool, args, tries=3):
    for i in range(tries):
        try:
            return m.call(tool, args)
        except Exception as e:  # 网络抖动或限流，退避重试
            if i == tries - 1:
                raise
            print(f"  {tool} 失败，{3 * (i + 1)}s 后重试：{str(e)[:120]}", file=sys.stderr)
            time.sleep(3 * (i + 1))


def cmd_ss(a, work):
    from mcp_http import MCP
    m = MCP("sellersprite-mcp")
    for seed in a.seeds:
        for old in work.glob(f"ss_{slug(seed)}_p*.json"):  # 清掉上次的页，避免参数变了旧页残留
            old.unlink()
        page, pages, total, months, n = 1, 1, 0, set(), 0
        while page <= min(pages, a.max_pages):
            req = {"keyword": seed, "marketplace": a.market.upper(), "page": page, "size": 100,
                   "order": {"field": "searches", "desc": True}, "returnFields": SS_FIELDS}
            if a.min_rel:
                req["minRelevancy"] = a.min_rel
            r = call_retry(m, "keyword_miner", {"request": req})
            if not isinstance(r, dict) or r.get("code") not in (None, "OK"):
                sys.exit(f"keyword_miner 返回异常（{seed} 第 {page} 页）：{str(r)[:300]}")
            d = r.get("data", {})
            pages, total = d.get("pages") or 1, d.get("total") or 0
            items = d.get("items") or []
            months |= {it.get("month") for it in items if it.get("month")}
            n += len(items)
            (work / f"ss_{slug(seed)}_p{page}.json").write_text(json.dumps(r, ensure_ascii=False))
            page += 1
        cut = "（达到 --max-pages 上限，未取完）" if pages > a.max_pages else ""
        print(f"ss {seed}: total={total} pages={pages} 已取={n} 月份={sorted(months)}{cut}")


def cmd_ac(a, work):
    from amazon_autocomplete import run_alphabet_soup
    for seed in a.seeds:
        d = run_alphabet_soup(seed, a.market.lower())
        (work / f"ac_{slug(seed)}.json").write_text(json.dumps(d, ensure_ascii=False))
        warn = "  ⚠ 失败接近全部，可能被亚马逊拦截，几分钟后重跑" if d["failed_requests"] >= 25 else ""
        print(f"ac {seed}: {d['total_unique']} 词，失败 {d['failed_requests']}/{d['requests']}{warn}")
        time.sleep(2)


def cmd_xy(a, work):
    from merge_sources import load
    kws = read_keywords(a.keywords_file)
    done = {(it.get("searchTerm") or "").strip().lower() for p in work.glob("xy_*.json") for it in load(p)}
    if done & set(kws):
        print(f"xy: {len(done & set(kws))} 词已查过，跳过")
        kws = [k for k in kws if k not in done]
    batches = [kws[i:i + 100] for i in range(0, len(kws), 100)]
    print(f"xy: 待查 {len(kws)} 词，{len(batches)} 批，预计约 {round(len(kws) / 10 + 0.49)} Credits")
    if not a.yes:
        print("未带 --yes，没有调用。确认后加 --yes 重跑。")
        return
    from mcp_http import MCP
    m = MCP("xydc-mcp")
    start = len(list(work.glob("xy_*.json")))
    for i, b in enumerate(batches, start + 1):
        r = call_retry(m, "get_keyword_info", {
            "keywords": b, "country": a.market.upper(), "user_task": a.user_task,
            "intent_summary": "批量查询候选词的 ABA 周搜索量、排名、点击转化率和建议竞价，用于词库分级复核"})
        check_xy(r, f"get_keyword_info 第 {i} 批")
        out = work / f"xy_{i:02d}.json"
        out.write_text(json.dumps(r, ensure_ascii=False))
        print(f"  xy_{i:02d}: 送 {len(b)} 词，返回 {len(load(out))} 条")


def cmd_asin(a, work):
    kws = read_keywords(a.keywords_file)
    skip = [k for k in kws if (work / f"asin_{slug(k)}.json").exists()]
    if skip:
        print(f"asin: {len(skip)} 词已查过，跳过")
        kws = [k for k in kws if k not in skip]
    print(f"asin: 待查 {len(kws)} 词，预计约 {len(kws)} Credits")
    if not a.yes:
        print("未带 --yes，没有调用。确认后加 --yes 重跑。")
        return
    from mcp_http import MCP
    m = MCP("xydc-mcp")
    for k in kws:
        r = call_retry(m, "get_keyword_asin_analysis", {
            "keyword": k, "country": a.market.upper(), "page": 1, "page_size": a.page_size,
            "user_task": a.user_task,
            "intent_summary": "看该词下前几个拿流量的 ASIN 是什么产品，判断搜索意图是否和本品同类"})
        check_xy(r, f"get_keyword_asin_analysis（{k}）")
        r["_keyword"] = k  # 原词面，slug 会丢符号
        (work / f"asin_{slug(k)}.json").write_text(json.dumps(r, ensure_ascii=False))
        print(f"  asin {k}: 已存")


def find_list(d, path="$"):
    """找 ASIN 列表：第一个"元素是字典且含 asin 字段"的列表，返回 (列表, 路径)。"""
    if isinstance(d, list) and d and isinstance(d[0], dict):
        if any(k.lower() == "asin" for k in d[0]):
            return d, path
    if isinstance(d, dict):
        keys = [k for k in ("items", "list", "data", "records", "asins") if k in d] + \
               [k for k in d if k not in ("items", "list", "data", "records", "asins")]
        for k in keys:
            x, p = find_list(d[k], f"{path}.{k}")
            if x:
                return x, p
    return [], path


def pick(it, *names):
    for n in names:
        for k, v in it.items():
            if k.lower() == n.lower() and v not in (None, ""):
                return v
    return None


def cmd_asin_summary(a, work):
    for i, p in enumerate(sorted(work.glob("asin_*.json"))):
        d = json.loads(p.read_text())
        rows, path = find_list(d)
        rows = rows[:10]
        if i == 0:  # 第一份打印列表路径和字段名，核对没抓错再看下面的摘要
            print(f"[结构核对] ASIN 列表路径 {path}，字段：{list(rows[0].keys()) if rows else '未找到含 asin 的列表'}")
        print(f"## {d.get('_keyword') or p.stem[5:]}（{len(rows)} 个）")
        for it in rows:
            title = str(pick(it, "title", "productTitle", "name") or "")[:70]
            print("  " + " | ".join(str(x) for x in (
                pick(it, "asin"), pick(it, "brand"), title, pick(it, "price"),
                f"自然{pick(it, 'orRank', 'organicRank')}", f"广告{pick(it, 'spRank', 'adRank')}",
                f"流量占比{pick(it, 'trafficRatio')}")))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("ss", "ac", "xy", "asin", "asin-summary"):
        s = sub.add_parser(name)
        s.add_argument("work")
        if name == "asin-summary":
            continue
        s.add_argument("--market", required=True)
        if name in ("ss", "ac"):
            s.add_argument("seeds", nargs="+")
        else:
            s.add_argument("--keywords-file", required=True)
            s.add_argument("--user-task", required=True)
            s.add_argument("--yes", action="store_true")
    sub.choices["ss"].add_argument("--min-rel", type=float, default=15)
    sub.choices["ss"].add_argument("--max-pages", type=int, default=30)
    sub.choices["asin"].add_argument("--page-size", type=int, default=10)
    a = ap.parse_args()
    work = Path(a.work)
    work.mkdir(parents=True, exist_ok=True)
    {"ss": cmd_ss, "ac": cmd_ac, "xy": cmd_xy, "asin": cmd_asin, "asin-summary": cmd_asin_summary}[a.cmd](a, work)


if __name__ == "__main__":
    main()
