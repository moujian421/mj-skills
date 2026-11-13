#!/bin/bash
# 西柚版 ABA 新兴市场发现，一键跑完。
# 用法: run_xy.sh [--week=2026-10-25 把历史周当本周跑] [--scale=0.5 试跑缩小] [--server=xydc-mcp 换账号]
# 补跑多周时从最早的一周开始逐周跑（跟踪池按时间顺序判断“确认/闪现”）。
# 拉数直连西柚（不经过 LLM），Flash 清洗和拆核心词走 agy。结果在 data/<拉数日期>/。
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"; SKILL="$(dirname "$HERE")"
export PYTHONIOENCODING=utf-8
PY=$(command -v python3 >/dev/null && python3 -c "" 2>/dev/null && echo python3 || echo python)
W=""; for a in "$@"; do case "$a" in --week=*) W="${a#--week=}";; esac; done
if [ -n "$W" ]; then RUN="$SKILL/data/xy_${W//-/}"; else RUN="$SKILL/data/$(date +%Y%m%d)"; fi
mkdir -p "$RUN"; LOG="$RUN/run.log"
echo "== $(date)" >> "$LOG"
for step in "xy_pull.py $RUN $*" "xy_screen.py $RUN" "clean.py $RUN gemini-3.8-flash-medium --reuse" "xy_core.py $RUN" "xy_track.py $RUN"; do
  echo "-- $step" | tee -a "$LOG"
  $PY "$HERE/"$step 2>&1 | tail -5 | tee -a "$LOG"
done
echo "RUN=$RUN"
