#!/usr/bin/env bash
set -euo pipefail

cat examples/route-topic-request.json | copilot-service ask --stdin
curl -sS http://127.0.0.1:8765/v1/tasks/route-topic \
  -H 'content-type: application/json' \
  --data @examples/route-topic-request.json
