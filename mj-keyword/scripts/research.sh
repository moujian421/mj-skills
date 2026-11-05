#!/bin/bash
# 兼容旧用法：research.sh "<种子词>" [站点] [--json]
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$DIR/amazon_autocomplete.py" "$@"
