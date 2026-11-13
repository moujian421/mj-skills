#!/bin/bash
# ABA 文件版（默认）：用卖家后台下载的 ABA 热门搜索词周报，本地筛选，西柚只给候选词补搜索量。
# 用法: run_aba.sh [新下载的 xlsx ...]      不给文件就直接用 data/aba 里最新一周
# 结果在 data/aba_<周>/：trend_<周>.xlsx（候选 / 持续跟踪 / 剔除）、report.md、run.log
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"; SKILL="$(dirname "$HERE")"
export PYTHONIOENCODING=utf-8
PY=python; command -v python >/dev/null || PY=python3
[ $# -gt 0 ] && $PY "$HERE/aba_import.py" "$@"
WEEK=$($PY -c "import json;print(max(json.load(open(r'$SKILL/data/aba/coverage.json'))))")
RUN="$SKILL/data/aba_${WEEK//-/}"; mkdir -p "$RUN"; LOG="$RUN/run.log"
echo "== $(date) 周 $WEEK" >> "$LOG"
for step in "aba_screen.py $RUN $WEEK" "clean.py $RUN gemini-3.8-flash-medium --reuse" "aba_enrich.py $RUN" "xy_core.py $RUN" "xy_track.py $RUN"; do
  echo "-- $step" | tee -a "$LOG"
  $PY "$HERE/"$step 2>&1 | tail -5 | tee -a "$LOG"
done
echo "RUN=$RUN"
