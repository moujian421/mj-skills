#!/bin/bash
# 安装周度/日度监控的定时器（已装过的会先卸载再装）。用法: bash install_timers.sh
set -u
cp "/Users/cathug/.claude/skills/mj-category-weekly-monitor/data/exercise-equipment-mats/com.cathug.cwm-weekly-exercise-equipment-mats.plist" ~/Library/LaunchAgents/
launchctl bootout gui/$(id -u)/com.cathug.cwm-weekly-exercise-equipment-mats 2>/dev/null
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.cathug.cwm-weekly-exercise-equipment-mats.plist 2>/dev/null
launchctl print gui/$(id -u)/com.cathug.cwm-weekly-exercise-equipment-mats >/dev/null 2>&1 && echo "OK  com.cathug.cwm-weekly-exercise-equipment-mats" || echo "FAIL com.cathug.cwm-weekly-exercise-equipment-mats"
cp "/Users/cathug/.claude/skills/mj-category-weekly-monitor/data/push-pull-golf-carts/com.cathug.cwm-weekly-push-pull-golf-carts.plist" ~/Library/LaunchAgents/
launchctl bootout gui/$(id -u)/com.cathug.cwm-weekly-push-pull-golf-carts 2>/dev/null
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.cathug.cwm-weekly-push-pull-golf-carts.plist 2>/dev/null
launchctl print gui/$(id -u)/com.cathug.cwm-weekly-push-pull-golf-carts >/dev/null 2>&1 && echo "OK  com.cathug.cwm-weekly-push-pull-golf-carts" || echo "FAIL com.cathug.cwm-weekly-push-pull-golf-carts"
cp "/Users/cathug/.claude/skills/mj-category-weekly-monitor/data/push-pull-golf-carts/com.cathug.cwm-daily-push-pull-golf-carts.plist" ~/Library/LaunchAgents/
launchctl bootout gui/$(id -u)/com.cathug.cwm-daily-push-pull-golf-carts 2>/dev/null
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.cathug.cwm-daily-push-pull-golf-carts.plist 2>/dev/null
launchctl print gui/$(id -u)/com.cathug.cwm-daily-push-pull-golf-carts >/dev/null 2>&1 && echo "OK  com.cathug.cwm-daily-push-pull-golf-carts" || echo "FAIL com.cathug.cwm-daily-push-pull-golf-carts"
cp "/Users/cathug/.claude/skills/mj-category-weekly-monitor/data/exercise-mats/com.cathug.cwm-weekly-exercise-mats.plist" ~/Library/LaunchAgents/
launchctl bootout gui/$(id -u)/com.cathug.cwm-weekly-exercise-mats 2>/dev/null
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.cathug.cwm-weekly-exercise-mats.plist 2>/dev/null
launchctl print gui/$(id -u)/com.cathug.cwm-weekly-exercise-mats >/dev/null 2>&1 && echo "OK  com.cathug.cwm-weekly-exercise-mats" || echo "FAIL com.cathug.cwm-weekly-exercise-mats"
cp "/Users/cathug/.claude/skills/mj-category-weekly-monitor/data/exercise-mats/com.cathug.cwm-daily-exercise-mats.plist" ~/Library/LaunchAgents/
launchctl bootout gui/$(id -u)/com.cathug.cwm-daily-exercise-mats 2>/dev/null
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.cathug.cwm-daily-exercise-mats.plist 2>/dev/null
launchctl print gui/$(id -u)/com.cathug.cwm-daily-exercise-mats >/dev/null 2>&1 && echo "OK  com.cathug.cwm-daily-exercise-mats" || echo "FAIL com.cathug.cwm-daily-exercise-mats"
