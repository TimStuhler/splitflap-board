#!/usr/bin/env bash
# Starts the split-flap test harness: http://localhost:8123/viewer/
cd "$(dirname "$0")/.." && exec python3 -m http.server 8123
