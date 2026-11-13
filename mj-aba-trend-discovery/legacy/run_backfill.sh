#!/bin/bash
# 月度补跑并清洗。用法: run_backfill.sh 202608 202609 202610
HERE="$(cd "$(dirname "$0")" && pwd)"; SKILL="$(dirname "$HERE")"
for M in "$@"; do
  "$HERE/run_week.sh" "$M" | tail -3
  python3 "$HERE/clean.py" "$SKILL/data/$M"
done
