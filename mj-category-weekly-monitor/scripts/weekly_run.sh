#!/bin/bash
# 周度监控的机械部分：无人值守跑完（不经过 Claude），每周二早上由定时器启动。
# 用法: weekly_run.sh <类目slug> [YYYY-MM-DD]
# 做: 快照(卖家精灵，失败用 Sorftime) -> 上升初筛+新品候选 -> 西柚拉数(daily + riser_bsr) -> 确认上升
#     -> 周度表(weekly.py/emit/主图/写飞书) -> 清空上周日度记录。
# 不做(留给 Claude): 新上升商品复盘与录入 config、复盘页签、每月刷新。新上升商品写进 RUN/pending_risers.json。
set -u
SLUG="$1"; DATE="${2:-$(date +%F)}"
SKILL="$HOME/.claude/skills/mj-category-weekly-monitor"; S="$SKILL/scripts"
CFG="$SKILL/data/$SLUG/config.json"; IMG="$SKILL/data/$SLUG/images"; SNAPDIR="$SKILL/data/$SLUG/snapshots"
RUN="$SKILL/data/$SLUG/weekly_runs/$DATE"; mkdir -p "$RUN"
LOG="$RUN/run.log"; exec >>"$LOG" 2>&1
PY=/usr/bin/python3
echo "=== $(date '+%F %T') start $SLUG $DATE"
# 同一周（同一个 ISO 周的运行日期 = 同一个“上一完整周”）已经跑完的就跳过，免得重复扣西柚 Credits
DONE=$($PY - "$SKILL/data/$SLUG/weekly_runs" "$DATE" <<'EOF'
import sys, os, datetime as dt
base, d = sys.argv[1], dt.date.fromisoformat(sys.argv[2])
for n in sorted(os.listdir(base)):
    try: o = dt.date.fromisoformat(n)
    except ValueError: continue
    if o != d and o.isocalendar()[:2] == d.isocalendar()[:2]:
        log = os.path.join(base, n, "run.log")
        if os.path.exists(log) and any(l.startswith("===") and l.rstrip().endswith(" end") for l in open(log)):
            print(n); break
EOF
)
[ -n "$DONE" ] && { echo "SKIP: 本周已在 $DONE 跑过"; exit 0; }
TASK=$($PY -c 'import json,sys;c=json.load(open(sys.argv[1]));print((c.get("daily") or {}).get("task") or "每周自动更新类目竞品周度监控表")' "$CFG")
TOKEN=$($PY -c 'import json,sys;print(json.load(open(sys.argv[1]))["sheet"]["token"])' "$CFG")
source "$S/pull_lib.sh"
lock || exit 1
fail() { echo "FAIL: $1"; notify "周度监控" "$1（日志：weekly_runs/$DATE/run.log）"; exit 1; }
rm -f "${RUN:?}/.agy_ok" "${RUN:?}/.agy_down"
rm -rf "${RUN:?}/snapshot" "${RUN:?}/new_listing" "${RUN:?}/daily" "${RUN:?}/riser_bsr"

