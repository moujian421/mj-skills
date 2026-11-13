#!/bin/bash
# 跑一周的 ABA 趋势新词发现。用法: run_week.sh [DATE=yyyymmdd 周六]
# DATE 也可以是 yyyymm（月度补跑，只跑异动市场）。不给 DATE 时取 10 天前之前最近的周六（卖家精灵只开放“上一周”，一般隔 10 天左右才有）。
# 拉数默认 DeepSeek（oc_pull.sh）；第 1 轮一个调用都没成功时（免费额度用完、限流）自动换 CodeBuddy hy3（cb_pull.sh）。
# 也可以 PULLER=cb run_week.sh 直接指定。
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"; SKILL="$(dirname "$HERE")"
BO=~/.claude/skills/batch-offload/scripts
export PULLER="${PULLER:-oc}"
if [ $# -ge 1 ]; then DATE="$1"; else
  DATE=$(python3 -c "from datetime import date,timedelta;d=date.today()-timedelta(days=10);print((d-timedelta(days=(d.weekday()-5)%7)).strftime('%Y%m%d'))")
fi
RUN="$SKILL/data/$DATE"; mkdir -p "$RUN"; LOG="$RUN/run.log"
echo "== $DATE $(date) PULLER=$PULLER" >> "$LOG"
py() { python3 "$HERE/aba_trend.py" "$@" 2>&1 | tee -a "$LOG"; }
pull() {  # pull CALLS OUT
  rm -rf "$2"
  if [ "$PULLER" = cb ]; then "$BO/cb_pull.sh" "$1" "$2" 5; else "$BO/oc_pull.sh" "$1" "$2"; fi 2>&1 | tail -2 | tee -a "$LOG"
}
ok_count() { python3 -c "import json,sys;ix=json.load(open('$1/index.json'));print(len(ix) if isinstance(ix,dict) else sum(1 for e in ix if not e.get('error')))" 2>/dev/null || echo 0; }

py calls1 "$RUN" "$DATE"
pull "$RUN/calls1.txt" "$RUN/pull1"
if [ "$(ok_count "$RUN/pull1")" = 0 ] && [ "$PULLER" = oc ]; then
  echo "DeepSeek 没拉到数据（看 pull1/oc/*.jsonl 的 error），改用 CodeBuddy hy3" | tee -a "$LOG"
  export PULLER=cb; py calls1 "$RUN" "$DATE"; pull "$RUN/calls1.txt" "$RUN/pull1"
fi
py calls2 "$RUN"
[ -s "$RUN/calls2.txt" ] && pull "$RUN/calls2.txt" "$RUN/pull2"
py screen "$RUN"
[ -s "$RUN/calls3.txt" ] && pull "$RUN/calls3.txt" "$RUN/pull3"
py final "$RUN"
echo "RUN=$RUN PULLER=$PULLER"
