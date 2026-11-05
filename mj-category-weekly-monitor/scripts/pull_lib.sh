# Shared by daily_run.sh and weekly_run.sh. Needs: PY, S, CFG, DATE, TASK, RUN.
# pull STAGE OUTDIR [asins file]: make_calls -> DeepSeek (oc_pull); calls that were skipped, rewritten or errored go to agy once.
# Leaves RUN/STAGE.left.txt non-empty when some calls are still missing.
pull() {
  local st="$1" out="$2" extra=()
  [ -n "${3:-}" ] && extra=(--asins "$3")
  rm -f "${RUN:?}/$st.retry.txt" "${RUN:?}/$st.left.txt"
  $PY "$S/make_calls.py" "$st" --config "$CFG" --out "$RUN/$st.txt" --date "$DATE" --task "$TASK" ${extra[@]+"${extra[@]}"} || return 1
  local stat; stat=$("$HOME/.claude/skills/batch-offload/scripts/oc_pull.sh" "$RUN/$st.txt" "$out" | tail -1)
  echo "$st oc_pull: $stat" | cut -c1-400
  $PY "$S/missing_calls.py" "$RUN/$st.txt" "$out" > "$RUN/$st.retry.txt"
  [ -s "$RUN/$st.retry.txt" ] || return 0
  # SellerSprite snapshots have a Sorftime fallback: don't spend time on agy for them
  if [ "$st" = "daily_snap" ] || [ "$st" = "snapshot" ] || [ "$st" = "new_listing" ] || ! agy_ok; then
    cp "$RUN/$st.retry.txt" "$RUN/$st.left.txt"
    echo "$st still missing $(wc -l < "$RUN/$st.left.txt" | tr -d ' ') lines (agy skipped)"; return 0
  fi
  echo "$st retry $(wc -l < "$RUN/$st.retry.txt" | tr -d ' ') lines via agy"
  $PY "$S/agy_pull.py" "$RUN/$st.retry.txt" "$out/retry" 2>&1 | tail -1 | cut -c1-300
  $PY "$S/missing_calls.py" "$RUN/$st.txt" "$out" > "$RUN/$st.left.txt"
  [ -s "$RUN/$st.left.txt" ] && echo "$st still missing $(wc -l < "$RUN/$st.left.txt" | tr -d ' ') lines"
  return 0
}
notify() { /usr/bin/osascript -e "display notification \"$2\" with title \"$1\"" >/dev/null 2>&1 || true; }
# One run at a time (write_tab.py shares /tmp files; missed jobs all start together after wake). Waits up to 90 min.
lock() {
  local L="$HOME/.claude/skills/mj-category-weekly-monitor/data/.run.lock" i=0
  until mkdir "$L" 2>/dev/null; do
    # holder gone (killed, shutdown): take the lock over
    local holder; holder=$(cat "$L/pid" 2>/dev/null)
    if [ -n "$holder" ] && ! kill -0 "$holder" 2>/dev/null; then rm -f "$L/pid"; rmdir "$L" 2>/dev/null; continue; fi
    i=$((i+1)); [ $i -gt 540 ] && { echo "lock wait timeout"; return 1; }
    sleep 10
  done
  echo $$ > "$L/pid"
  trap 'rm -f "$HOME/.claude/skills/mj-category-weekly-monitor/data/.run.lock/pid"; rmdir "$HOME/.claude/skills/mj-category-weekly-monitor/data/.run.lock" 2>/dev/null' EXIT
}
# Is agy answering? One tiny call with a 90 s limit, checked once per run (result cached in RUN/.agy_ok / .agy_down).
agy_ok() {
  [ -f "${RUN:?}/.agy_ok" ] && return 0
  [ -f "${RUN:?}/.agy_down" ] && return 1
  local out
  out=$(cd "$HOME/.gemini-offload" && /usr/bin/perl -e 'alarm 90; exec @ARGV' "$HOME/.local/bin/agy" -p "只回复 OK" --model gemini-3.8-flash-low --output-format json < /dev/null 2>/dev/null)
  if echo "$out" | grep -q '"status": *"SUCCESS"'; then touch "$RUN/.agy_ok"; return 0; fi
  touch "$RUN/.agy_down"; echo "agy not answering, skipped for this run"; return 1
}