# 月度刷新要 Claude 做；过期了照常跑，只提醒
STALE=$($PY -c 'import json,sys,datetime as dt
c=json.load(open(sys.argv[1])); d=dt.date.fromisoformat(sys.argv[2]); pm=(d.replace(day=1)-dt.timedelta(days=1)).strftime("%Y-%m")
print("" if c.get("rank_month")==pm else pm)' "$CFG" "$DATE")

# 1. 快照
pull snapshot "$RUN/snapshot"
[ -s "$RUN/snapshot.left.txt" ] && pull daily_sorftime "$RUN/snapshot/sorftime"
$PY "$S/snapshot.py" --config "$CFG" --pull "$RUN/snapshot" --date "$DATE" --save "$SNAPDIR" || fail "快照没拉到"
SNAP="$SNAPDIR/$DATE.json"
# 2. 上升初筛 + 新品候选
$PY "$S/riser_scan.py" prefilter --config "$CFG" --snapdir "$SNAPDIR" --date "$DATE" --out "$RUN/cand.txt" || fail "上升初筛出错"
pull new_listing "$RUN/new_listing"
$PY "$S/riser_scan.py" supplement --config "$CFG" --snapdir "$SNAPDIR" --date "$DATE" --out "$RUN/cand.txt" --newlist "$RUN/new_listing"
# 3. 西柚拉数
pull daily "$RUN/daily"
[ -s "$RUN/cand.txt" ] && pull riser_bsr "$RUN/riser_bsr" "$RUN/cand.txt"
[ -s "$RUN/daily.left.txt" ] && echo "WARN: daily 有 $(wc -l < "$RUN/daily.left.txt" | tr -d ' ') 个调用没拉到"
# 4. 确认上升（只列出，不录入）
$PY "$S/riser_scan.py" confirm --config "$CFG" --run "$RUN" --date "$DATE" || fail "上升确认出错"
NEWR=$($PY - "$CFG" "$RUN" <<'EOF'
import json, sys
cfg = json.load(open(sys.argv[1])); run = sys.argv[2]
known = {r["asin"] for r in cfg.get("risers", [])}
f = json.load(open(run + "/risers_found.json"))
new = [x for x in f if x["status"] == "riser" and (x["asin"] not in known or any(r["asin"] == x["asin"] and r.get("recheck") for r in cfg.get("risers", [])))]
json.dump({"new": new, "watch": [x for x in f if x["status"] == "watch"]}, open(run + "/pending_risers.json", "w"), ensure_ascii=False, indent=1)
print(len(new))
EOF
)
echo "pending risers: $NEWR"
# 5. 周度表
$PY "$S/weekly.py" --config "$CFG" --run "$RUN" --date "$DATE" > "$RUN/weekly.txt" || fail "周度表计算出错"
$PY "$S/emit_weekly.py" --config "$CFG" --run "$RUN" --date "$DATE" || fail "周度表生成出错"
ASINS=$($PY -c 'import json,sys;print(" ".join(sorted({r["asin"] for r in json.load(open(sys.argv[1]))})))' "$RUN/weekly_rows.json")
[ -n "$ASINS" ] && $PY "$S/fetch_images.py" --dir "$IMG" --asins $ASINS --snapshot "$SNAP"
CHECK=$($PY "$S/write_tab.py" --token "$TOKEN" --spec "$RUN/spec_weekly.json" --images "$IMG" --log "$RUN/write.log" | tail -1)
echo "write weekly: $CHECK"
# 6. 清空上周日度记录
if $PY -c 'import json,sys;sys.exit(0 if json.load(open(sys.argv[1])).get("daily") else 1)' "$CFG"; then
  $PY "$S/daily_monitor.py" reset --config "$CFG" --run "$RUN/daily_reset" --date "$DATE"
  echo "write daily: $($PY "$S/write_tab.py" --token "$TOKEN" --spec "$RUN/daily_reset/spec_daily.json" --images "$IMG" --log "$RUN/write.log" | tail -1)"
fi
BAD=$(echo "$CHECK" | $PY -c 'import json,sys
try: d=json.loads(sys.stdin.read()); print(sum(len(d[k]) for k in ("value_mismatch_rows","cells_without_link","truncated_rows")))
except Exception: print(1)')
MSG="周度表已更新"; [ "$NEWR" != "0" ] && MSG="$MSG；$NEWR 个新上升商品待复盘"; [ -n "$STALE" ] && MSG="$MSG；需要做 $STALE 月度刷新"
[ "$BAD" != "0" ] && MSG="周度表写入核对没通过，看日志"
notify "周度监控" "$MSG"
echo "$MSG"
find "${SKILL:?}/data/${SLUG:?}/weekly_runs" -mindepth 1 -maxdepth 1 -type d -mtime +60 -exec rm -rf {} +
echo "=== $(date '+%F %T') end"
