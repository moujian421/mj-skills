#!/bin/bash
# 日度降价监控：无人值守跑完整个流程（不经过 Claude）。
# 用法: daily_run.sh <类目slug> [YYYY-MM-DD]
# 步骤: 卖家精灵快照(免费；失败时用 Sorftime 前 100) -> 选前 N 竞品 -> 西柚每日价格 -> 判断降价 -> 降价竞品补拉新开广告 -> 主图 -> 写飞书“竞对动作-日度”
# 拉数先用 DeepSeek(oc_pull)，有漏行时把漏掉的行交给 agy 补拉。
set -u
SLUG="$1"; DATE="${2:-$(date +%F)}"
SKILL="$HOME/.claude/skills/mj-category-weekly-monitor"; S="$SKILL/scripts"
CFG="$SKILL/data/$SLUG/config.json"; IMG="$SKILL/data/$SLUG/images"
RUN="$SKILL/data/$SLUG/daily_runs/$DATE"; mkdir -p "$RUN"
LOG="$RUN/run.log"; exec >>"$LOG" 2>&1
PY=/usr/bin/python3
echo "=== $(date '+%F %T') start $SLUG $DATE"
TASK=$($PY -c 'import json,sys;print(json.load(open(sys.argv[1]))["daily"]["task"])' "$CFG")
TOKEN=$($PY -c 'import json,sys;print(json.load(open(sys.argv[1]))["sheet"]["token"])' "$CFG")
fail() { echo "FAIL: $1"; /usr/bin/osascript -e "display notification \"$1（日志：daily_runs/$DATE/run.log）\" with title \"日度降价监控\"" || true; exit 1; }

source "$S/pull_lib.sh"
lock || exit 1

rm -f "${RUN:?}/.agy_ok" "${RUN:?}/.agy_down"
rm -rf "${RUN:?}/snap" "${RUN:?}/sorftime" "${RUN:?}/price" "${RUN:?}/ads"; rm -f "${RUN:?}"/*.retry.txt "${RUN:?}"/*.left.txt
pull daily_snap "$RUN/snap"
# SellerSprite failed: try Sorftime BestSeller top 100
[ -s "$RUN/daily_snap.left.txt" ] && pull daily_sorftime "$RUN/sorftime"
$PY "$S/daily_monitor.py" pick --config "$CFG" --run "$RUN" --date "$DATE" || fail "卖家精灵快照没拉到"
pull daily_price "$RUN/price" "$RUN/asins.txt"
$PY "$S/daily_monitor.py" detect --config "$CFG" --run "$RUN" --date "$DATE" || fail "价格判断出错"
[ -s "$RUN/drop_asins.txt" ] && pull daily_ads "$RUN/ads" "$RUN/drop_asins.txt"
$PY "$S/daily_monitor.py" emit --config "$CFG" --run "$RUN" --date "$DATE" | tee "$RUN/emit.json" || fail "生成表格出错"
ASINS=$($PY -c 'import json,sys;print(" ".join(json.load(open(sys.argv[1]))["asins"]))' "$RUN/emit.json")
[ -n "$ASINS" ] && $PY "$S/fetch_images.py" --dir "$IMG" --asins $ASINS --snapshot "$RUN/snap.json"
CHECK=$($PY "$S/write_tab.py" --token "$TOKEN" --spec "$RUN/spec_daily.json" --images "$IMG" --log "$RUN/write.log" | tail -1)
echo "write: $CHECK"
NEW=$($PY -c 'import json,sys;print(json.load(open(sys.argv[1]))["new_rows"])' "$RUN/emit.json")
BAD=$(echo "$CHECK" | $PY -c 'import json,sys
try: d=json.loads(sys.stdin.read()); print(sum(len(d[k]) for k in ("value_mismatch_rows","cells_without_link","truncated_rows")))
except Exception: print(1)')
[ "$BAD" != "0" ] && fail "写飞书核对没通过"
/usr/bin/osascript -e "display notification \"今天新增 $NEW 个降价竞品\" with title \"日度降价监控\"" || true
# 中间文件只留 14 天
find "${SKILL:?}/data/${SLUG:?}/daily_runs" -mindepth 1 -maxdepth 1 -type d -mtime +14 -exec rm -rf {} +
echo "=== $(date '+%F %T') end"
